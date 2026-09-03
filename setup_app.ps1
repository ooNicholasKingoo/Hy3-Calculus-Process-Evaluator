$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "项目目录：$ProjectRoot"
Write-Host "检查 Python 版本……"
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
            Write-Host "Python 版本通过：$versionText" -ForegroundColor Green
            break
        }
    }
}
if (-not $launcher) {
    Write-Error "未找到可用的 Python 3.12+。请安装 Python 3.12 或更高版本后重试。"
    exit 1
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "创建虚拟环境 .venv……"
    & $launcher @launcherArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "创建 .venv 失败。" }
}

Write-Host "安装/更新项目依赖……"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败，请检查网络或使用代理后重试。" }

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env"))) {
    Write-Host "未创建 .env：在线 Hy3 Key 需要时请复制 .env.example 为 .env，并填写本地 Key。" -ForegroundColor Yellow
}

Push-Location $ProjectRoot
try {
    & $Python -c "import hy3_eval, streamlit, sympy, pandas; print('依赖和模块导入检查通过')"
    if ($LASTEXITCODE -ne 0) { throw "模块导入检查失败。" }
    & $Python -m hy3_eval.cli validate-dataset
    if ($LASTEXITCODE -ne 0) { throw "题集检查失败。" }
} finally {
    Pop-Location
}

Write-Host "初始化完成。下一步：" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_app.ps1"
Write-Host "  或：.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8765"
