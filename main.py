"""Launch VideoRefiner Studio.

Jasna resolves ``model_weights`` relative to the working directory, so this
entry point switches to the project root before the app starts. The app is a
desktop GUI and must be launched with the project virtual environment.
"""

from __future__ import annotations

import ctypes
import importlib.util
import logging
import logging.handlers
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _setup_dpi() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _setup_logging() -> Path:
    from videorefiner.settings import config_dir

    directory = config_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        directory = ROOT
    path = directory / "app.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=2_000_000, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    return path


def main() -> int:
    _setup_dpi()
    os.chdir(ROOT)
    os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    vendor = ROOT / "vendor" / "jasna"
    if vendor.is_dir() and importlib.util.find_spec("jasna") is None:
        sys.path.insert(0, str(vendor))

    log_path = _setup_logging()
    LOGGER = logging.getLogger("videorefiner.main")
    LOGGER.info("Project root: %s", ROOT)
    LOGGER.info("Log file: %s", log_path)

    try:
        from videorefiner.app import VideoRefinerApp

        app = VideoRefinerApp()
        app.mainloop()
    except Exception:
        LOGGER.exception("Fatal error while running VideoRefiner Studio")
        if os.name == "nt":
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "VideoRefiner Studio could not start.\n\n"
                    f"See the log for details:\n{log_path}",
                    "VideoRefiner Studio",
                    0x10,
                )
            except Exception:
                pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
