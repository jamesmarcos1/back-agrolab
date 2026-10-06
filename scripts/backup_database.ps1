#Requires -Version 7.4
param(
    [Parameter(Mandatory)][string]$SshKeyPath,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9@.:-]+$')][string]$SshHost = 'ubuntu@163.176.206.209',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]+$')][string]$Container = 'db-r13cwfklsavepdjyxl5j5rqs',
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime\backups')
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'backup_crypto.psm1') -Force
$OutputDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$keyPath = Join-Path $OutputDirectory 'key.dpapi'
$key = Get-BackupKey -KeyPath $keyPath -Create
$process = [Diagnostics.Process]::new()
$memory = [IO.MemoryStream]::new()
$plaintext = $null
try {
    $process.StartInfo.FileName = 'ssh.exe'
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    foreach ($argument in @('-i', (Resolve-Path -LiteralPath $SshKeyPath).Path,
        '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
        $SshHost, "sudo -n docker exec $Container pg_dump -U agrolab -d agrolab -Fc --no-owner --no-acl")) {
        $process.StartInfo.ArgumentList.Add($argument)
    }
    [void]$process.Start()
    $stderr = $process.StandardError.ReadToEndAsync()
    $buffer = [byte[]]::new(65536)
    while (($count = $process.StandardOutput.BaseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $memory.Write($buffer, 0, $count)
        if ($memory.Length -gt 256MB) { $process.Kill(); throw 'Dump excedeu limite local de 256 MB.' }
    }
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw ('Falha no pg_dump: ' + $stderr.GetAwaiter().GetResult()) }
    $plaintext = $memory.ToArray()
    if ($plaintext.Length -lt 5 -or [Text.Encoding]::ASCII.GetString($plaintext, 0, 5) -ne 'PGDMP') {
        throw 'O servidor não retornou um dump PostgreSQL custom válido.'
    }
    $encrypted = Protect-BackupBytes -Data $plaintext -Key $key
    $outputPath = Join-Path $OutputDirectory ('agrolab-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '.agbackup')
    [IO.File]::WriteAllBytes($outputPath, $encrypted)
    Write-Output ('Backup AES-256-GCM salvo: ' + $outputPath)
    Write-Output ('Tamanho do dump: ' + $plaintext.Length + ' bytes. Nenhum dump em texto foi salvo.')
} finally {
    if ($plaintext) { [Array]::Clear($plaintext, 0, $plaintext.Length) }
    if ($memory.Length) { [Array]::Clear($memory.GetBuffer(), 0, [int]$memory.Length) }
    [Array]::Clear($key, 0, $key.Length)
    $memory.Dispose()
    $process.Dispose()
}
