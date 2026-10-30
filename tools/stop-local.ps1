$ErrorActionPreference = 'Stop'
$workspacePath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pidPath = Join-Path $workspacePath '.local\app-processes.json'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output 'No recorded application processes.'; exit }
$recorded = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
$inventory = Get-CimInstance Win32_Process
foreach ($record in $recorded) {
    $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq $record.started) {
        $queue = [System.Collections.Generic.Queue[int]]::new()
        $queue.Enqueue([int]$record.id)
        $ownedIds = [System.Collections.Generic.List[int]]::new()
        while ($queue.Count -gt 0) {
            $ownedId = $queue.Dequeue()
            $ownedIds.Add($ownedId)
            foreach ($child in ($inventory | Where-Object { $_.ParentProcessId -eq $ownedId })) { $queue.Enqueue([int]$child.ProcessId) }
        }
        foreach ($ownedId in $ownedIds) { Stop-Process -Id $ownedId -ErrorAction SilentlyContinue }
    }
}
Remove-Item -LiteralPath $pidPath
Write-Output 'Recorded application process trees stopped. The database is unchanged.'
