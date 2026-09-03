$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8765
$Url = "http://localhost:$Port"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = Join-Path $ProjectRoot "venv\Scripts\python.exe" }
Write-Host "项目 Python：$Python"
try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    Write-Host "Health check passed: $Url (HTTP $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "Web page is not responding: $Url" -ForegroundColor Yellow
}
$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($connections) {
    $connections | Select-Object State, OwningProcess, LocalAddress, LocalPort
    foreach ($connection in ($connections | Select-Object -ExpandProperty OwningProcess -Unique)) {
        Get-Process -Id $connection -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, Path
    }
} else {
    Write-Host "No process is listening on port $Port. Run .\start_app.ps1."
}
