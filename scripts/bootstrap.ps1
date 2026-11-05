$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$JasnaCommit = "3073dd4"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/ and run this script again."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required. Install Git for Windows and run this script again."
}

$Vendor = Join-Path $Root "vendor\jasna"
if (-not (Test-Path -LiteralPath (Join-Path $Vendor "pyproject.toml"))) {
    if (Test-Path -LiteralPath $Vendor) {
        throw "vendor\jasna exists but is not a Jasna checkout. Move it away first."
    }
    Write-Host "Cloning Jasna..."
    git clone https://github.com/Kruk2/jasna.git $Vendor
    if ($LASTEXITCODE -ne 0) { throw "Cloning Jasna failed with exit code $LASTEXITCODE." }
    git -C $Vendor checkout $JasnaCommit
    if ($LASTEXITCODE -ne 0) { throw "Checking out Jasna $JasnaCommit failed with exit code $LASTEXITCODE." }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating Python 3.13 virtual environment..."
    uv venv --python 3.13 (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Creating the virtual environment failed with exit code $LASTEXITCODE." }
}

Write-Host "Installing CUDA PyTorch..."
uv pip install --python $Python `
    "torch==2.12.1+cu130" "torchvision==0.27.1+cu130" `
    --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw "Installing PyTorch failed with exit code $LASTEXITCODE." }

Write-Host "Installing Jasna and desktop dependencies..."
uv pip install --python $Python -e $Vendor
if ($LASTEXITCODE -ne 0) { throw "Installing Jasna failed with exit code $LASTEXITCODE." }
uv pip install --python $Python `
    "tensorrt==10.16.1.11" "torch-tensorrt==2.12.0+cu130" scipy `
    --extra-index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw "Installing TensorRT failed with exit code $LASTEXITCODE." }

Write-Host "Downloading model weights..."
& $Python (Join-Path $Root "scripts\download_models.py")
if ($LASTEXITCODE -ne 0) { throw "Downloading model weights failed with exit code $LASTEXITCODE." }

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Run: $Root\run.bat"
Write-Host "First scan may compile the TensorRT detector and take a few minutes."
