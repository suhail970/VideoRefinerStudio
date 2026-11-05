import logging
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)

import torch

from jasna.accelerator import vendor_for_device
from jasna.media.encoder_settings import encoder_cq_spec
from jasna.session_config import SessionConfig
from jasna.session_factory import build_pipeline, build_restoration_session


def main() -> None:
    video = Path("test_input/audio_clip.mp4")
    out = Path("test_output/audio_clip_restored.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    device = "cuda:0"
    codec = "h264"
    vendor = vendor_for_device(device)
    cq = encoder_cq_spec(codec, vendor).default
    config = SessionConfig(
        device=device,
        fp16=True,
        batch_size=4,
        detection_model_name="lada-yolo-v4",
        detection_model_path=Path("model_weights/lada_mosaic_detection_model_v4_fast.pt"),
        detection_score_threshold=0.25,
        max_detection_gap=2,
        min_detection_duration=2,
        scene_detection=True,
        restoration_model_name="basicvsrpp",
        restoration_model_path=Path("model_weights/lada_mosaic_restoration_model_generic_v1.2.pth"),
        ltx_large_canvas=False,
        ltx_window_hop=8,
        ltx_seed=20260923,
        ltx_fast=False,
        ltx_model="distilled2",
        ltx_trial=False,
        ltx_auto_split_percent=None,
        compile_basicvsrpp=False,
        max_clip_size=60,
        temporal_overlap=10,
        enable_crossfade=True,
        denoise_strength="none",
        denoise_step="after_primary",
        secondary_restoration="none",
        tvai_ffmpeg_path="",
        tvai_model="",
        tvai_scale=2,
        tvai_args="",
        tvai_workers=1,
        tvai_denoise=False,
        rtx_scale=2,
        rtx_quality="medium",
        rtx_denoise="none",
        rtx_deblur="none",
        vr_mode="auto",
        vr_projection="auto",
        codec=codec,
        encoder_settings={"cq": cq},
        lut_path=None,
        sharpen_strength=0.0,
        retarget_high_fps=False,
        fmp4=False,
        disable_progress=True,
        working_dir=None,
    )
    t0 = time.time()
    session = build_restoration_session(config, log_callback=lambda m: print("BUILD:", m, flush=True))
    print("session built in", round(time.time() - t0, 1), "s", flush=True)
    last = [0.0]

    def progress(percent, fps, eta, done, total, stage):
        if percent - last[0] >= 5 or percent >= 100:
            last[0] = percent
            print(
                f"progress {percent:5.1f}% fps={fps:.1f} eta={eta:.0f}s {done}/{total} stage={stage}",
                flush=True,
            )

    try:
        pipeline = build_pipeline(
            config, session, video, out, progress_callback=progress, segments=None
        )
        t0 = time.time()
        pipeline.run()
        print("pipeline finished in", round(time.time() - t0, 1), "s", flush=True)
        print("output exists", out.exists(), out.stat().st_size if out.exists() else 0, flush=True)
        free, total = torch.cuda.mem_get_info()
        print("vram used", round((total - free) / 1024**3, 2), "GiB", flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
