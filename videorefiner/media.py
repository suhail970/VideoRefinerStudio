"""Local video probing, frame extraction, comparison composition and playback."""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import av
from PIL import Image, ImageDraw

from .theme import C


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration: float
    frames: int
    codec: str
    has_audio: bool
    size_bytes: int

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 16 / 9


def _ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if not exe:
        raise MediaError("ffprobe was not found on PATH. Install FFmpeg 8 or newer.")
    return exe


def probe_video(path: str | Path) -> MediaInfo:
    path = Path(path)
    if not path.is_file():
        raise MediaError(f"File not found: {path}")
    try:
        proc = subprocess.run(
            [
                _ffprobe(),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MediaError(f"Could not run ffprobe: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()
        raise MediaError(f"Not a readable video: {detail or path.name}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("ffprobe returned invalid metadata.") from exc
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("This file has no video stream.")
    if video.get("width", 0) <= 0 or video.get("height", 0) <= 0:
        raise MediaError("The video stream has invalid dimensions.")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/0"
    try:
        num, _, den = fps_text.partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    if not fps or fps <= 0:
        fps = 25.0
    duration = 0.0
    for candidate in (video.get("duration"), (data.get("format") or {}).get("duration")):
        try:
            duration = float(candidate)
        except (TypeError, ValueError):
            continue
        if duration > 0:
            break
    try:
        frames = int(video.get("nb_frames") or 0)
    except (TypeError, ValueError):
        frames = 0
    if frames <= 0 and duration > 0:
        frames = max(1, round(duration * fps))
    return MediaInfo(
        path=path,
        width=int(video["width"]),
        height=int(video["height"]),
        fps=fps,
        duration=duration,
        frames=frames,
        codec=str(video.get("codec_name") or "unknown"),
        has_audio=has_audio,
        size_bytes=int((data.get("format") or {}).get("size") or path.stat().st_size),
    )


def _frame_at(path: Path, seconds: float) -> Image.Image | None:
    with av.open(str(path), metadata_errors="replace") as container:
        if not container.streams.video:
            return None
        stream = container.streams.video[0]
        seconds = max(0.0, float(seconds))
        if seconds > 0.01:
            try:
                container.seek(int(seconds / float(stream.time_base)), stream=stream, backward=True)
            except (av.FFmpegError, ValueError):
                pass
        target = seconds - 0.02
        last = None
        for frame in container.decode(stream):
            last = frame
            if frame.time is not None and frame.time >= target:
                return frame.to_image()
        if last is not None:
            return last.to_image()
    return None


def fit_image(image: Image.Image, width: int, height: int) -> Image.Image:
    width = max(2, int(width))
    height = max(2, int(height))
    scale = min(width / image.width, height / image.height)
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    if size == image.size:
        return image
    return image.resize(size, Image.Resampling.LANCZOS)


def compose_compare(
    original: Image.Image | None,
    restored: Image.Image | None,
    *,
    mode: str,
    wipe: float,
    width: int,
    height: int,
) -> Image.Image | None:
    """Compose a comparison frame. ``mode`` is ``original``, ``side`` or ``wipe``."""
    width = max(16, int(width))
    height = max(16, int(height))
    canvas = Image.new("RGB", (width, height), C.PREVIEW_BG)
    if original is None:
        return None
    if mode == "original" or restored is None:
        fitted = fit_image(original, width, height)
        canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
        return canvas
    if mode == "side":
        gap = 8
        half = (width - gap * 3) // 2
        left = fit_image(original, half, height - gap * 2)
        right = fit_image(restored, half, height - gap * 2)
        canvas.paste(left, (gap + (half - left.width) // 2, (height - left.height) // 2))
        canvas.paste(right, (gap * 2 + half + (half - right.width) // 2, (height - right.height) // 2))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((width // 2, 0, width // 2 + 1, height), fill="#2A2E3A")
        return canvas

    left = fit_image(original, width, height)
    right = fit_image(restored, width, height)
    base = Image.new("RGB", (width, height), C.PREVIEW_BG)
    base.paste(left, ((width - left.width) // 2, (height - left.height) // 2))
    divider = max(2, min(width - 3, int(width * max(0.02, min(0.98, wipe)))))
    if divider < width:
        right_crop = right.crop((divider, 0, right.width, right.height))
        base.paste(right_crop, (divider + (width - right.width) // 2, (height - right.height) // 2))
    draw = ImageDraw.Draw(base)
    draw.rectangle((divider, 0, divider + 1, height), fill="#F8FAFC")
    return base


def load_static_frame(
    original_path: Path,
    restored_path: Path | None,
    seconds: float,
    *,
    mode: str,
    wipe: float,
    width: int,
    height: int,
) -> Image.Image | None:
    original = _frame_at(original_path, seconds)
    restored = None
    if restored_path is not None:
        restored = _frame_at(restored_path, seconds)
    return compose_compare(
        original, restored, mode=mode, wipe=wipe, width=width, height=height
    )


def make_thumbnail(path: Path, seconds: float, width: int = 320) -> Image.Image | None:
    image = _frame_at(path, seconds)
    if image is None:
        return None
    height = max(1, int(width * image.height / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


class PlaybackSession:
    """Decode original and restored frames in lockstep and compose a preview."""

    def __init__(
        self,
        original_path: Path,
        restored_path: Path | None,
        *,
        start: float,
        mode: str,
        wipe: float,
        width: int,
        height: int,
        events: queue.Queue,
    ) -> None:
        self.original_path = Path(original_path)
        self.restored_path = Path(restored_path) if restored_path else None
        self.start_time = max(0.0, float(start))
        self.mode = mode
        self.wipe = float(wipe)
        self.width = max(16, int(width))
        self.height = max(16, int(height))
        self.events = events
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="VideoRefinerPlayback", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        orig_container = None
        restored_container = None
        try:
            orig_container = av.open(str(self.original_path), metadata_errors="replace")
            orig_stream = orig_container.streams.video[0]
            if self.restored_path is not None:
                restored_container = av.open(str(self.restored_path), metadata_errors="replace")
                restored_stream = restored_container.streams.video[0]
            else:
                restored_stream = None

            if self.start_time > 0.02:
                offset = int(self.start_time / float(orig_stream.time_base))
                try:
                    orig_container.seek(offset, stream=orig_stream, backward=True)
                except (av.FFmpegError, ValueError):
                    pass
                if restored_container is not None and restored_stream is not None:
                    r_offset = int(self.start_time / float(restored_stream.time_base))
                    try:
                        restored_container.seek(r_offset, stream=restored_stream, backward=True)
                    except (av.FFmpegError, ValueError):
                        pass

            restored_iter = restored_container.decode(restored_stream) if (
                restored_container is not None and restored_stream is not None
            ) else None
            restored_last = None
            restored_frame = next(restored_iter, None) if restored_iter is not None else None
            wall_start = time.monotonic()
            frame_interval = 1.0 / 30.0
            last_emit = -1.0

            for frame in orig_container.decode(orig_stream):
                if self._stop.is_set():
                    return
                if frame.time is None:
                    continue
                stamp = float(frame.time)
                if stamp < self.start_time - 0.01:
                    continue
                restored = None
                if restored_iter is not None:
                    while restored_frame is not None and restored_frame.time is not None and restored_frame.time < stamp:
                        restored_last = restored_frame
                        restored_frame = next(restored_iter, None)
                    restored = restored_frame if restored_frame is not None else restored_last
                orig_image = frame.to_image()
                restored_image = restored.to_image() if restored is not None else None
                composed = compose_compare(
                    orig_image,
                    restored_image,
                    mode=self.mode,
                    wipe=self.wipe,
                    width=self.width,
                    height=self.height,
                )
                if composed is None:
                    continue
                if stamp - last_emit < frame_interval * 0.9:
                    continue
                last_emit = stamp
                due = max(0.0, stamp - self.start_time)
                now = time.monotonic() - wall_start
                if due > now:
                    wait = due - now
                    if self._stop.wait(min(wait, 0.25)):
                        return
                    while due > time.monotonic() - wall_start + 0.002 and not self._stop.is_set():
                        if self._stop.wait(0.005):
                            return
                try:
                    self.events.put_nowait(("playback_frame", composed, stamp))
                except queue.Full:
                    try:
                        self.events.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self.events.put_nowait(("playback_frame", composed, stamp))
                    except queue.Full:
                        pass
            self.events.put(("playback_end", last_emit))
        except Exception as exc:  # noqa: BLE001 - the UI displays the message
            if not self._stop.is_set():
                self.events.put(("playback_error", str(exc)))
        finally:
            if orig_container is not None:
                orig_container.close()
            if restored_container is not None:
                restored_container.close()
