import random

def get_effect_filter(effect_name: str, width: int, height: int, fps: float, freeze_duration: float, ad_duration: float) -> dict:
    """
    Returns a dictionary containing the specific filter chains for the chosen effect.
    The pipeline expects these keys:
    - `freeze_filter`: applied to the looped freeze frame BEFORE the ad starts. (Input: [v_bg_p_raw], Output: [v_freeze_pause])
    - `ad_bg_filter`: applied to the looped freeze frame DURING the ad. (Input: [v_bg_a_raw], Output: [v_bg_ad])
    - `transition_in`: applied between v1 and ad (optional, mostly handled by freeze_filter)
    - `transition_out`: applied after ad, before v2 (optional)
    """
    effects = ["Classic", "Freeze + Zoom", "Freeze + Blur", "Snap", "Glitch", "Dark Transition", "Flash", "Zoom Out", "Cinematic", "Shake", "Pop"]
    if effect_name == "Random" or effect_name not in effects:
        effect_name = random.choice(effects)
        
    freeze_frames = int(fps * freeze_duration)
        
    filters = {
        "freeze_filter": f"[v_bg_p_raw]copy[v_freeze_pause]", # Default pass-through
        "ad_bg_filter": f"[v_bg_a_raw]copy[v_bg_ad]"
    }
    
    if effect_name == "Classic":
        pass # defaults are fine
        
    elif effect_name == "Freeze + Blur":
        # We need a static blur for the background during the ad
        filters["ad_bg_filter"] = f"[v_bg_a_raw]gblur=sigma=10[v_bg_ad]"
        # Fade from clear to blur during the freeze duration. 
        # Since gblur isn't easily animatable, we'll just apply the blur to the pause as well for simplicity, or step it.
        # Let's just apply static blur for now to avoid extreme complexity in blending.
        filters["freeze_filter"] = f"[v_bg_p_raw]gblur=sigma=5[v_freeze_pause]"
        
    elif effect_name == "Freeze + Zoom":
        z_step = 0.5 / max(freeze_frames, 1)
        # zoompan takes a single frame and creates a video, but since we feed it a looped video, we must be careful.
        # Actually zoompan works best on a single image.
        filters["freeze_filter"] = f"[v_bg_p_raw]zoompan=z='min(zoom+{z_step},1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}[v_freeze_pause]"
        # For the ad background, we keep it at 1.5x zoom
        filters["ad_bg_filter"] = f"[v_bg_a_raw]crop=iw/1.5:ih/1.5:iw/2-iw/3:ih/2-ih/3,scale={width}:{height}[v_bg_ad]"

    elif effect_name == "Flash":
        # White fade in and out
        filters["freeze_filter"] = f"[v_bg_p_raw]fade=t=in:c=white:d={freeze_duration}[v_freeze_pause]"
        
    elif effect_name == "Dark Transition":
        # Black fade
        filters["freeze_filter"] = f"[v_bg_p_raw]fade=t=in:c=black:d={freeze_duration}[v_freeze_pause]"

    elif effect_name == "Glitch":
        # RGB shift and noise for a glitchy look
        filters["freeze_filter"] = f"[v_bg_p_raw]rgbashift=rh=10:bv=-10,noise=c0s=20:allf=t[v_freeze_pause]"
        filters["ad_bg_filter"] = f"[v_bg_a_raw]rgbashift=rh=5:bv=-5[v_bg_ad]"

    elif effect_name == "Shake":
        # Shake effect using crop offset
        filters["freeze_filter"] = f"[v_bg_p_raw]crop=iw*0.9:ih*0.9:'iw*0.05+10*sin(t*50)':'ih*0.05+10*cos(t*40)',scale={width}:{height}[v_freeze_pause]"
        
    elif effect_name == "Cinematic":
        # Add cinematic black bars (letterbox) and slight color grade (increased contrast)
        filters["freeze_filter"] = f"[v_bg_p_raw]eq=contrast=1.2:saturation=1.2,drawbox=y=0:w=iw:h=ih*0.1:color=black:t=fill,drawbox=y=ih*0.9:w=iw:h=ih*0.1:color=black:t=fill[v_freeze_pause]"
        filters["ad_bg_filter"] = f"[v_bg_a_raw]eq=contrast=1.2:saturation=1.2,drawbox=y=0:w=iw:h=ih*0.1:color=black:t=fill,drawbox=y=ih*0.9:w=iw:h=ih*0.1:color=black:t=fill[v_bg_ad]"

    elif effect_name == "Pop":
        # Fast zoom in, then slight bounce back
        filters["freeze_filter"] = f"[v_bg_p_raw]zoompan=z='if(lte(pzoom,1.0), 1.2, max(1.1, pzoom-0.05))':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}[v_freeze_pause]"
        filters["ad_bg_filter"] = f"[v_bg_a_raw]crop=iw/1.1:ih/1.1:iw/2-iw/2.2:ih/2-ih/2.2,scale={width}:{height}[v_bg_ad]"

    elif effect_name == "Snap":
        # High contrast, inverted colors for a split second
        filters["freeze_filter"] = f"[v_bg_p_raw]negate,eq=contrast=2[v_freeze_pause]"
        
    elif effect_name == "Zoom Out":
        # Shrink the frame into the center
        filters["freeze_filter"] = f"[v_bg_p_raw]zoompan=z='max(zoom-0.01, 0.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}[v_freeze_pause]"
        filters["ad_bg_filter"] = f"[v_bg_a_raw]scale={width*0.5}:{height*0.5},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black[v_bg_ad]"

    return filters

