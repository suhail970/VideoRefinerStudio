import logging
import os
import time
from pathlib import Path

os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

import torch

from jasna.media.probe import get_video_meta_data
from jasna.mosaic.detection_registry import resolve_detection_model
from jasna.mosaic_scan import scan_mosaic_sizes
from jasna.session_factory import build_compiled_detection_model


def main() -> None:
    name = "lada-yolo-v4"
    det_name, det_path, thr = resolve_detection_model(name, "", None)
    print("detector", det_name, det_path, thr, flush=True)
    device = torch.device("cuda:0")
    t0 = time.time()
    det = build_compiled_detection_model(
        det_name,
        det_path,
        device=device,
        batch_size=4,
        fp16=True,
        score_threshold=thr,
        log_callback=lambda m: print("COMPILE:", m, flush=True),
    )
    print("loaded detector in", round(time.time() - t0, 1), "s", flush=True)
    video = Path("vendor/jasna/assets/test_clip1_1080p.mp4")
    meta = get_video_meta_data(str(video))
    print(
        "meta",
        meta.video_width,
        meta.video_height,
        meta.video_fps,
        meta.duration,
        meta.num_frames,
        flush=True,
    )
    t0 = time.time()
    samples = scan_mosaic_sizes(
        det,
        video,
        meta,
        batch_size=4,
        device=device,
        disable_progress=True,
        on_progress=lambda f: None,
    )
    print("scan in", round(time.time() - t0, 1), "s", "samples", len(samples.times), flush=True)
    for t, s, z in zip(samples.times, samples.scores, samples.sizes):
        print(f"t={t:.2f} score={s:.3f} size={z:.3f}", flush=True)
    det.close()


if __name__ == "__main__":
    main()
