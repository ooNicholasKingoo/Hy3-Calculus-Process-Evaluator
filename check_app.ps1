$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8765
$Url = "http://localhost:$Port"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = Join-Path $ProjectRoot "venv\Scripts\python.exe" }
Write-Host "Project Python: $Python"
try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    Write-Host "Health check passed: $Url (HTTP $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "Web page is not responding: $Url" -ForegroundColor Yellow
}
$pythonPaths = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot "venv\Scripts\python.exe")
)
$projectProcesses = @(Get-Process -Name python,pythonw -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and ($pythonPaths -contains $_.Path) })
if ($projectProcesses) {
    $projectProcesses | Select-Object Id, ProcessName, Path
} else {
    Write-Host "No project Python process was found. Run .\run_app.cmd."
}
