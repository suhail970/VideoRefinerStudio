import os
import time

os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")

import torch

from jasna.restorer.basicvsrpp_mosaic_restorer import BasicvsrppMosaicRestorer


def main() -> None:
    device = torch.device("cuda:0")
    t0 = time.time()
    restorer = BasicvsrppMosaicRestorer(
        checkpoint_path="model_weights/lada_mosaic_restoration_model_generic_v1.2.pth",
        device=device,
        max_clip_size=60,
        use_tensorrt=False,
        fp16=True,
    )
    print("loaded basicvsrpp in", round(time.time() - t0, 1), "s", flush=True)
    frames = [torch.randint(0, 256, (3, 256, 256), dtype=torch.uint8) for _ in range(8)]
    t0 = time.time()
    out = restorer.raw_process(frames)
    torch.cuda.synchronize()
    print("forward", tuple(out.shape), out.dtype, "in", round(time.time() - t0, 2), "s", flush=True)
    free, total = torch.cuda.mem_get_info()
    print("vram used", round((total - free) / 1024**3, 2), "GiB of", round(total / 1024**3, 2), flush=True)
    restorer.close()


if __name__ == "__main__":
    main()
