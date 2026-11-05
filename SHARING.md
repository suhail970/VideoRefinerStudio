# Sharing VideoRefiner Studio

This guide is for handing the app to someone else without building a public
installer. The recommended path is to share the source folder and let the
recipient run `setup.bat` once.

## Recipient requirements

- Windows 10 or Windows 11, 64-bit (AMD64)
- A recent NVIDIA GPU (RTX 20 series or newer recommended)
- NVIDIA driver 580 or newer, for the CUDA 13 build
- 6 GB of VRAM recommended; 4 GB cards may need a smaller max clip size
- At least 10 GB of free disk space on the drive containing the project
  (15 GB recommended)
- Internet access for the first setup
- No Python installation is required; setup creates a local `.venv`

This app does not support CPU-only operation, AMD GPUs, macOS, or ARM64
Windows. There is no cloud fallback.

## Quick start for recipients

1. Copy or clone the project folder to a local drive. Do not copy someone
   else's `.venv` folder.
2. Double-click `setup.bat`.
3. Approve any winget prompts for uv, Git, or FFmpeg.
4. Wait while Python, CUDA PyTorch, TensorRT, Jasna, and the model files are
   downloaded. The first setup can take 10-30 minutes and several GB.
5. When setup finishes, allow it to create a desktop shortcut and launch the
   app, or run `run.bat` later.

The first detection run may compile the TensorRT engine and take a few minutes.
Later runs reuse the compiled engine.

### Check the machine without installing

```bat
setup.bat -CheckOnly
```

This checks Windows, the NVIDIA driver, VRAM, and free disk space, and reports
which tools are already installed. It does not install or download anything.

### Skip prompts

```bat
setup.bat -NoShortcut -NoLaunch
```

## What setup.bat does

- Checks Windows version and architecture
- Checks `nvidia-smi`, the driver version, GPU memory, and free disk space
- Installs `uv`, Git, and FFmpeg with winget if they are missing
- Runs `scripts\bootstrap.ps1` to:
  - clone the pinned Jasna revision into `vendor\jasna`
  - create `.venv` with Python 3.13
  - install CUDA PyTorch, TensorRT, torch-tensorrt, and desktop dependencies
  - download and SHA-256 check the model weights
- Verifies that the environment imports and that PyTorch can see the GPU
- Optionally creates a desktop shortcut

Setup does not install VLC. Preview playback uses PyAV.

## Where data lives

- Settings: `%LOCALAPPDATA%\VideoRefinerStudio\settings.json`
- Logs: `%LOCALAPPDATA%\VideoRefinerStudio\app.log`
- Models: `model_weights\` inside the project
- TensorRT engine cache: `model_weights\` and the user cache directory
- Outputs: the source folder by default, or the folder selected in the app

Set `VIDEOREFINER_CONFIG_DIR` to use a different settings directory. Delete the
settings file to reset the app.

## Troubleshooting for recipients

**`nvidia-smi` was not found or the driver is too old**

Install or update the NVIDIA driver from NVIDIA's driver page or the NVIDIA
app, then run `setup.bat` again. The CUDA 13 build requires driver 580 or newer.

**winget is not available**

Install **App Installer** from the Microsoft Store, then rerun `setup.bat`. If
you cannot use winget, install these manually and rerun setup:

- uv: https://docs.astral.sh/uv/getting-started/installation/
- Git for Windows: https://git-scm.com/download/win
- FFmpeg (Gyan build): https://www.gyan.dev/ffmpeg/builds/

**Only X GB free**

The environment and models need about 10 GB. Free space on the drive that
contains the project, or move the project to a drive with more room.

**CUDA is not available**

Update the NVIDIA driver, reboot if prompted, close other GPU applications, and
run `setup.bat -CheckOnly`. The setup verification must print
`CUDA available True`.

**The app is very slow on the first scan**

TensorRT is compiling the detector. This is expected. Later scans reuse the
compiled engine.

**Out of VRAM on 4K or high-frame-rate video**

Lower **Max clip size**, close other GPU applications, or use whole-video
H.264. A 6 GB laptop GPU is the tested configuration.

**Setup failed partway through**

Read the last error, then rerun `setup.bat`. To run the underlying setup
manually:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

The app log is at `%LOCALAPPDATA%\VideoRefinerStudio\app.log`.

**Windows SmartScreen or antivirus warns about the app**

The app is not code-signed. Only run it from a source you trust. If you are
sharing it, tell recipients why the warning appears.

## For the person sharing the project

Recommended: use a private GitHub repository, or send a source zip. To build a
source zip automatically:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\make_share_zip.ps1
```

The script writes `dist\VideoRefinerStudio-share.zip` and excludes `.venv`,
`vendor`, `model_weights`, test data, caches, and logs. It includes the docs,
screenshots, setup scripts, and license notices.

Include these files:

- `setup.bat`
- `SHARING.md`
- `README.md`
- `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`
- `videorefiner\`, `scripts\`, `docs\`, `resources\`, and `main.py`
- `run.bat`

Do **not** include:

- `.venv\` - it is machine-specific. The editable Jasna install contains an
  absolute path such as `D:\Xcoder\VideoRefinerStudio\vendor\jasna`, so copying
  it to another path or computer breaks the Jasna import.
- `vendor\jasna\` - setup clones the pinned revision. Keeping it out also keeps
  the shared folder small.
- `model_weights\` - setup downloads and checks the models. Bundling them makes
  the upload much larger.
- `test_input\`, `test_output\`, and `.log` files - these are local test data.
- `%LOCALAPPDATA%\VideoRefinerStudio\` - these are personal settings and logs,
  and may contain file paths.

The repository `.gitignore` already excludes the large local folders. A source
zip is typically tens of MB; a full installed copy is several GB. GitHub release
assets have upload limits, so avoid uploading a packaged environment unless you
have tested it on a clean machine.

If you need a single-folder app for non-technical users, build a packaged app
separately with PyInstaller or Nuitka. Do not ship the development `.venv`.

## Updating recipients

If they have a Git checkout:

```powershell
git pull
setup.bat
```

If they received a zip, replace the source files with the new versions, keep
their `.venv` and models if compatible, and rerun `setup.bat`. A clean reinstall
is safer when Python or CUDA dependencies change.

## Licensing and privacy

VideoRefiner Studio is AGPL-3.0-only because it incorporates Jasna. Keep
`LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md` with every copy. If you
distribute a binary, provide the corresponding source and retain all notices.
The setup script downloads models from their upstream sources and verifies
their SHA-256 hashes.

The app runs locally and has no telemetry, accounts, or cloud upload. Logs can
contain local file paths, so do not post them publicly without review.
