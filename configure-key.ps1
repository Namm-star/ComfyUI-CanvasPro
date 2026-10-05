param([string]$KeyFile = (Join-Path $env:LOCALAPPDATA 'CanvasProComfyUI/key.txt'))
$ErrorActionPreference = 'Stop'
$resolvedKeyPath = [IO.Path]::GetFullPath($KeyFile)
$privateDirectory = [IO.Path]::GetDirectoryName($resolvedKeyPath)
[IO.Directory]::CreateDirectory($privateDirectory) | Out-Null
# Apply owner-only ACL before any credential bytes are written.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = [Security.AccessControl.FileSecurity]::new()
$acl.SetOwner($identity)
$acl.SetAccessRuleProtection($true, $false)
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'Allow'))
if (-not (Test-Path -LiteralPath $resolvedKeyPath)) {
    [IO.File]::WriteAllText($resolvedKeyPath, '')
}
Set-Acl -LiteralPath $resolvedKeyPath -AclObject $acl
$secret = Read-Host 'Paste your CanvasPro site Key (hidden)' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
    if (-not $plainKey -or $plainKey -match '\s') { throw 'Key must be a nonempty single token' }
    [IO.File]::WriteAllText($resolvedKeyPath, $plainKey, [Text.UTF8Encoding]::new($false))
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $plainKey = $null
    $secret.Dispose()
}
Write-Output "Key saved in local owner-only file. Restart ComfyUI if needed."
