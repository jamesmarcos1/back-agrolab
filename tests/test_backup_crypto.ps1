#Requires -Version 7.4
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Este teste usa DPAPI do Windows.' }
$taskRoot = Split-Path -Parent $PSScriptRoot
$modulePath = Join-Path $taskRoot 'scripts\backup_crypto.psm1'
$scratch = Join-Path $taskRoot '.runtime'
New-Item -ItemType Directory -Path $scratch -Force | Out-Null
$testKeyPath = Join-Path $scratch ('key-race-' + [Guid]::NewGuid().ToString('N') + '.dpapi')
$barrier = [Threading.Barrier]::new(8)
$key = $null
try {
    $results = 1..8 | ForEach-Object -Parallel {
        $ErrorActionPreference = 'Stop'
        Import-Module $using:modulePath -Force
        $syncBarrier = $using:barrier
        [void]$syncBarrier.SignalAndWait()
        $workerKey = Get-BackupKey -KeyPath $using:testKeyPath -Create
        try { [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($workerKey)) }
        finally { [Array]::Clear($workerKey, 0, $workerKey.Length) }
    } -ThrottleLimit 8
    if ($results.Count -ne 8 -or @($results | Select-Object -Unique).Count -ne 1) {
        throw 'Inicializações concorrentes não receberam a mesma chave recuperável.'
    }
    Import-Module $modulePath -Force
    $key = Get-BackupKey -KeyPath $testKeyPath
    $data = [Text.Encoding]::UTF8.GetBytes('Conteúdo de teste do backup.')
    $encrypted = Protect-BackupBytes -Data $data -Key $key
    $roundtrip = Unprotect-BackupBytes -Data $encrypted -Key $key
    if ([Convert]::ToHexString($data) -ne [Convert]::ToHexString($roundtrip)) {
        throw 'Descriptografia alterou o conteúdo.'
    }
    $encrypted[-1] = $encrypted[-1] -bxor 1
    $rejected = $false
    try { [void](Unprotect-BackupBytes -Data $encrypted -Key $key) }
    catch {
        if ($_.Exception.InnerException -is [Security.Cryptography.AuthenticationTagMismatchException]) {
            $rejected = $true
        } else { throw }
    }
    if (-not $rejected) { throw 'Backup adulterado foi aceito.' }
    Write-Output 'Backup: 8/8 chaves concorrentes iguais, conteúdo recuperado e adulteração rejeitada.'
} finally {
    $barrier.Dispose()
    if ($key) { [Array]::Clear($key, 0, $key.Length) }
    if (Test-Path -LiteralPath $testKeyPath) { Remove-Item -LiteralPath $testKeyPath -Force }
}
