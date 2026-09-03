$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$connections = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
if (-not $connections) { Write-Host "No Streamlit process is using port 8765."; exit 0 }
$ids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($id in $ids) {
    $process = Get-Process -Id $id -ErrorAction SilentlyContinue
    $commandLine = ""
    try { $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction Stop).CommandLine } catch { }
    $isProjectProcess = $commandLine -and ($commandLine -like "*$ProjectRoot*")
    if ($process -and $process.ProcessName -in @("python", "pythonw") -and ($isProjectProcess -or -not $commandLine)) {
        Stop-Process -Id $id -Force
        Write-Host "Stopped process $id ($($process.ProcessName))."
    } else {
        Write-Warning "Port is used by non-Python process $id; it was not stopped."
    }
}
