import os
import subprocess
import tempfile
import requests
from typing import List, Optional


def download_to(path: str, url: str, chunk: int = 1024 * 1024) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = requests.get(url, stream=True, timeout=180)
    r.raise_for_status()
    with open(path, "wb") as f:
        for c in r.iter_content(chunk):
            if c:
                f.write(c)
    return path


def extract_last_frame(video_path: str, out_image_path: str) -> str:
    os.makedirs(os.path.dirname(out_image_path), exist_ok=True)
    # Seek to near end and grab a single frame. This is more portable than relying on 'last' in select()
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",
        "-i", video_path,
        "-frames:v", "1",
        out_image_path,
    ]
    subprocess.run(cmd, check=True)
    return out_image_path


def _probe_duration(path: str) -> float:
    import json
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        stdout=subprocess.PIPE,
        check=True,
        text=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def _normalize_video(input_path: str, output_path: str, fps: int, width: Optional[int]) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    vf_chain = []
    if width:
        vf_chain.append(f"scale={width}:-2")
    vf_chain.append(f"fps=fps={fps}")
    vf_chain.append("format=yuv420p")
    vf_chain.append("setsar=1")
    vf = ",".join(vf_chain)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    return output_path


def merge_two_with_xfade(clip1: str, clip2: str, out_path: str, xfade_sec: float = 1.0, fps: int = 24, width: Optional[int] = 720) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Normalize inputs to constant frame rate and matching geometry/pixel format
    norm1 = os.path.join(os.path.dirname(out_path), "_norm1.mp4")
    norm2 = os.path.join(os.path.dirname(out_path), "_norm2.mp4")
    _normalize_video(clip1, norm1, fps=fps, width=width)
    _normalize_video(clip2, norm2, fps=fps, width=width)

    d1 = _probe_duration(norm1)
    offset = max(0.0, d1 - xfade_sec)
    # Inputs already normalized; still enforce fps/timebase explicitly before xfade
    filter_complex = (
        f"[0:v]fps=fps={fps},format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v0];"
        f"[1:v]fps=fps={fps},format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]xfade=transition=fade:duration={xfade_sec}:offset={offset},format=yuv420p[v]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", norm1,
        "-i", norm2,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-an",  # drop audio for simplicity
        "-movflags", "+faststart",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True)
        return out_path
    except subprocess.CalledProcessError:
        # Fallback: hard cut concat after normalization
        concat_out = out_path + ".tmp.mp4"
        cmd2 = [
            "ffmpeg", "-y",
            "-i", norm1,
            "-i", norm2,
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            concat_out,
        ]
        subprocess.run(cmd2, check=True)
        os.replace(concat_out, out_path)
        return out_path


