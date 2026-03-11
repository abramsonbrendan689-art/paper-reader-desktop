param(
    [switch]$SkipDependencyCheck,
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
$RequirementsFile = Join-Path $ProjectRoot "requirements.txt"
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExampleFile = Join-Path $ProjectRoot ".env.example"
$StampFile = Join-Path $VenvDir ".requirements.sha256"

function Get-BootstrapPython {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "No usable Python was found. Please install Python 3.12 or 3.13 first."
}

function New-ProjectVenv {
    if (Test-Path $VenvPython) {
        Write-Host "[launch] Reusing existing virtual environment: $VenvDir"
        return
    }

    Write-Host "[launch] .venv was not found. Creating a new virtual environment..."
    $bootstrap = Get-BootstrapPython
    & $bootstrap[0] -m venv $VenvDir
}

function Ensure-ProjectEnvFile {
    if (Test-Path $EnvFile) {
        return
    }

    if (Test-Path $EnvExampleFile) {
        Copy-Item $EnvExampleFile $EnvFile
        Write-Host "[launch] Created .env from .env.example"
        return
    }

    Set-Content -Path $EnvFile -Value "DEFAULT_PROVIDER=deepseek`r`nDEEPSEEK_API_KEY=`r`n" -Encoding UTF8
    Write-Host "[launch] Created a minimal .env file"
}

function Activate-ProjectVenv {
    if (-not (Test-Path $ActivateScript)) {
        throw "Virtual environment activation script was not found: $ActivateScript"
    }

    . $ActivateScript
    $PythonPath = python -c 'import sys; print(sys.executable)'
    Write-Host "[launch] Active interpreter: $PythonPath"
}

function Get-RequirementsHash {
    return (Get-FileHash -Path $RequirementsFile -Algorithm SHA256).Hash
}

function Test-DependenciesInstalled {
    if ($SkipDependencyCheck) {
        return $true
    }

    python -c "import PySide6, fitz, openai, dotenv" *> $null
    return $LASTEXITCODE -eq 0
}

function Install-DependenciesIfNeeded {
    $requirementsHash = Get-RequirementsHash
    $storedHash = ""
    if (Test-Path $StampFile) {
        $storedHash = (Get-Content $StampFile -Raw).Trim()
    }

    $needsInstall = $false
    if ($storedHash -ne $requirementsHash) {
        $needsInstall = $true
    }
    if (-not (Test-DependenciesInstalled)) {
        $needsInstall = $true
    }

    if (-not $needsInstall) {
        Write-Host "[launch] Dependencies are already satisfied. Skipping install."
        return
    }

    Write-Host "[launch] Installing or updating dependencies..."
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install -r $RequirementsFile
    Set-Content -Path $StampFile -Value $requirementsHash -Encoding ASCII
}

New-ProjectVenv
Ensure-ProjectEnvFile
Activate-ProjectVenv
Install-DependenciesIfNeeded

Write-Host "[launch] Starting application..."
if ($SmokeTest) {
    $env:QT_QPA_PLATFORM = "offscreen"
    python -c "from PySide6.QtWidgets import QApplication; from app.core.container import AppContainer; from app.ui.theme import apply_app_theme, material3_light_tokens; from app.ui.main_window import MainWindow; app = QApplication([]); apply_app_theme(app, material3_light_tokens()); container = AppContainer.build(); win = MainWindow(container); win.show(); app.processEvents(); print('LAUNCH_SMOKE_OK'); win.close()"
    exit $LASTEXITCODE
}

python run.py
