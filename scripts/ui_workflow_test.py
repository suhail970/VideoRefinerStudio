"""End-to-end test of the desktop app's wiring, without manual clicks.

Run with the project venv from the project root:
    .venv\\Scripts\\python.exe scripts\\ui_workflow_test.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")
sys.path.insert(0, str(ROOT))

from videorefiner import app as app_module  # noqa: E402
from videorefiner import media  # noqa: E402
from videorefiner.app import VideoRefinerApp  # noqa: E402

app_module.messagebox.showerror = lambda *a, **k: print("MESSAGEBOX ERROR:", a[1] if len(a) > 1 else a)
app_module.messagebox.showwarning = lambda *a, **k: print("MESSAGEBOX WARNING:", a[1] if len(a) > 1 else a)
app_module.messagebox.askyesno = lambda *a, **k: True


def pump(app, seconds: float = 0.05) -> None:
    app.update()
    time.sleep(seconds)
    app.update()


def wait_for(app, predicate, timeout: float, label: str):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pump(app)
        if predicate():
            return True
    print(f"TIMEOUT waiting for {label}")
    return False


def run_case(app, video: Path, *, scope: str, label: str, expect_change: bool = False) -> Path | None:
    print(f"\n== {label}: {video}")
    app._load_video(video)
    pump(app)
    assert app.media is not None, "video did not load"
    print(
        "media:",
        app.media.width,
        app.media.height,
        round(app.media.fps, 2),
        round(app.media.duration, 2),
        app.media.codec,
        "audio" if app.media.has_audio else "no-audio",
    )
    assert video.name in app._header_sub.cget("text"), "workspace header lost file metadata"
    app.settings.scope = scope
    app.scope_seg.set("Selected ranges" if scope == "selected" else "Whole video")
    app._update_restore_summary()
    app._update_start_state()
    assert app.start_btn.winfo_ismapped(), "start button is not visible"

    if scope == "selected":
        app._start_scan()
        assert wait_for(app, lambda: app._scan_worker is None, 900, "mosaic scan"), "scan timeout"
        assert app.scan is not None, "scan result missing"
        assert app.scan_segments, "no mosaic ranges found"
        print(
            "scan:",
            len(app.scan.times),
            "samples,",
            len(app.scan_segments),
            "ranges, threshold",
            app.settings.threshold,
        )
        app._select_all()
        assert app.selected_ranges, "no selected ranges"
        assert app.start_btn.cget("state") == "normal", "start button stayed disabled"
    else:
        print("scan skipped (whole-video scope)")
        assert app.start_btn.cget("state") == "normal", "start button stayed disabled"

    started = time.monotonic()
    app._start_restore()
    assert app._restore_worker is not None, "restore worker did not start"
    ok = wait_for(app, lambda: app._restore_worker is None, 1800, "restoration")
    elapsed = time.monotonic() - started
    assert ok, "restoration timeout"
    assert app.output_path is not None, "restoration did not produce an output path"
    assert Path(app.output_path).is_file(), "output file missing"
    print("restore:", elapsed, "s ->", app.output_path, Path(app.output_path).stat().st_size, "bytes")
    info = media.probe_video(Path(app.output_path))
    print(
        "output meta:",
        info.width,
        info.height,
        round(info.duration, 2),
        info.codec,
        "audio" if info.has_audio else "no-audio",
    )
    assert info.duration > 0
    if app.media.has_audio:
        assert info.has_audio, "audio was not preserved"
    if expect_change:
        from PIL import ImageChops, ImageStat

        at = min(2.0, info.duration / 2)
        original_frame = media.load_static_frame(
            app.media.path, None, at, mode="original", wipe=0.5, width=320, height=180
        )
        restored_frame = media.load_static_frame(
            Path(app.output_path), None, at, mode="original", wipe=0.5, width=320, height=180
        )
        diff = ImageStat.Stat(ImageChops.difference(original_frame, restored_frame)).mean
        mean_diff = round(sum(diff) / 3, 2)
        print("mean preview difference:", mean_diff)
        assert mean_diff > 0.5, "restored frames look identical to the source"
    print("status:", app.status_title.cget("text"), "|", app.status_detail.cget("text"))

    app._show_compare(True)
    pump(app, 2.0)
    print("compare mode:", app.compare, app.compare_mode, "pill:", app._preview_pill.cget("text"))
    app._start_playback(min(1.0, max(0.0, info.duration / 2)))
    pump(app, 2.5)
    print("playback time:", round(app._last_play_time, 2), "playing:", app._playing)
    app._stop_playback()
    return Path(app.output_path)


def main() -> int:
    config = Path(tempfile.mkdtemp(prefix="videorefiner-test-"))
    os.environ["VIDEOREFINER_CONFIG_DIR"] = str(config)
    print("test config:", config)
    app = VideoRefinerApp()
    app.update()
    app.settings.output_dir = str(ROOT / "test_output" / "ui_test")
    app.settings.suffix = "_ui_restored"
    app.settings.threshold = 0.35
    app.settings.scope = "selected"
    try:
        run_case(
            app,
            ROOT / "vendor" / "jasna" / "assets" / "test_clip1_1080p.mp4",
            scope="selected",
            label="selected ranges + compare",
            expect_change=True,
        )
        run_case(
            app,
            ROOT / "test_input" / "audio_clip.mp4",
            scope="whole",
            label="whole video + audio preservation",
        )
        run_case(
            app,
            ROOT / "test_input" / "mosaic_audio_clip.mp4",
            scope="selected",
            label="selected ranges + audio preservation",
            expect_change=True,
        )
        app.deiconify()
        pump(app, 0.5)
        shot = ROOT / "test_output" / "ui_workspace.png"
        app.update_idletasks()
        print("\nUI is live; closing test window in 3 seconds.")
        pump(app, 3.0)
        print("PASS")
        return 0
    except Exception:
        traceback.print_exc()
        print("\n--- log tail ---")
        for stamp, level, line in app._log_lines[-80:]:
            print(f"[{stamp}] {level:<7} {line}")
        return 1
    finally:
        try:
            app.settings.save()
            app.destroy()
        except Exception:
            pass
        shutil.rmtree(config, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
