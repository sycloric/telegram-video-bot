import asyncio
import json
import os
from bot.utils.logger import logger
from bot.config import (
    FFMPEG_PATH, FFPROBE_PATH,
    CHROMA_KEY_COLOR, CHROMA_SIMILARITY, CHROMA_BLEND,
    AD_SCALE, AD_POSITION_X, AD_POSITION_Y
)

class FFmpegError(Exception):
    pass

async def probe_video(file_path: str) -> dict:
    cmd = [
        FFPROBE_PATH,
        '-v', 'error',
        '-show_entries', 'format=duration:stream=width,height,codec_type',
        '-of', 'json',
        file_path
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFprobe failed: {stderr.decode()}")
            raise FFmpegError("Failed to probe video.")
            
        data = json.loads(stdout.decode())
        duration = float(data['format'].get('duration', 0))
        has_audio = False
        has_video = False
        width = 0
        height = 0
        
        for stream in data.get('streams', []):
            if stream['codec_type'] == 'video':
                has_video = True
                width = int(stream.get('width', 0))
                height = int(stream.get('height', 0))
            elif stream['codec_type'] == 'audio':
                has_audio = True
                
        return {
            "duration": duration,
            "has_audio": has_audio,
            "has_video": has_video,
            "width": width,
            "height": height
        }
    except Exception as e:
        logger.error(f"Error in probe_video: {e}")
        raise FFmpegError(f"Probe error: {e}")

def get_overlay_x(pos_x):
    if pos_x.lower() == "center": return "(W-w)/2"
    if pos_x.lower() == "left": return "0"
    if pos_x.lower() == "right": return "W-w"
    return pos_x

def get_overlay_y(pos_y):
    if pos_y.lower() == "center": return "(H-h)/2"
    if pos_y.lower() == "top": return "0"
    if pos_y.lower() == "bottom": return "H-h"
    return pos_y

async def process_video_with_ad(input_path: str, ad_path: str, output_path: str, split_time: float, freeze_duration: float, input_info: dict, ad_info: dict, target_aspect: str = "16:9"):
    has_audio = input_info['has_audio']
    width = input_info['width']
    height = input_info['height']
    duration = input_info['duration']
    
    ad_has_audio = ad_info['has_audio']
    ad_duration = ad_info['duration']
    
    temp_dir = os.path.dirname(output_path)
    freeze_img = os.path.join(temp_dir, "freeze.png")
    
    # Pre-crop if needed
    crop_filter = ""
    if target_aspect == "4:3":
        # Crop 16:9 to 4:3 (assuming input is wider than 4:3)
        crop_filter = "[0:v]crop=ih*4/3:ih[v_cropped];"
        width = int(height * 4 / 3)
    
    # Extract exact frame at split_time
    # We must apply crop when extracting the frame too if cropping is applied
    if target_aspect == "4:3":
        extract_cmd = [FFMPEG_PATH, '-y', '-ss', str(split_time), '-i', input_path, '-vf', 'crop=ih*4/3:ih', '-frames:v', '1', freeze_img]
    else:
        extract_cmd = [FFMPEG_PATH, '-y', '-ss', str(split_time), '-i', input_path, '-frames:v', '1', freeze_img]
        
    process_ex = await asyncio.create_subprocess_exec(*extract_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process_ex.communicate()
    
    if process_ex.returncode != 0:
        logger.error("Failed to extract freeze frame")
        raise FFmpegError("Failed to extract freeze frame")
    
    filter_complex = []
    
    if target_aspect == "4:3":
        filter_complex.append(f"[0:v]crop=ih*4/3:ih[v_cropped]")
        input_vid_lbl = "[v_cropped]"
    else:
        input_vid_lbl = "[0:v]"
        
    # Splitting input streams to avoid multiple references
    filter_complex.append(f"{input_vid_lbl}split=2[v_part1][v_part2]")

    
    # 1. Part 1 Video
    filter_complex.append(f"[v_part1]trim=start=0:end={split_time},setpts=PTS-STARTPTS,setsar=1[v1]")
    
    # Splitting freeze image if we have a pause before ad
    if freeze_duration > 0:
        filter_complex.append("[2:v]split=2[v_bg_p][v_bg_a]")
        filter_complex.append(f"[v_bg_p]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB,trim=duration={freeze_duration},setsar=1[v_freeze_pause]")
        filter_complex.append(f"[v_bg_a]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB,trim=duration={ad_duration},setsar=1[v_bg_ad]")
    else:
        filter_complex.append(f"[2:v]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB,trim=duration={ad_duration},setsar=1[v_bg_ad]")
    
    # Ad Video Processing
    ad_target_w = width * AD_SCALE
    ad_target_h = height * AD_SCALE
    
    filter_complex.append(f"[1:v]chromakey={CHROMA_KEY_COLOR}:{CHROMA_SIMILARITY}:{CHROMA_BLEND}[ck_ad]")
    filter_complex.append(f"[ck_ad]scale={ad_target_w}:{ad_target_h}:force_original_aspect_ratio=decrease,setsar=1[ad_scaled]")
    
    # Overlay Ad on Background
    x_expr = get_overlay_x(AD_POSITION_X)
    y_expr = get_overlay_y(AD_POSITION_Y)
    filter_complex.append(f"[v_bg_ad][ad_scaled]overlay=x={x_expr}:y={y_expr}:format=auto,setpts=PTS-STARTPTS[v_ad_overlaid]")
    
    # 4. Part 2 Video
    filter_complex.append(f"[v_part2]trim=start={split_time},setpts=PTS-STARTPTS,setsar=1[v2]")
    
    # AUDIO
    afmt = "aformat=sample_rates=44100:channel_layouts=stereo"
    if has_audio:
        filter_complex.append("[0:a]asplit=2[a_part1][a_part2]")
        filter_complex.append(f"[a_part1]atrim=start=0:end={split_time},asetpts=PTS-STARTPTS,{afmt}[a1]")
        filter_complex.append(f"[a_part2]atrim=start={split_time},asetpts=PTS-STARTPTS,{afmt}[a2]")
    else:
        filter_complex.append(f"anullsrc=duration={split_time}:sample_rate=44100:channel_layout=stereo[a1]")
        part2_dur = max(0, duration - split_time)
        filter_complex.append(f"anullsrc=duration={part2_dur}:sample_rate=44100:channel_layout=stereo[a2]")
        
    # Freeze Pause Audio
    if freeze_duration > 0:
        filter_complex.append(f"anullsrc=duration={freeze_duration}:sample_rate=44100:channel_layout=stereo[a_pause]")
    
    # Ad Audio
    if ad_has_audio:
        filter_complex.append(f"[1:a]{afmt},asetpts=PTS-STARTPTS[a_ad]")
    else:
        filter_complex.append(f"anullsrc=duration={ad_duration}:sample_rate=44100:channel_layout=stereo[a_ad]")
        
    # Concat
    if freeze_duration > 0:
        filter_complex.append("[v1][a1][v_freeze_pause][a_pause][v_ad_overlaid][a_ad][v2][a2]concat=n=4:v=1:a=1[v_out][a_out]")
    else:
        filter_complex.append("[v1][a1][v_ad_overlaid][a_ad][v2][a2]concat=n=3:v=1:a=1[v_out][a_out]")
    
    fc_str = ";".join(filter_complex)
    
    cmd = [
        FFMPEG_PATH,
        '-y',
        '-i', input_path,
        '-i', ad_path,
        '-i', freeze_img,
        '-filter_complex', fc_str,
        '-map', '[v_out]',
        '-map', '[a_out]',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        output_path
    ]
    
    logger.info(f"Running FFmpeg: {' '.join(cmd)}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"FFmpeg failed: {stderr.decode()}")
        raise FFmpegError("Failed to process video.")
    
    logger.info("Video processed successfully.")
    return True
