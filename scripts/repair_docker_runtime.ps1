# Repara apenas diretórios de sockets temporários, preservando backup.
# Não altera VHDX, imagens, containers ou volumes.
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $taskRoot '.runtime\docker-repair.log'
New-Item -ItemType Directory -Path (Split-Path $logPath) -Force | Out-Null
try {
    Get-Process -Name 'Docker Desktop','com.docker.backend' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like 'C:\Program Files\Docker\*' } | Stop-Process
    $allowedPaths = @(
        'C:\Users\USUARIO\AppData\Local\docker-secrets-engine',
        'C:\Users\USUARIO\AppData\Local\Docker\run'
    )
    foreach ($targetPath in $allowedPaths) {
        $resolvedPath = (Resolve-Path -LiteralPath $targetPath).Path
        if ($resolvedPath -ne $targetPath) { throw 'Caminho de runtime inesperado' }
        $backupPath = $targetPath + '.agrolab-preserved-' + (Get-Date -Format 'yyyyMMddHHmmss')
        if (Test-Path -LiteralPath $backupPath) { throw 'Backup já existe' }
        [System.IO.Directory]::Move($targetPath, $backupPath)
        New-Item -ItemType Directory -Path $targetPath | Out-Null
        Add-Content -LiteralPath $logPath -Value ('Preservado: ' + $backupPath)
    }
    Add-Content -LiteralPath $logPath -Value 'SUCCESS'
} catch {
    Add-Content -LiteralPath $logPath -Value ('FAILED: ' + $_.Exception.Message)
    exit 1
}
