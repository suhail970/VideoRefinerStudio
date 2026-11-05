# VideoRefiner Studio

A local Windows desktop front end for [Jasna](https://github.com/Kruk2/jasna):
mosaic detection, selected-range restoration with BasicVSR++, before/after
comparison, and safe non-overwriting export.

Everything runs on this computer. There is no telemetry, account system, cloud
upload, or paid API.

## Current status

The application is built and verified in this workspace with:

- Windows, NVIDIA GeForce RTX 3050 6 GB Laptop GPU
- CUDA 13.0, PyTorch 2.12.1+cu130
- TensorRT 10.16.1.11 and torch-tensorrt 2.12.0+cu130
- Jasna 0.12.0 from `vendor/jasna` (pinned, unmodified)
- FFmpeg/ffprobe 9.0 on `PATH`
- CustomTkinter 6.0.0 and PyAV 18.1.0

The three-case UI workflow currently passes:

| Case | Result |
| --- | --- |
| Selected ranges + side-by-side compare | PASS, 10.0 s HEVC output, mean preview difference 2.32 |
| Whole video + audio preservation | PASS, 4.9 s H.264 output with audio |
| Selected ranges + audio preservation | PASS, 10.0 s HEVC output with audio |

## Run it

Double-click `run.bat`, or run:

```powershell
.venv\Scripts\python.exe main.py
```

Logs are written to `%LOCALAPPDATA%\VideoRefinerStudio\app.log`.
The app writes settings to `%LOCALAPPDATA%\VideoRefinerStudio\settings.json`.
Set `VIDEOREFINER_CONFIG_DIR` to use a different settings directory.

## Fresh-machine setup

The easiest path is to double-click `setup.bat`. It checks the Windows version,
NVIDIA driver, VRAM, and free disk space, installs uv, Git, and FFmpeg with
winget when needed, then runs the bootstrap. See `SHARING.md` for the recipient
instructions and troubleshooting.

To check a machine without installing anything:

```bat
setup.bat -CheckOnly
```

Manual prerequisites:

- Windows 10/11 with a current NVIDIA driver (580 or newer for CUDA 13)
- [uv](https://docs.astral.sh/uv/)
- Git for Windows
- FFmpeg and ffprobe on `PATH`
- VLC is optional; the app uses PyAV for preview playback

From PowerShell in this directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

The script clones the pinned Jasna revision, creates `.venv` with Python 3.13,
installs CUDA PyTorch, TensorRT, the desktop dependencies, and the BasicVSR++
restoration plus YOLO detector model files. It deliberately does not install
`python-vali`; the app uses Jasna's PyAV hardware decode backend
(`JASNA_DECODE_BACKEND=pyav-hw`).

After setup, start the app with `run.bat`. The first detection run may compile a
TensorRT engine and take a few minutes; later runs reuse the compiled engine.

## Sharing it

Share the source through a private Git repository or a source zip, and point the
recipient at `setup.bat`. Do not copy `.venv`: it is machine-specific and its
editable Jasna install contains an absolute path. See `SHARING.md` for what to
include, what to exclude, and the recipient troubleshooting steps.

## Using the app

1. Import a video. The header shows the file name, resolution, frame rate,
   duration, codec, and audio status.
2. Choose **Selected ranges** or **Whole video**. Run a scan for selected-range
   work. The scan samples once per second and reports one-second ranges.
3. Select ranges on the timeline or with **Select all**.
4. Adjust detection confidence, clip size, overlap, denoise, and scene
   detection. Lower the confidence if mosaics are missed; raise it for false
   positives.
5. Press **Start restoration** in the status footer.
6. Use **Original**, **Compare**, **Side by side**, and **Wipe** to inspect the
   result. The source and restored outputs are compared at the same timestamp.
7. Use **Output folder** to choose a destination and **View log** for details.

Output naming is automatic and unique. A file is never overwritten, including
the source video.

### Scope and codec rules

- **Selected ranges** smart-renders only the detected ranges and streams
  untouched video from the source. It always keeps the source codec. Only
  H.264, HEVC, and AV1 sources are supported for this mode.
- **Whole video** uses the selected H.264, HEVC, or AV1 codec for a complete
  re-encode.
- The source audio is muxed into the output when audio is present. The
  comparison view does not play audio.

## Tests

Run the end-to-end UI workflow:

```powershell
.venv\Scripts\python.exe scripts\ui_workflow_test.py
```

The test uses an isolated temporary settings directory, opens the real Tk
window, scans, restores selected ranges and whole video, checks audio retention,
checks that the preview changes, exercises the compare/playback UI, and exits
with `PASS`.

Rebuild the workspace screenshot:

```powershell
.venv\Scripts\python.exe scripts\ui_screenshot.py
```

It writes `test_output\ui_workspace.png` and does not touch real user settings.

Validate the model files:

```powershell
.venv\Scripts\python.exe scripts\download_models.py
```

Add `--rfdetr` to fetch the optional RF-DETR v6 large ONNX detector. The default
detector is Lada YOLO v4 fast, which is faster on a 6 GB GPU.

## Project layout

- `main.py` - DPI setup, logging, environment defaults, GUI entry point
- `videorefiner/app.py` - main window, views, settings, compare player, footer
- `videorefiner/widgets.py` - responsive scroll area, cards, timeline, pills
- `videorefiner/engine.py` - scan/restore workers, GPU checks, codec handling
- `videorefiner/media.py` - probing, PyAV frame preview, compare composition
- `videorefiner/settings.py` - JSON settings and config-directory override
- `videorefiner/theme.py` - colors, fonts, and CustomTkinter setup
- `scripts/ui_workflow_test.py` - three-case GUI workflow test
- `scripts/ui_screenshot.py` - reproducible workspace screenshot
- `scripts/download_models.py` - SHA-256 checked model downloads
- `scripts/bootstrap.ps1` - clean-clone setup
- `scripts/setup.ps1` - preflight and sharing setup behind `setup.bat`
- `scripts/make_share_zip.ps1` - builds `dist\VideoRefinerStudio-share.zip`
- `setup.bat` - one-click setup for recipients
- `SHARING.md` - sharing, requirements, and troubleshooting guide
- `vendor/jasna` - pinned upstream source, not committed to this repository
- `model_weights` - local model files, not committed to this repository

## Known limitations

- Windows and NVIDIA only. CPU-only operation is not supported.
- 4K or high-frame-rate sources can exhaust 6 GB of VRAM. Lower **Max clip
  size**, use whole-video H.264, or close other GPU applications.
- The first scan can be slow while TensorRT compiles the detector.
- Audio is preserved in exports but is not previewed in the player.
- There is no signed installer yet. Run from this directory with the provided
  virtual environment.
- LTX, UNet 4x, and SD 1.5 are intentionally not included. This build uses
  BasicVSR++ only.

## Troubleshooting

- **Startup error**: read `%LOCALAPPDATA%\VideoRefinerStudio\app.log`.
- **No CUDA**: confirm the NVIDIA driver is current and that `torch.cuda` is
  available in `.venv`; the System view reports the runtime check.
- **Selected-range button disabled**: the source codec must be H.264, HEVC, or
  AV1, and at least one range must be selected. Otherwise use whole video.
- **VRAM out of memory**: reduce max clip size, close other GPU apps, or use
  whole-video H.264.
- **No preview audio**: expected; audio is decoded and muxed only.
- **Reset settings**: delete `%LOCALAPPDATA%\VideoRefinerStudio\settings.json`.

## Licensing

VideoRefiner Studio is licensed under **AGPL-3.0-only** because it incorporates
Jasna. See `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`. Jasna's own
notices and model provenance are retained under `vendor/jasna/`. If you
distribute the app, provide the corresponding source and retain these notices.
