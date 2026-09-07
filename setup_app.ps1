$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "Project directory: $ProjectRoot"
Write-Host "Checking Python version..."
$launcher = $null
$launcherArgs = @()
$candidates = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $candidates += ,@("py", @("-3.12"))
    $candidates += ,@("py", @("-3"))
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    $candidates += ,@("python", @())
}
foreach ($candidate in $candidates) {
    $exe = $candidate[0]
    $args = $candidate[1]
    $versionText = (& $exe @args --version 2>&1 | Out-String).Trim()
    if ($versionText -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 12)) {
            $launcher = $exe
            $launcherArgs = @($args)
            Write-Host "Python version accepted: $versionText" -ForegroundColor Green
            break
        }
    }
}
if (-not $launcher) {
    Write-Error "No usable Python 3.12+ was found. Install Python 3.12 or newer and try again."
    exit 1
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating .venv..."
    & $launcher @launcherArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv." }
}

Write-Host "Installing project dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check network or proxy settings and try again." }

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env"))) {
    Write-Host "No .env was created. Copy .env.example and add a local key only when online Hy3 is needed." -ForegroundColor Yellow
}

Push-Location $ProjectRoot
try {
    & $Python -c "import hy3_eval, streamlit, sympy, pandas; print('Dependency and module import check passed')"
    if ($LASTEXITCODE -ne 0) { throw "Module import check failed." }
    & $Python -m hy3_eval.cli validate-dataset
    if ($LASTEXITCODE -ne 0) { throw "Dataset validation failed." }
} finally {
    Pop-Location
}

Write-Host "Setup completed. Next steps:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_app.ps1"
Write-Host "  Or: .\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8765"
