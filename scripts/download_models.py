"""Download the model files used by VideoRefiner Studio, with SHA-256 checks."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "model_weights"

FILES = {
    "lada_mosaic_restoration_model_generic_v1.2.pth": (
        "https://huggingface.co/ladaapp/lada/resolve/"
        "3bfd69ffc21518bde80ba6b61696d51efd0a398b/"
        "lada_mosaic_restoration_model_generic_v1.2.pth",
        "d404152576ce64fb5b2f315c03062709dac4f5f8548934866cd01c823c8104ee",
    ),
    "lada_mosaic_detection_model_v4_fast.pt": (
        "https://huggingface.co/ladaapp/lada/resolve/"
        "404620fe2f6b72657b92f76e62af914c8b3ee686/"
        "lada_mosaic_detection_model_v4_fast.pt",
        "9a6b660d1d3e3797d39515e08b0e72fcc59815f38279faa7a4ab374ab2c1e3b4",
    ),
}

OPTIONAL_FILES = {
    "rfdetr-v6-large.onnx": (
        "https://github.com/Kruk2/jasna/releases/download/0.1/rfdetr-v6-large.onnx",
        "e8c1af4b1d7be2b99ef21325a8140b7bea15132df0b25cd30d32128bcd8cd644",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(name: str, url: str, expected: str) -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    destination = TARGET / name
    if destination.is_file() and sha256(destination) == expected:
        print(f"ok      {name}")
        return

    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    print(f"fetch   {name}")
    request = urllib.request.Request(url, headers={"User-Agent": "VideoRefiner-Studio/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            handle.write(block)
            done += len(block)
            if total:
                print(f"\r        {done * 100 // total:3d}%", end="", flush=True)
    print()

    actual = sha256(partial)
    if actual != expected:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"checksum mismatch for {name}: {actual}")
    shutil.move(str(partial), str(destination))
    print(f"saved   {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rfdetr",
        action="store_true",
        help="also download the optional RF-DETR v6 large ONNX detector",
    )
    args = parser.parse_args()

    for name, (url, expected) in FILES.items():
        download(name, url, expected)
    if args.rfdetr:
        for name, (url, expected) in OPTIONAL_FILES.items():
            download(name, url, expected)
    print(f"models ready in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
