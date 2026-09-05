$ErrorActionPreference = "Stop"

$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$BuildDirectory = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "build"))
$DistDirectory = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "dist"))
$AppName = -join @(
    [char]0x8BFE, [char]0x7A0B, [char]0x52A0, [char]0x6743, [char]0x5E73,
    [char]0x5747, [char]0x5206, [char]0x8BA1, [char]0x7B97, [char]0x5668
)

foreach ($Target in @($BuildDirectory, $DistDirectory)) {
    if (-not $Target.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the project: $Target"
    }
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}

foreach ($SpecFile in Get-ChildItem -LiteralPath $ProjectRoot -Filter "*.spec" -File) {
    if ($SpecFile.DirectoryName -ne $ProjectRoot) {
        throw "Refusing to clean a spec file outside the project: $($SpecFile.FullName)"
    }
    Remove-Item -LiteralPath $SpecFile.FullName -Force
}

$Python = (Get-Command python -ErrorAction Stop).Source
& $Python -c "import openpyxl, PyInstaller, tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "The selected Python must provide openpyxl, PyInstaller, and tkinter."
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $AppName `
    --distpath $DistDirectory `
    --workpath $BuildDirectory `
    --specpath $ProjectRoot `
    (Join-Path $ProjectRoot "app.py")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

$Executable = Join-Path $DistDirectory "$AppName.exe"
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Build finished without the expected executable: $Executable"
}

Write-Host "Built: $Executable"
