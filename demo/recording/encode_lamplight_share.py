"""Make a presentation-friendly 720p copy and decode-check both final videos."""
from pathlib import Path
import argparse
import json
import subprocess
import imageio_ffmpeg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Missing source video: {args.source}")
    if args.source.resolve() == args.output.resolve():
        parser.error("The source and output must be different files.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
                    "-i", str(args.source), "-vf", "scale=1280:720:flags=lanczos",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", "120",
                    "-movflags", "+faststart", str(args.output)], check=True)
    for path, size in ((args.source, (1920, 1080)), (args.output, (1280, 720))):
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path),
                        "-map", "0", "-f", "null", "-"], check=True,
                       stdout=subprocess.DEVNULL)
        frames = imageio_ffmpeg.read_frames(str(path))
        metadata = next(frames)
        frames.close()
        assert metadata["size"] == size, metadata
        assert metadata["duration"] == 120 and metadata["fps"] == 30, metadata
        print(json.dumps({"name": path.name, "bytes": path.stat().st_size,
                          "size": metadata["size"], "fps": metadata["fps"],
                          "duration": metadata["duration"]}), flush=True)


if __name__ == "__main__":
    main()
