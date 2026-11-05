# Third-party notices

VideoRefiner Studio is an AGPL-3.0 desktop front end built on the public
Jasna source tree (`vendor/jasna`, not modified). The following components are
used at runtime.

| Component | Version | License | Source |
| --- | --- | --- | --- |
| Jasna | 0.12.0 (commit 3073dd4) | AGPL-3.0-only | https://github.com/Kruk2/jasna |
| Lada models | BasicVSR++ v1.2, YOLO v4 | AGPL-3.0 | https://codeberg.org/ladaapp/lada |
| RF-DETR | 1.8.3 architecture; optional v6 large ONNX | Apache-2.0 | https://github.com/roboflow/rf-detr |
| PyAV | 18.1.0 | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| FFmpeg | 9.0 (system) | LGPL/GPL depending on build | https://ffmpeg.org |
| PyTorch | 2.12.1+cu130 | BSD-3-Clause | https://pytorch.org |
| TensorRT | 10.16.1.11 | NVIDIA license | https://developer.nvidia.com/tensorrt |
| torch-tensorrt | 2.12.0+cu130 | BSD-3-Clause | https://github.com/pytorch/TensorRT |
| Ultralytics | 8.4.192 | AGPL-3.0 | https://github.com/ultralytics/ultralytics |
| CustomTkinter | 6.0.0 | MIT | https://github.com/TomSchimansky/CustomTkinter |
| python-vlc | 3.0.21203 | LGPL-2.1 | https://github.com/oaubert/python-vlc |
| OpenCV | 4.14.0.94 | Apache-2.0 | https://github.com/opencv/opencv-python |
| Pillow | 13.0.0 | MIT-CMU | https://python-pillow.org |
| NumPy | 2.5.4 | BSD-3-Clause | https://numpy.org |
| SciPy | 1.18.1 | BSD-3-Clause | https://scipy.org |

Jasna's own detailed notices, including the OpenMMLab MMagic subset, LTX-2.x
Community License and SageAttention notices, are retained unmodified under
`vendor/jasna/`.

The application processes video locally. It contains no telemetry, paid API
calls, or cloud upload path.
