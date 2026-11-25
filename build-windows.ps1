$ErrorActionPreference = 'Stop'

# Windows wrapper for the portable Bash build. No WSL is required; use bundled tools when present or installed Git Bash and LLVM.
$root = $PSScriptRoot
$llvmBin = if ($env:LLVM_BIN) { $env:LLVM_BIN } elseif (Test-Path (Join-Path $root 'tools\LLVM-portable\LLVM\bin\clang.exe')) { Join-Path $root 'tools\LLVM-portable\LLVM\bin' } else { $null }
if (-not $llvmBin) {
    $clang = Get-Command clang.exe -ErrorAction SilentlyContinue
    if ($clang) { $llvmBin = Split-Path -Parent $clang.Source }
}
if (-not $llvmBin -or -not (Test-Path (Join-Path $llvmBin 'clang.exe')) -or -not (Test-Path (Join-Path $llvmBin 'ld.lld.exe'))) {
    throw 'LLVM clang.exe and ld.lld.exe are required. Set LLVM_BIN to their bin folder or install LLVM.'
}

$bashCandidates = @(
    $env:GIT_BASH,
    (Join-Path $root 'tools\GitPortable\bin\bash.exe'),
    (Join-Path $root 'tools\GitPortable\usr\bin\bash.exe'),
    (Join-Path $env:ProgramFiles 'Git\bin\bash.exe'),
    (Join-Path $env:ProgramFiles 'Git\usr\bin\bash.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$bash = if ($bashCandidates.Count -gt 0) { $bashCandidates | Select-Object -First 1 } else {
    $cmd = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($cmd) { $cmd.Source } else { $null }
}
if (-not $bash) {
    throw 'Git Bash is required. The bundled tools\GitPortable\bin\bash.exe was not found; set GIT_BASH to bash.exe.'
}

$env:PATH = "$llvmBin;$env:PATH"
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($python) { $env:PYTHON = $python.Source }
$env:LLD = Join-Path $llvmBin 'ld.lld.exe'
$nm = Join-Path $llvmBin 'llvm-nm.exe'
if (Test-Path -LiteralPath $nm) { $env:NM = $nm }
$cygpath = & $bash -lc 'command -v cygpath' 2>$null
if ($LASTEXITCODE -eq 0 -and $cygpath) {
    $rootUnix = (& $bash -lc "cygpath -u '$root'").Trim()
} else {
    $rootUnix = $root -replace '\\','/'
}
& $bash -lc "cd '$rootUnix' && bash ./build.sh"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Build completed. ARMv7/QNX libraries are in plugin\.'