import os
import asyncio
import re
import random
from typing import Dict, Any
from bot.utils.logger import logger
from bot.config import FFMPEG_PATH
from media.probe import FFmpegError
from media.effects import get_effect_filter

ASPECT_RATIO_MAP = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "4:3": (1440, 1080),
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
    "21:9": (2560, 1080),
    "4K": (3840, 2160)
}

QUALITY_MAP = {
    "Economy": {"crf": "28", "preset": "veryfast", "ab": "96k"},
    "Balance": {"crf": "23", "preset": "fast", "ab": "128k"},
    "Maximum": {"crf": "18", "preset": "slow", "ab": "192k"}
}

async def get_smart_split_time(input_path: str, duration: float) -> float:
    cmd = [FFMPEG_PATH, '-i', input_path, '-af', 'silencedetect=noise=-30dB:d=0.5', '-f', 'null', '-']
    process = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    output = stderr.decode('utf-8', errors='ignore')
    
    # Look for: silencedetect @ 0x... silence_start: 12.34
    matches = re.findall(r'silence_start:\s+([\d\.]+)', output)
    if matches:
        # Pick a silence that is not too close to the beginning or end (between 20% and 80%)
        valid_times = [float(m) for m in matches if 0.2 * duration < float(m) < 0.8 * duration]
        if valid_times:
            # Return the one closest to the middle
            return min(valid_times, key=lambda x: abs(x - duration/2.0))
            
    # Fallback to middle
    return duration / 2.0

def _get_target_resolution(aspect_ratio_setting: str, orig_width: int, orig_height: int):
    if aspect_ratio_setting == "Original" or aspect_ratio_setting not in ASPECT_RATIO_MAP:
        # ensure even dimensions
        return (orig_width // 2 * 2, orig_height // 2 * 2)
    return ASPECT_RATIO_MAP[aspect_ratio_setting]

def build_filter_graph(
    split_time: float, 
    freeze_duration: float, 
    ad_duration: float, 
    target_w: int, 
    target_h: int, 
    effect: str,
    fps: float
) -> str:
    
    # 1. Format input video (crop/pad/blur background) -> [v_main]
    v_format = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[v_fg];[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},gblur=sigma=20[v_bg_blur];[v_bg_blur][v_fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v_main];"
    
    # Split [v_main] into two parts based on split_time
    v_split = f"[v_main]split=2[v_main_p1][v_main_p2];[v_main_p1]trim=start=0:end={split_time},setpts=PTS-STARTPTS[v1];[v_main_p2]trim=start={split_time},setpts=PTS-STARTPTS[v2];"
    
    # Format freeze frame [2:v]
    f_format = f"[2:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[f_fg];[2:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},gblur=sigma=20[f_bg_blur];[f_bg_blur][f_fg]overlay=(W-w)/2:(H-h)/2,setsar=1[f_main];"
    
    # Loop freeze frame
    f_loop = f"[f_main]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB,trim=duration={freeze_duration}[v_bg_p_raw];"
    
    # Apply Effects to freeze frame
    effect_filters = get_effect_filter(effect, target_w, target_h, fps, freeze_duration, ad_duration)
    eff_p = effect_filters["freeze_filter"] + ";"
    
    # Format Ad video [1:v] - Pad with black or blur
    # Since ad is standalone now, we just scale and pad it to match target aspect ratio
    ad_format = f"[1:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1[v_ad_formatted];"
    
    # Concat Video
    v_concat = f"[v1][v_freeze_pause][v_ad_formatted][v2]concat=n=4:v=1:a=0[v_out];"
    
    # Audio Pipeline
    a_split = f"[0:a]asplit=2[a_part1][a_part2];[a_part1]atrim=start=0:end={split_time},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a1];[a_part2]atrim=start={split_time},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a2];"
    a_pause = f"anullsrc=duration={freeze_duration}:sample_rate=44100:channel_layout=stereo[a_pause];"
    a_ad = f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a_ad];"
    a_concat = f"[a1][a_pause][a_ad][a2]concat=n=4:v=0:a=1[a_out]"
    
    return v_format + v_split + f_format + f_loop + eff_p + ad_format + v_concat + a_split + a_pause + a_ad + a_concat

async def process_advanced_video(
    input_path: str, 
    ad_path: str, 
    output_path: str, 
    settings: Dict[str, Any],
    input_info: dict, 
    ad_info: dict,
    freeze_duration: float = 0.5
):
    duration = input_info['duration']
    pos_setting = settings.get('position', 'Middle')
    
    if pos_setting == "Start": split_time = 0.5
    elif pos_setting == "25%": split_time = duration * 0.25
    elif pos_setting == "Middle": split_time = duration * 0.5
    elif pos_setting == "75%": split_time = duration * 0.75
    elif pos_setting == "End": split_time = max(0.5, duration - 1.0)
    elif pos_setting == "Random": split_time = random.uniform(1.0, duration - 1.0)
    elif pos_setting == "Smart": split_time = await get_smart_split_time(input_path, duration)
    else: split_time = duration * 0.5
    
    target_w, target_h = _get_target_resolution(settings.get("aspect_ratio", "Original"), input_info['width'], input_info['height'])
    
    temp_dir = os.path.dirname(output_path)
    freeze_img = os.path.join(temp_dir, "freeze.png")
    
    # 1. Extract raw freeze frame
    extract_cmd = [FFMPEG_PATH, '-y', '-ss', str(split_time), '-i', input_path, '-frames:v', '1', freeze_img]
    ex_proc = await asyncio.create_subprocess_exec(*extract_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await ex_proc.communicate()
    if ex_proc.returncode != 0:
        raise FFmpegError("Failed to extract freeze frame")
        
    # 2. Build filter graph
    # Assume fps is 30 for calculations
    fps = 30.0
    filter_graph = build_filter_graph(
        split_time=split_time,
        freeze_duration=freeze_duration,
        ad_duration=ad_info['duration'],
        target_w=target_w,
        target_h=target_h,
        effect=settings.get("effect", "Classic"),
        fps=fps
    )
    
    qual = QUALITY_MAP.get(settings.get("quality", "Balance"), QUALITY_MAP["Balance"])
    
    # 3. Execute FFmpeg
    cmd = [
        FFMPEG_PATH, '-y',
        '-i', input_path,
        '-i', ad_path,
        '-i', freeze_img,
        '-filter_complex', filter_graph,
        '-map', '[v_out]',
        '-map', '[a_out]',
        '-c:v', 'libx264',
        '-preset', qual["preset"],
        '-crf', qual["crf"],
        '-c:a', 'aac',
        '-b:a', qual["ab"],
        output_path
    ]
    
    logger.info(f"Running Advanced FFmpeg...")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        raise FFmpegError(f"FFmpeg process failed with code {process.returncode}")

