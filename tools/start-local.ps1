$ErrorActionPreference = 'Stop'
$workspacePath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$localPath = Join-Path $workspacePath '.local'
New-Item -ItemType Directory -Path $localPath -Force | Out-Null
$pythonPath = Join-Path $workspacePath 'backend\.venv\Scripts\python.exe'
$nodePath = (Get-Command node -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create backend/.venv and install requirements.lock first.' }
if (-not (Test-Path -LiteralPath (Join-Path $workspacePath '.env'))) { throw 'Configure .env first. See docs/07-running.md.' }
foreach ($port in @(8000, 5173)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop that process before starting this workspace."
    }
}
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8000','--no-proxy-headers' -WorkingDirectory (Join-Path $workspacePath 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localPath 'api.out.log') -RedirectStandardError (Join-Path $localPath 'api.err.log') -PassThru
$vitePath = Join-Path $workspacePath 'frontend\node_modules\vite\bin\vite.js'
$webProcess = Start-Process -FilePath $nodePath -ArgumentList "`"$vitePath`"",'--host','127.0.0.1' -WorkingDirectory (Join-Path $workspacePath 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localPath 'web.out.log') -RedirectStandardError (Join-Path $localPath 'web.err.log') -PassThru
@(
    @{ id = $apiProcess.Id; started = $apiProcess.StartTime.ToUniversalTime().Ticks },
    @{ id = $webProcess.Id; started = $webProcess.StartTime.ToUniversalTime().Ticks }
) | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $localPath 'app-processes.json')
Write-Output 'MyCareer: http://127.0.0.1:5173'
Write-Output 'API documentation: http://127.0.0.1:8000/api/docs'
Write-Output 'Logs: .local/. Stop these application processes with tools/stop-local.ps1.'
