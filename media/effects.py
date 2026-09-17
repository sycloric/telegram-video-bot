import random

def get_effect_filter(effect_name: str, width: int, height: int, fps: float, freeze_duration: float, ad_duration: float) -> dict:
    """
    Returns a dictionary containing the specific filter chains for the chosen effect.
    The pipeline expects:
    - `freeze_filter`: applied to the SINGLE extracted frame [f_main]. 
      It MUST generate a video stream [v_freeze_pause] of exactly `freeze_duration` seconds at `fps`.
    """
    effects = ["Classic", "Freeze + Zoom", "Freeze + Blur", "Snap", "Glitch", "Dark Transition", "Flash", "Zoom Out", "Cinematic", "Shake", "Pop"]
    if effect_name == "Random" or effect_name not in effects:
        effect_name = random.choice(effects)
        
    freeze_frames = int(fps * freeze_duration)
    
    # Base loop template for static effects
    base_loop = f"loop=-1:1:0,setpts=N/({fps}*TB),trim=duration={freeze_duration},fps={fps},format=yuv420p"
    
    filters = {}
    
    if effect_name == "Classic":
        filters["freeze_filter"] = f"[f_main]{base_loop}[v_freeze_pause]"
        
    elif effect_name == "Freeze + Blur":
        filters["freeze_filter"] = f"[f_main]gblur=sigma=10,{base_loop}[v_freeze_pause]"
        
    elif effect_name == "Freeze + Zoom":
        z_step = 0.5 / max(freeze_frames, 1)
        filters["freeze_filter"] = f"[f_main]zoompan=z='min(1.0+({z_step}*on),1.5)':d={freeze_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},trim=duration={freeze_duration},fps={fps},format=yuv420p[v_freeze_pause]"

    elif effect_name == "Flash":
        filters["freeze_filter"] = f"[f_main]{base_loop},fade=t=in:c=white:d={freeze_duration}[v_freeze_pause]"
        
    elif effect_name == "Dark Transition":
        filters["freeze_filter"] = f"[f_main]{base_loop},fade=t=in:c=black:d={freeze_duration}[v_freeze_pause]"

    elif effect_name == "Glitch":
        filters["freeze_filter"] = f"[f_main]{base_loop},rgbashift=rh=10:bv=-10,noise=c0s=20:allf=t[v_freeze_pause]"

    elif effect_name == "Shake":
        filters["freeze_filter"] = f"[f_main]{base_loop},crop=iw*0.9:ih*0.9:'iw*0.05+10*sin(t*50)':'ih*0.05+10*cos(t*40)',scale={width}:{height}[v_freeze_pause]"
        
    elif effect_name == "Cinematic":
        filters["freeze_filter"] = f"[f_main]eq=contrast=1.2:saturation=1.2,drawbox=y=0:w=iw:h=ih*0.1:color=black:t=fill,drawbox=y=ih*0.9:w=iw:h=ih*0.1:color=black:t=fill,{base_loop}[v_freeze_pause]"

    elif effect_name == "Pop":
        filters["freeze_filter"] = f"[f_main]zoompan=z='if(eq(on,1), 1.2, max(1.0, pzoom-0.02))':d={freeze_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},trim=duration={freeze_duration},fps={fps},format=yuv420p[v_freeze_pause]"

    elif effect_name == "Snap":
        filters["freeze_filter"] = f"[f_main]negate,eq=contrast=2,{base_loop}[v_freeze_pause]"
        
    elif effect_name == "Zoom Out":
        z_step = 0.5 / max(freeze_frames, 1)
        filters["freeze_filter"] = f"[f_main]zoompan=z='max(1.5-({z_step}*on), 1.0)':d={freeze_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},trim=duration={freeze_duration},fps={fps},format=yuv420p[v_freeze_pause]"

    else:
        filters["freeze_filter"] = f"[f_main]{base_loop}[v_freeze_pause]"

    return filters
