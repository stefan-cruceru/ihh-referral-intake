"""Render the bilingual Lamplight demo from a real application recording.

Requires Pillow and imageio-ffmpeg. The default output is exactly 120 seconds,
1920 x 1080, 30 fps, H.264 / AAC. Narration captions remain optional sidecar
files; only chapter labels are composited into the branded header.
No network requests are made. All intermediates live in the supplied scratch
directory (required via --scratch) and are removed.

Timeline accepts either a list of scene dictionaries, a list of six-item rows
[start, end, title_en, title_es, caption_en, caption_es], or an object containing
"scenes" and optional top-level "cues". A scene may contain a "cues" list to
subdivide its captions. All cue times are absolute seconds unless the cue has
"relative": true. Cue text keys may be caption_en/caption_es or en/es.

Example:
  python render_lamplight.py --raw raw.webm --audio narration.mp3 \
      --timeline timeline.json --scratch session-scratch --output final.mp4 --cover-time 24
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FPS = 1920, 1080, 30
VIDEO_X, VIDEO_Y, VIDEO_W, VIDEO_H = 0, 84, 1920, 912
CREAM = "#FFF8F0"
INK = "#3B2B22"
SPANISH = "#A0461F"
AMBER = "#E39235"
SAND = "#F4EADB"
LINE = "#E2CDB8"


def fonts(regular: Path, bold: Path) -> tuple[Path, Path]:
    """Sam's brand uses Public Sans only; fail rather than substitute a font."""
    for path in (regular, bold):
        if not path.is_file():
            raise FileNotFoundError(path)
        family, _ = ImageFont.truetype(str(path), 24).getname()
        if "public sans" not in family.lower():
            raise ValueError(f"The brand requires Public Sans, found {family!r}: {path}")
    return regular, bold


def caption_text(cue: dict[str, Any], language: str) -> str:
    return str(cue.get(f"caption_{language}", cue.get(language, ""))).strip()


def load_timeline(path: Path, duration: float) -> tuple[list[dict], list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    raw_scenes = data.get("scenes", []) if isinstance(data, dict) else data
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("Timeline must contain at least one scene.")
    scenes, cues = [], []
    for value in raw_scenes:
        if isinstance(value, list):
            if len(value) != 6:
                raise ValueError("Scene rows must contain exactly six items.")
            scene = dict(zip(("start", "end", "title_en", "title_es",
                              "caption_en", "caption_es"), value))
        elif isinstance(value, dict):
            scene = dict(value)
        else:
            raise ValueError("Every scene must be a dictionary or a six-item row.")
        scene["start"], scene["end"] = float(scene["start"]), float(scene["end"])
        if not (0 <= scene["start"] < scene["end"] <= duration + 0.001):
            raise ValueError(f"Scene outside 0–{duration:g} seconds: {scene}")
        scene.setdefault("title_en", "")
        scene.setdefault("title_es", "")
        scenes.append(scene)
        for value in scene.get("cues", [scene]):
            cue = dict(value)
            cue.setdefault("start", scene["start"])
            cue.setdefault("end", scene["end"])
            cue["start"], cue["end"] = float(cue["start"]), float(cue["end"])
            if cue.get("relative"):
                cue["start"] += scene["start"]
                cue["end"] += scene["start"]
            if caption_text(cue, "en") or caption_text(cue, "es"):
                cues.append(cue)
    if isinstance(data, dict) and "cues" in data:
        cues = [dict(value) for value in data["cues"]]
    scenes.sort(key=lambda scene: scene["start"])
    for previous, current in zip(scenes, scenes[1:]):
        if current["start"] < previous["end"] - 0.001:
            raise ValueError("Scene times overlap.")
    for cue in cues:
        cue["start"], cue["end"] = float(cue["start"]), float(cue["end"])
        if not (0 <= cue["start"] < cue["end"] <= duration + 0.001):
            raise ValueError(f"Caption cue outside the video: {cue}")
    cues.sort(key=lambda cue: cue["start"])
    for previous, current in zip(cues, cues[1:]):
        if current["start"] < previous["end"] - 0.001:
            raise ValueError("Caption cue times overlap.")
    return scenes, cues


def fit_font(text: str, font_path: Path, size: int, max_width: int,
             min_size: int = 16) -> ImageFont.FreeTypeFont:
    while size > min_size:
        font = ImageFont.truetype(str(font_path), size)
        if font.getlength(text) <= max_width:
            return font
        size -= 1
    return ImageFont.truetype(str(font_path), size)


def make_frame(path: Path, font_path: Path, bold_path: Path, logo_path: Path) -> None:
    """A transparent video window preserves every pixel of the app recording."""
    image = Image.new("RGBA", (WIDTH, HEIGHT), CREAM)
    draw = ImageDraw.Draw(image)
    draw.rectangle((VIDEO_X, VIDEO_Y, VIDEO_X + VIDEO_W - 1,
                    VIDEO_Y + VIDEO_H - 1), fill=(0, 0, 0, 0))
    draw.rectangle((VIDEO_X - 1, VIDEO_Y - 1, VIDEO_X + VIDEO_W,
                    VIDEO_Y + VIDEO_H), outline=LINE, width=1)
    logo = Image.open(logo_path).convert("RGBA")
    if logo.getbbox():
        logo = logo.crop(logo.getbbox())
    logo.thumbnail((42, 46), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (80, 8))
    draw.text((137, 12), "Lamplight", font=ImageFont.truetype(str(bold_path), 31),
              fill=INK)
    draw.line((315, 17, 315, 49), fill=LINE, width=1)
    disclosure = ImageFont.truetype(str(bold_path), 17)
    disclosure_es = ImageFont.truetype(str(font_path), 16)
    draw.text((1840, 11), "Prototype · Fictional patients", font=disclosure,
              anchor="ra", fill=INK)
    draw.text((1840, 35), "Prototipo · Pacientes ficticios", font=disclosure_es,
              anchor="ra", fill=SPANISH)
    draw.rectangle((0, HEIGHT - 5, WIDTH, HEIGHT), fill=SAND)
    image.save(path)


def ass_time(seconds: float) -> str:
    centiseconds = round(seconds * 100)
    return (f"{centiseconds // 360000}:"
            f"{centiseconds // 6000 % 60:02d}:"
            f"{centiseconds // 100 % 60:02d}."
            f"{centiseconds % 100:02d}")


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def write_chapters(path: Path, scenes: list[dict],
                   font_path: Path, bold_path: Path) -> None:
    family = "Public Sans"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Chapter,{family},23,&H00222B3B,&H00222B3B,&H00F0F8FF,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: ChapterES,{family},18,&H001F46A0,&H001F46A0,&H00F0F8FF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Number,{family},23,&H003592E3,&H003592E3,&H00F0F8FF,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    def event(start: float, end: float, style: str, text: str, tags: str) -> None:
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,"
                     f"{{{tags}}}{text}\n")

    # If caption subdivisions are represented as repeated scene rows, retain
    # one chapter number and one entrance animation for the complete chapter.
    chapters = []
    for scene in scenes:
        if (chapters and scene["title_en"] == chapters[-1]["title_en"]
                and scene["title_es"] == chapters[-1]["title_es"]
                and abs(scene["start"] - chapters[-1]["end"]) < 0.01):
            chapters[-1]["end"] = scene["end"]
        else:
            chapters.append(dict(scene))
    for index, scene in enumerate(chapters, 1):
        start, end = scene["start"], scene["end"]
        event(start, end, "Number", f"{index:02d}", r"\pos(339,18)\fad(250,0)")
        en_size = fit_font(str(scene["title_en"]), bold_path, 23, 970).size
        es_size = fit_font(str(scene["title_es"]), font_path, 18, 970).size
        event(start, end, "Chapter", ass_escape(str(scene["title_en"])),
              rf"\pos(392,7)\fs{en_size}\fad(250,0)")
        event(start, end, "ChapterES", ass_escape(str(scene["title_es"])),
              rf"\pos(392,36)\fs{es_size}\fad(250,0)")
    path.write_text("".join(lines), encoding="utf-8")


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def render(args: argparse.Namespace) -> None:
    for required in (args.raw, args.audio, args.timeline):
        if not required.is_file():
            raise FileNotFoundError(required)
    duration = args.duration
    if duration <= 0 or not math.isfinite(duration):
        raise ValueError("Duration must be a positive finite number.")
    if args.video_offset < 0 or not math.isfinite(args.video_offset):
        raise ValueError("Video offset must be a nonnegative finite number.")
    scenes, cues = load_timeline(args.timeline, duration)
    regular, bold = fonts(args.font, args.font_bold)
    if not args.brand_logo.is_file():
        raise FileNotFoundError(args.brand_logo)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args.scratch.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # TempDirectory only ever deletes intermediates created by this invocation.
    with tempfile.TemporaryDirectory(prefix="lamplight-composite-", dir=args.scratch) as temp:
        stage = Path(temp)
        font_dir = stage / "fonts"
        font_dir.mkdir()
        shutil.copy2(regular, font_dir / regular.name)
        shutil.copy2(bold, font_dir / bold.name)
        make_frame(stage / "frame.png", regular, bold, args.brand_logo)
        write_chapters(stage / "chapters.ass", scenes, regular, bold)
        stage_filters = (
            f"[0:v]trim=start={args.video_offset},setpts=PTS-STARTPTS,fps={FPS},"
            f"scale={VIDEO_W}:{VIDEO_H}:flags=lanczos,setsar=1,"
            f"tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration}[base];"
        )
        insert_inputs = []
        if args.resources_raw:
            if not args.resources_raw.is_file():
                raise FileNotFoundError(args.resources_raw)
            if not (0 <= args.resources_start < args.resources_end < duration):
                raise ValueError("Resource insert must be inside the video duration.")
            if args.resources_offset < 0 or not math.isfinite(args.resources_offset):
                raise ValueError("Resource offset must be finite and nonnegative.")
            insert_duration = args.resources_end - args.resources_start
            insert_inputs = ["-i", str(args.resources_raw.resolve())]
            stage_filters += (
                "[base]split=2[before][after];"
                f"[before]trim=end={args.resources_start},setpts=PTS-STARTPTS[pre];"
                f"[after]trim=start={args.resources_end},setpts=PTS-STARTPTS[post];"
                f"[4:v]trim=start={args.resources_offset}:duration={insert_duration},"
                f"setpts=PTS-STARTPTS,fps={FPS},"
                f"scale={VIDEO_W}:{VIDEO_H}:flags=lanczos,setsar=1,"
                f"tpad=stop_mode=clone:stop_duration={insert_duration},"
                f"trim=duration={insert_duration}[insert];"
                "[pre][insert][post]concat=n=3:v=1:a=0[stage];"
            )
        else:
            stage_filters += "[base]null[stage];"
        filters = stage_filters + (
            f"[stage]pad={WIDTH}:{HEIGHT}:{VIDEO_X}:{VIDEO_Y}:color={CREAM}[video];"
            "[video][2:v]overlay=0:0:format=auto[framed];"
            "[framed]ass=filename=chapters.ass:fontsdir=fonts[labeled];"
            f"[labeled][3:v]overlay=x='-W+W*min(t/{duration},1)':"
            f"y={HEIGHT - 5}:eval=frame:shortest=1,format=yuv420p[outv];"
            f"[1:a]asetpts=PTS-STARTPTS,apad,atrim=duration={duration}[outa]"
        )
        command = [
            ffmpeg, "-hide_banner", "-y", "-filter_complex_threads", "2",
            "-i", str(args.raw.resolve()), "-i", str(args.audio.resolve()),
            "-loop", "1", "-framerate", str(FPS), "-i", "frame.png",
            "-f", "lavfi", "-i", f"color=c={AMBER}:s={WIDTH}x6:r={FPS}",
            *insert_inputs,
            "-filter_complex", filters, "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-frames:v", str(round(duration * FPS)),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-t", f"{duration:.6f}", "-movflags", "+faststart",
            "-metadata", "title=Lamplight | It never says yes or no. You do.",
            "-metadata", "comment=Prototype demonstration. Fictional patients. Optional English and Spanish caption files.",
            str(args.output.resolve()),
        ]
        print(f"Rendering {duration:g}s / {round(duration * FPS)} frames -> {args.output}", flush=True)
        run(command, cwd=stage)
    cover_path = args.cover or args.output.with_name(f"{args.output.stem}-cover.png")
    cover_path.parent.mkdir(parents=True, exist_ok=True)
    cover_time = max(0, min(args.cover_time, duration - 1 / FPS))
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(cover_time),
         "-i", str(args.output.resolve()), "-frames:v", "1", "-update", "1",
         str(cover_path.resolve())])
    print(f"Video: {args.output.resolve()}\nCover: {cover_path.resolve()}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--resources-raw", type=Path,
                        help="Optional separately recorded client-resource PDF workflow.")
    parser.add_argument("--resources-offset", type=float, default=0)
    parser.add_argument("--resources-start", type=float, default=68.5)
    parser.add_argument("--resources-end", type=float, default=77.5)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--font", type=Path,
                        default=None)
    parser.add_argument("--font-bold", type=Path,
                        default=None)
    parser.add_argument("--brand-logo", type=Path,
                        default=Path(__file__).resolve().parents[2] / "campaign" / "logo" / "lamplight-logo-1024.png")
    parser.add_argument("--cover", type=Path)
    parser.add_argument("--cover-time", type=float, default=24)
    parser.add_argument("--video-offset", type=float, default=0,
                        help="Trim startup seconds from the recording before aligning it to narration.")
    parser.add_argument("--duration", type=float, default=120,
                        help="Default 120. Shorter values are useful for compositor QA.")
    parser.add_argument("--preset", default="fast")
    parser.add_argument("--crf", type=int, default=18)
    args = parser.parse_args()
    args.font = args.font or args.scratch / "lamplight-public-sans.ttf"
    args.font_bold = args.font_bold or args.scratch / "lamplight-public-sans-bold.ttf"
    try:
        render(args)
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
