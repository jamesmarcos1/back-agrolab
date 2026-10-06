#Requires -Version 7.4
param(
    [Parameter(Mandatory)][string]$BackupFile,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [string]$KeyPath = (Join-Path (Split-Path -Parent $BackupFile) 'key.dpapi'),
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9@.:-]+$')][string]$SshHost = 'ubuntu@163.176.206.209',
    [ValidatePattern('^agrolab-(validation|restore)[A-Za-z0-9_.-]*$')][string]$RestoreContainer = 'agrolab-validation-pg',
    [switch]$KeepRestoreDatabase
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'backup_crypto.psm1') -Force
$key = Get-BackupKey -KeyPath $KeyPath
$plain = $null
$restoreDb = 'agrolab_restore_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss') + '_' + [Guid]::NewGuid().ToString('N').Substring(0,8) + '_test'
$restoreDbCreated = $false

function Invoke-BackupSsh {
    param([string]$Command, [byte[]]$InputBytes)
    $p = [Diagnostics.Process]::new()
    try {
        $p.StartInfo.FileName = 'ssh.exe'
        $p.StartInfo.UseShellExecute = $false
        $p.StartInfo.RedirectStandardInput = $true
        $p.StartInfo.RedirectStandardOutput = $true
        $p.StartInfo.RedirectStandardError = $true
        foreach ($arg in @('-i', (Resolve-Path -LiteralPath $SshKeyPath).Path,
            '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10', $SshHost, $Command)) {
            $p.StartInfo.ArgumentList.Add($arg)
        }
        [void]$p.Start()
        $stdout = $p.StandardOutput.ReadToEndAsync()
        $stderr = $p.StandardError.ReadToEndAsync()
        if ($InputBytes) { $p.StandardInput.BaseStream.Write($InputBytes, 0, $InputBytes.Length) }
        $p.StandardInput.Close()
        $p.WaitForExit()
        if ($p.ExitCode -ne 0) { throw ('Falha na validação: ' + $stderr.GetAwaiter().GetResult()) }
        return $stdout.GetAwaiter().GetResult()
    } finally { $p.Dispose() }
}

try {
    $encrypted = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $BackupFile).Path)
    $plain = Unprotect-BackupBytes -Data $encrypted -Key $key
    $tampered = [byte[]]$encrypted.Clone()
    $tampered[$tampered.Length - 1] = $tampered[-1] -bxor 1
    $rejected = $false
    try { [void](Unprotect-BackupBytes -Data $tampered -Key $key) } catch { $rejected = $true }
    if (-not $rejected) { throw 'Falha: backup adulterado foi aceito.' }
    Write-Output 'Criptografia verificada; adulteração rejeitada.'
    [void](Invoke-BackupSsh "sudo -n docker exec $RestoreContainer createdb -U agrolab $restoreDb")
    $restoreDbCreated = $true
    [void](Invoke-BackupSsh "sudo -n docker exec -i $RestoreContainer pg_restore -U agrolab -d $restoreDb --exit-on-error --no-owner --no-acl" -InputBytes $plain)
    $query = 'SELECT (SELECT count(*) FROM users) AS users_restored, (SELECT version_num FROM alembic_version) AS schema_version;'
    $result = Invoke-BackupSsh "sudo -n docker exec $RestoreContainer psql -U agrolab -d $restoreDb -c `"$query`""
    Write-Output ('Restauração validada somente no banco descartável ' + $restoreDb)
    Write-Output $result
} finally {
    try {
        if ($restoreDbCreated -and -not $KeepRestoreDatabase) {
            [void](Invoke-BackupSsh "sudo -n docker exec $RestoreContainer dropdb -U agrolab $restoreDb")
            Write-Output ('Banco de restauração desta execução removido: ' + $restoreDb)
        }
    } finally {
        if ($plain) { [Array]::Clear($plain, 0, $plain.Length) }
        [Array]::Clear($key, 0, $key.Length)
    }
}
