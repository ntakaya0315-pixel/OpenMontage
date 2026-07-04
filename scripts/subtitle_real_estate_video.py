#!/usr/bin/env python3
"""Create Japanese subtitles and normalize audio for real-estate narration videos.

Usage:
    python scripts/subtitle_real_estate_video.py source_media/input.mp4

The script intentionally uses local tooling only:
- faster-whisper for Japanese transcription
- FFmpeg/ffprobe for subtitle burn-in, loudness normalization, and MP4 export

It does not call paid APIs, paid cloud services, or external generation AI.
The first faster-whisper run may download the selected Whisper model into the
Codespaces cache, but transcription itself runs locally after that download.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "output" / "subtitled_final.mp4"
DEFAULT_GLOSSARY = REPO_ROOT / "glossary" / "real_estate_terms.txt"
DEFAULT_MODEL = "small"

# Common real-estate terms that Whisper may split, spell phonetically, or
# confuse. The glossary is still passed into the transcription prompt; this map
# handles likely subtitle text variants after transcription.
COMMON_CORRECTIONS = {
    "不動産 売却": "不動産売却",
    "不動産ばいきゃく": "不動産売却",
    "媒介 契約": "媒介契約",
    "専属 専任 媒介": "専属専任媒介",
    "専属専任 媒介": "専属専任媒介",
    "専任 媒介": "専任媒介",
    "一般 媒介": "一般媒介",
    "レインズ": "レインズ",
    "REINS": "レインズ",
    "売り主": "売主",
    "買い主": "買主",
    "仲介 手数料": "仲介手数料",
    "重要 事項 説明": "重要事項説明",
    "契約 不適合 責任": "契約不適合責任",
    "住宅 ローン": "住宅ローン",
    "抵当 権": "抵当権",
    "残さい": "残債",
    "引き渡し": "引渡し",
    "司法 書士": "司法書士",
    "固定 資産 税": "固定資産税",
    "修繕 積立 金": "修繕積立金",
    "修繕 積立金": "修繕積立金",
    "戸建て": "戸建",
    "福岡 市": "福岡市",
    "中央 区": "中央区",
    "博多 区": "博多区",
    "早良 区": "早良区",
    "西 区": "西区",
    "南 区": "南区",
    "東 区": "東区",
    "城南 区": "城南区",
}


@dataclass
class Segment:
    start: float
    end: float
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Japanese real-estate subtitle + audio-normalized MP4 exporter."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(REPO_ROOT / "source_media" / "input.mp4"),
        help="Input video path. Use source_media/input.mp4 or source_media/input.mov.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output MP4 path. Defaults to output/subtitled_final.mp4.",
    )
    parser.add_argument(
        "--glossary",
        default=str(DEFAULT_GLOSSARY),
        help="Glossary file used as the transcription prompt and correction reference.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="faster-whisper model size. small is a good Codespaces default.",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=24,
        help="Burned subtitle font size.",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="x264 quality setting. Lower is higher quality/larger file.",
    )
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def ensure_prerequisites() -> None:
    print("Local-only mode: no paid APIs, cloud transcription, or external generation AI will be used.")
    if shutil.which("ffmpeg") is None:
        fail("ffmpeg not found. In Codespaces run: sudo apt-get update && sudo apt-get install -y ffmpeg fonts-noto-cjk")
    if shutil.which("ffprobe") is None:
        fail("ffprobe not found. Install ffmpeg in Codespaces.")
    if importlib.util.find_spec("faster_whisper") is None:
        fail("faster-whisper not found. Run: python -m pip install -r requirements-subtitles.txt")


def validate_input(path: Path) -> None:
    if not path.exists():
        fail(f"Input video not found: {path}")
    if path.suffix.lower() not in {".mp4", ".mov"}:
        fail("Input must be .mp4 or .mov")


def read_glossary_terms(path: Path) -> list[str]:
    if not path.exists():
        return []
    terms: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line == "不動産用語集":
            continue
        term = line.split(":", 1)[0].split("：", 1)[0].strip()
        if term:
            terms.append(term)
    return terms


def build_prompt(terms: list[str]) -> str:
    if not terms:
        return "日本語の不動産売却に関する1人語り動画です。"
    joined = "、".join(terms[:100])
    return f"日本語の不動産売却に関する1人語り動画です。専門用語: {joined}。"


def apply_glossary_corrections(text: str, glossary_terms: list[str]) -> str:
    corrected = text.strip()
    for wrong, right in COMMON_CORRECTIONS.items():
        corrected = corrected.replace(wrong, right)

    # If Whisper inserts spaces inside known glossary terms, remove them.
    compact = corrected.replace(" ", "").replace("　", "")
    for term in glossary_terms:
        spaced = " ".join(term)
        corrected = corrected.replace(spaced, term)
        if term in compact and term not in corrected:
            corrected = corrected.replace(term.replace(" ", ""), term)
    return " ".join(corrected.split())


def wrap_japanese_text(text: str, max_chars: int = 18, max_lines: int = 2) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text

    break_chars = "、。！？!? "
    lines: list[str] = []
    remaining = text
    while remaining and len(lines) < max_lines:
        if len(remaining) <= max_chars or len(lines) == max_lines - 1:
            lines.append(remaining)
            break
        split_at = max(
            remaining.rfind(ch, 0, max_chars + 1) for ch in break_chars
        )
        if split_at <= 0:
            split_at = max_chars
        chunk = remaining[: split_at + 1].strip()
        remaining = remaining[split_at + 1 :].strip()
        if chunk:
            lines.append(chunk)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines and len(lines[-1]) > max_chars * 2:
        # Keep two lines maximum while preventing extreme overflows.
        lines[-1] = lines[-1][: max_chars * 2 - 1] + "…"
    return "\n".join(lines)


def seconds_to_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def transcribe(input_path: Path, model_size: str, prompt: str, terms: list[str]) -> list[Segment]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments_iter, _info = model.transcribe(
        str(input_path),
        language="ja",
        initial_prompt=prompt,
        vad_filter=True,
        beam_size=5,
        word_timestamps=False,
    )

    segments: list[Segment] = []
    for segment in segments_iter:
        text = apply_glossary_corrections(segment.text, terms)
        if text:
            segments.append(Segment(start=segment.start, end=segment.end, text=text))
    return segments


def write_srt(segments: list[Segment], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, 1):
            handle.write(f"{index}\n")
            handle.write(
                f"{seconds_to_srt_timestamp(segment.start)} --> {seconds_to_srt_timestamp(segment.end)}\n"
            )
            handle.write(wrap_japanese_text(segment.text))
            handle.write("\n\n")


def write_transcript_json(segments: list[Segment], path: Path) -> None:
    payload = [segment.__dict__ for segment in segments]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ffmpeg_subtitles_path(path: Path) -> str:
    # FFmpeg subtitles filter treats ':' and '\\' specially. The repository path
    # in Codespaces is POSIX, but this keeps the command resilient.
    escaped = str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return escaped


def render_video(input_path: Path, srt_path: Path, output_path: Path, font_size: int, crf: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subtitle_filter = (
        f"subtitles='{ffmpeg_subtitles_path(srt_path)}':"
        "force_style='FontName=Noto Sans CJK JP,"
        f"FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=36'"
    )
    audio_filter = "dynaudnorm=f=150:g=15:p=0.95:m=10,loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        subtitle_filter,
        "-af",
        audio_filter,
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def run_ffprobe(path: Path) -> None:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size",
        "-of",
        "default=noprint_wrappers=1",
        str(path),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    ensure_prerequisites()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    glossary_path = Path(args.glossary).resolve()
    validate_input(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path = output_path.parent / "subtitles.srt"
    transcript_path = output_path.parent / "transcript.json"

    terms = read_glossary_terms(glossary_path)
    prompt = build_prompt(terms)

    print(f"Transcribing Japanese audio with faster-whisper model={args.model}...")
    segments = transcribe(input_path, args.model, prompt, terms)
    if not segments:
        fail("No speech segments were transcribed.")

    write_srt(segments, srt_path)
    write_transcript_json(segments, transcript_path)
    print(f"Wrote subtitles: {srt_path}")
    print(f"Wrote transcript: {transcript_path}")

    print("Burning subtitles and normalizing audio with FFmpeg...")
    render_video(input_path, srt_path, output_path, args.font_size, args.crf)
    print(f"Wrote final video: {output_path}")
    run_ffprobe(output_path)


if __name__ == "__main__":
    main()
