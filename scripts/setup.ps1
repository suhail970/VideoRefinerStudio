<#
.SYNOPSIS
    Preflight and one-time setup for sharing VideoRefiner Studio.

.DESCRIPTION
    Checks Windows, the NVIDIA driver, VRAM, and free disk space. Installs
    uv, Git, and FFmpeg with winget when missing, then runs bootstrap.ps1
    and verifies the resulting environment.

.PARAMETER CheckOnly
    Run preflight checks only. Do not install anything.

.PARAMETER NoLaunch
    Do not offer to launch the app after setup.

.PARAMETER NoShortcut
    Do not offer to create a desktop shortcut.

.EXAMPLE
    .\setup.bat -CheckOnly

.EXAMPLE
    .\setup.bat
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoLaunch,
    [switch]$NoShortcut
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "  OK   $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  WARN $Message" -ForegroundColor Yellow
}

function Fail {
    param([string]$Message)
    throw $Message
}

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $extra = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"),
        (Join-Path $env:USERPROFILE ".local\bin"),
        (Join-Path $env:ProgramFiles "Git\cmd")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $env:Path = (@($machinePath, $userPath) + $extra | Where-Object { $_ }) -join ";"
}

function Find-Tool {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\$Name.exe"),
        (Join-Path $env:USERPROFILE ".local\bin\$Name.exe"),
        (Join-Path $env:ProgramFiles "Git\cmd\$Name.exe"),
        (Join-Path $env:ProgramFiles "NVIDIA Corporation\NVSMI\$Name.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Add-ToolToPath {
    param([string]$Path)

    if (-not $Path) {
        return
    }
    $directory = Split-Path -Parent $Path
    if (-not $directory) {
        return
    }
    $parts = $env:Path -split ";"
    if ($parts -notcontains $directory) {
        $env:Path = "$directory;$env:Path"
    }
}

function Invoke-Preflight {
    Write-Step "Checking Windows"
    if (-not [Environment]::Is64BitOperatingSystem) {
        Fail "64-bit Windows is required."
    }
    if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
        Fail "This build requires 64-bit Windows on AMD64. ARM64 is not supported."
    }
    $os = [Environment]::OSVersion.Version
    if ($os.Major -lt 10) {
        Fail "Windows 10 or Windows 11 is required."
    }
    Write-Ok "Windows $($os.Major).$($os.Minor) build $($os.Build), AMD64"

    Write-Step "Checking NVIDIA GPU"
    $smi = Find-Tool "nvidia-smi"
    if (-not $smi) {
        Fail "nvidia-smi was not found. Install or update the NVIDIA driver, then run setup again."
    }
    Add-ToolToPath $smi

    $rows = & $smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $rows) {
        Fail "nvidia-smi could not read a GPU. Update the NVIDIA driver and try again."
    }

    $first = @($rows)[0]
    $parts = @($first -split ",")
    if ($parts.Count -lt 3) {
        Fail "Could not parse nvidia-smi output: $first"
    }

    $gpuName = $parts[0].Trim()
    $driver = $parts[1].Trim()
    $vramMiB = 0.0
    try {
        $vramMiB = [double]::Parse($parts[2].Trim(), [System.Globalization.CultureInfo]::InvariantCulture)
    } catch {
        $vramMiB = 0.0
    }
    $vramGiB = [math]::Round($vramMiB / 1024, 1)

    Write-Ok "GPU: $gpuName"
    Write-Ok "Driver: $driver"
    if ($vramGiB -gt 0) {
        Write-Ok "VRAM: $vramGiB GB"
        if ($vramGiB -lt 5.5) {
            Write-Warn "Less than 6 GB VRAM detected. Long 4K or high-fps jobs may run out of memory."
        }
    }

    $driverMajor = 0
    if ($driver -match "^(\d+)") {
        $driverMajor = [int]$Matches[1]
    }
    if ($driverMajor -gt 0 -and $driverMajor -lt 580) {
        Fail "Driver $driver is too old for the bundled CUDA 13 stack. Update to NVIDIA driver 580 or newer."
    }

    Write-Step "Checking disk space"
    $qualifier = (Split-Path -Qualifier $Root).TrimEnd(':')
    $freeBytes = $null
    $drive = Get-PSDrive -Name $qualifier -ErrorAction SilentlyContinue
    if ($drive) {
        $freeBytes = $drive.Free
    }
    if ($null -eq $freeBytes) {
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($qualifier):'" -ErrorAction SilentlyContinue
        if ($disk) {
            $freeBytes = $disk.FreeSpace
        }
    }
    if ($null -eq $freeBytes) {
        Write-Warn "Could not determine free disk space on $($qualifier):"
    } else {
        $freeGiB = [math]::Round($freeBytes / 1GB, 1)
        if ($freeGiB -lt 10) {
            Fail "Only $freeGiB GB free on $($qualifier):. At least 10 GB is required for the environment and models."
        }
        Write-Ok "Free space: $freeGiB GB on $($qualifier):"
    }
}

function Install-Prerequisite {
    param(
        [string]$Name,
        [string]$WingetId,
        [string]$ManualUrl
    )

    Refresh-Path
    $found = Find-Tool $Name
    if ($found) {
        Add-ToolToPath $found
        Write-Ok "$Name found"
        return
    }

    $winget = Find-Tool "winget"
    if (-not $winget) {
        Fail "$Name is missing and winget is not available. Install it manually: $ManualUrl"
    }

    Write-Step "Installing $Name (one-time)"
    & $winget install --id $WingetId -e --source winget --accept-package-agreements --accept-source-agreements --silent
    $exitCode = $LASTEXITCODE

    Refresh-Path
    $found = Find-Tool $Name
    if (-not $found) {
        Fail "winget could not install $Name (exit code $exitCode). Install it manually: $ManualUrl"
    }
    Add-ToolToPath $found
    Write-Ok "$Name installed"
}

function Invoke-Bootstrap {
    Write-Step "Setting up the Python environment and models"
    Write-Host "  This downloads several GB and can take 10-30 minutes on first run."

    $bootstrap = Join-Path $PSScriptRoot "bootstrap.ps1"
    if (-not (Test-Path -LiteralPath $bootstrap)) {
        Fail "Missing scripts\bootstrap.ps1."
    }
    & $bootstrap
}

function Test-Environment {
    Write-Step "Verifying the environment"
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        Fail "The Python virtual environment was not created."
    }

    & $python -c "import sys, torch, tensorrt, torch_tensorrt, av, customtkinter, jasna; print('Python', sys.version.split()[0]); print('PyTorch', torch.__version__); print('TensorRT', tensorrt.__version__); print('CUDA available', torch.cuda.is_available()); print('GPU', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'); sys.exit(0 if torch.cuda.is_available() else 7)"
    if ($LASTEXITCODE -ne 0) {
        Fail "The environment was installed but the import or CUDA check failed. Update the NVIDIA driver and rerun setup."
    }

    $models = @(
        @{ Name = "Lada mosaic detection model"; Path = "model_weights\lada_mosaic_detection_model_v4_fast.pt" },
        @{ Name = "Lada mosaic restoration model"; Path = "model_weights\lada_mosaic_restoration_model_generic_v1.2.pth" }
    )
    foreach ($model in $models) {
        $fullPath = Join-Path $Root $model.Path
        if (-not (Test-Path -LiteralPath $fullPath)) {
            Fail "Missing model file: $($model.Path)"
        }
        if ((Get-Item -LiteralPath $fullPath).Length -lt 1MB) {
            Fail "Model file looks incomplete: $($model.Path)"
        }
        Write-Ok "$($model.Name) present"
    }
}

function New-DesktopShortcut {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) {
        Write-Warn "Could not find the Desktop folder; skipping shortcut."
        return
    }

    $shortcutPath = Join-Path $desktop "VideoRefiner Studio.lnk"
    $runBat = Join-Path $Root "run.bat"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $runBat
    $shortcut.WorkingDirectory = $Root
    $shortcut.Description = "Launch VideoRefiner Studio"
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,137"
    $shortcut.Save()
    Write-Ok "Desktop shortcut created: $shortcutPath"
}

try {
    Write-Host "VideoRefiner Studio setup" -ForegroundColor White
    Write-Host "Project: $Root"

    Invoke-Preflight

    if ($CheckOnly) {
        Write-Step "Checking local tools"
        foreach ($tool in @("uv", "git", "ffmpeg", "ffprobe")) {
            $found = Find-Tool $tool
            if ($found) {
                Add-ToolToPath $found
                Write-Ok "$tool found"
            } else {
                Write-Warn "$tool is missing; setup will install it."
            }
        }
        $python = Join-Path $Root ".venv\Scripts\python.exe"
        if (Test-Path -LiteralPath $python) {
            Write-Ok "Python environment found"
        } else {
            Write-Warn "Python environment is not set up yet."
        }
        Write-Host ""
        Write-Host "Check complete. Run setup.bat without -CheckOnly to install." -ForegroundColor Green
        exit 0
    }

    Write-Step "Checking required tools"
    Install-Prerequisite -Name "uv" -WingetId "astral-sh.uv" -ManualUrl "https://docs.astral.sh/uv/getting-started/installation/"
    Install-Prerequisite -Name "git" -WingetId "Git.Git" -ManualUrl "https://git-scm.com/download/win"
    Install-Prerequisite -Name "ffmpeg" -WingetId "Gyan.FFmpeg" -ManualUrl "https://www.gyan.dev/ffmpeg/builds/"
    Install-Prerequisite -Name "ffprobe" -WingetId "Gyan.FFmpeg" -ManualUrl "https://www.gyan.dev/ffmpeg/builds/"

    Invoke-Bootstrap
    Test-Environment

    if (-not $NoShortcut) {
        $answer = Read-Host "Create a desktop shortcut? [Y/n]"
        if ($answer -notmatch "^(n|no)$") {
            New-DesktopShortcut
        }
    }

    Write-Host ""
    Write-Host "Setup complete." -ForegroundColor Green
    Write-Host "Launch with: $(Join-Path $Root 'run.bat')"
    Write-Host "First scan may compile the TensorRT detector and take several minutes."

    if (-not $NoLaunch) {
        $answer = Read-Host "Launch VideoRefiner Studio now? [Y/n]"
        if ($answer -notmatch "^(n|no)$") {
            Start-Process -FilePath (Join-Path $Root "run.bat")
        }
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "Setup stopped: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "See SHARING.md for troubleshooting." -ForegroundColor Yellow
    exit 1
}
