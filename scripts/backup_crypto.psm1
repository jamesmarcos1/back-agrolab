#Requires -Version 7.4
# AES-256-GCM autentica o conteúdo e o cabeçalho; a chave local usa DPAPI.
Add-Type -AssemblyName System.Security.Cryptography.ProtectedData
$script:BackupHeader = [Text.Encoding]::ASCII.GetBytes("AGROLAB1`n")

function Get-BackupKey {
    param([Parameter(Mandatory)][string]$KeyPath, [switch]$Create)
    $KeyPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($KeyPath)
    if (-not (Test-Path -LiteralPath $KeyPath)) {
        if (-not $Create) { throw 'Chave de backup ausente.' }
        $rawKey = [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
        $keyDirectory = [IO.Path]::GetDirectoryName($KeyPath)
        $temporaryKey = Join-Path $keyDirectory ('.agrolab-key-' + [Guid]::NewGuid().ToString('N') + '.tmp')
        try {
            $protectedKey = [Security.Cryptography.ProtectedData]::Protect(
                $rawKey, $script:BackupHeader, [Security.Cryptography.DataProtectionScope]::CurrentUser)
            $keyStream = [IO.File]::Open($temporaryKey, [IO.FileMode]::CreateNew,
                [IO.FileAccess]::Write, [IO.FileShare]::None)
            try { $keyStream.Write($protectedKey); $keyStream.Flush($true) }
            finally { $keyStream.Dispose() }
            # Publica somente o arquivo completo, sem sobrescrever uma chave existente.
            try { [IO.File]::Move($temporaryKey, $KeyPath) }
            catch [IO.IOException] {
                if (-not [IO.File]::Exists($KeyPath)) { throw }
            }
        } finally {
            if ([IO.File]::Exists($temporaryKey)) { [IO.File]::Delete($temporaryKey) }
            [Array]::Clear($rawKey, 0, $rawKey.Length)
        }
    }
    $key = [Security.Cryptography.ProtectedData]::Unprotect(
        [IO.File]::ReadAllBytes($KeyPath), $script:BackupHeader,
        [Security.Cryptography.DataProtectionScope]::CurrentUser)
    if ($key.Length -ne 32) { throw 'Chave AES-256 inválida.' }
    return ,$key
}

function Protect-BackupBytes {
    param([Parameter(Mandatory)][byte[]]$Data, [Parameter(Mandatory)][ValidateCount(32,32)][byte[]]$Key)
    $nonce = [Security.Cryptography.RandomNumberGenerator]::GetBytes(12)
    $tag = [byte[]]::new(16)
    $ciphertext = [byte[]]::new($Data.Length)
    $aes = [Security.Cryptography.AesGcm]::new($Key, 16)
    $stream = [IO.MemoryStream]::new()
    try {
        $aes.Encrypt($nonce, $Data, $ciphertext, $tag, $script:BackupHeader)
        foreach ($part in @($script:BackupHeader, $nonce, $tag, $ciphertext)) {
            $stream.Write($part, 0, $part.Length)
        }
        return ,$stream.ToArray()
    } finally { $aes.Dispose(); $stream.Dispose() }
}

function Unprotect-BackupBytes {
    param([Parameter(Mandatory)][byte[]]$Data, [Parameter(Mandatory)][ValidateCount(32,32)][byte[]]$Key)
    $offset = $script:BackupHeader.Length
    if ($Data.Length -lt ($offset + 29)) { throw 'Backup truncado.' }
    $header = [byte[]]::new($offset)
    [Array]::Copy($Data, 0, $header, 0, $offset)
    if ([Convert]::ToHexString($header) -ne [Convert]::ToHexString($script:BackupHeader)) {
        throw 'Formato de backup desconhecido.'
    }
    $nonce = [byte[]]::new(12)
    $tag = [byte[]]::new(16)
    $ciphertext = [byte[]]::new($Data.Length - $offset - 28)
    [Array]::Copy($Data, $offset, $nonce, 0, 12)
    [Array]::Copy($Data, ($offset + 12), $tag, 0, 16)
    [Array]::Copy($Data, ($offset + 28), $ciphertext, 0, $ciphertext.Length)
    $plaintext = [byte[]]::new($ciphertext.Length)
    $aes = [Security.Cryptography.AesGcm]::new($Key, 16)
    try {
        $aes.Decrypt($nonce, $ciphertext, $tag, $plaintext, $script:BackupHeader)
        return ,$plaintext
    } catch {
        [Array]::Clear($plaintext, 0, $plaintext.Length)
        throw
    } finally { $aes.Dispose() }
}

Export-ModuleMember -Function Get-BackupKey, Protect-BackupBytes, Unprotect-BackupBytes
