"""Render the workspace with a finished comparison and save a screenshot."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab  # noqa: E402

import main as launcher  # noqa: E402
from videorefiner.app import VideoRefinerApp  # noqa: E402


def main() -> int:
    config = Path(tempfile.mkdtemp(prefix="videorefiner-shot-"))
    os.environ["VIDEOREFINER_CONFIG_DIR"] = str(config)
    launcher._setup_dpi()
    app = VideoRefinerApp()
    app.update()
    source = ROOT / "test_input" / "mosaic_audio_clip.mp4"
    restored = ROOT / "test_output" / "ui_test" / "mosaic_audio_clip_ui_restored.mp4"
    if not restored.is_file():
        restored = ROOT / "test_output" / "ui_test" / "test_clip1_1080p_ui_restored.mp4"
    app._load_video(source)
    app.settings.scope = "selected"
    app.scope_seg.set("Selected ranges")
    app._sync_codec_controls()
    app._start_scan()
    deadline = time.monotonic() + 120
    while app._scan_worker is not None and time.monotonic() < deadline:
        app.update()
        time.sleep(0.05)
    app._select_all()
    app.output_path = restored
    app._set_status(
        "success",
        "Restoration complete",
        f"Saved {restored.name}. Compare the result with the source.",
    )
    app.progress.set(100)
    app.status_stats.configure(text="10.0s  ·  30.0 fps  ·  0:10  ·  2.4 GB VRAM")
    app._show_compare(True)
    for _ in range(60):
        app.update()
        time.sleep(0.05)
    app.update_idletasks()
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    w = app.winfo_width()
    h = app.winfo_height()
    shot = ROOT / "test_output" / "ui_workspace.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(shot)
    print(f"saved {shot} ({w}x{h} at {x},{y})")
    app.destroy()
    shutil.rmtree(config, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
