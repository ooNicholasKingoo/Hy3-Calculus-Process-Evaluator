$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPaths = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot "venv\Scripts\python.exe")
)
$projectProcesses = @(Get-Process -Name python,pythonw -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and ($pythonPaths -contains $_.Path) })
$ids = @($projectProcesses | Select-Object -ExpandProperty Id -Unique)
if (-not $ids) {
    try {
        $ids = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique)
    } catch { }
}
if (-not $ids) { Write-Host "No project Streamlit process is running."; exit 0 }
foreach ($id in $ids) {
    $process = Get-Process -Id $id -ErrorAction SilentlyContinue
    $commandLine = ""
    try { $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction Stop).CommandLine } catch { }
    $isProjectProcess = ($process -and $process.Path -and ($pythonPaths -contains $process.Path)) -or
        ($commandLine -and ($commandLine -like "*$ProjectRoot*"))
    if ($process -and $process.ProcessName -in @("python", "pythonw") -and $isProjectProcess) {
        Stop-Process -Id $id -Force
        Write-Host "Stopped process $id ($($process.ProcessName))."
    } else {
        Write-Warning "Port is used by non-Python process $id; it was not stopped."
    }
}
