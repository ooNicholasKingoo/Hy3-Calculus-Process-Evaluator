$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $legacyPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $legacyPython) {
        $Python = $legacyPython
        Write-Warning "使用兼容的旧环境 venv；新下载项目建议使用 .venv。"
    }
}
$Port = 8765
$Url = "http://localhost:$Port"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Python environment not found. Run powershell -ExecutionPolicy Bypass -File .\setup_app.ps1 first."
    exit 1
}

$healthy = $false
try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
    $healthy = $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
} catch { }

if ($healthy) {
    Write-Host "Streamlit is already running: $Url" -ForegroundColor Green
    try { Start-Process $Url -ErrorAction Stop } catch { Write-Warning "Browser could not be opened automatically. Open $Url manually." }
    exit 0
}

$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warning "Port $Port is occupied by another process. Run .\check_app.ps1 to inspect it."
    exit 2
}

$args = @("-m", "streamlit", "run", (Join-Path $ProjectRoot "app.py"), "--server.headless", "true", "--server.port", "$Port")
Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $ProjectRoot -WindowStyle Minimized

for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            Write-Host "Streamlit started successfully: $Url" -ForegroundColor Green
            try { Start-Process $Url -ErrorAction Stop } catch { Write-Warning "Browser could not be opened automatically. Open $Url manually." }
            exit 0
        }
    } catch { }
}

Write-Error "Streamlit did not start in time. Run .\check_app.ps1, then run $Python -m streamlit run app.py to inspect errors."
exit 3
