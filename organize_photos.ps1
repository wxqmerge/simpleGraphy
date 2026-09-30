# Rename undated photos by their EXIF capture date, in place.
#
# Usage:
#   organize_photos.ps1                 -> process the current directory (recursively)
#   organize_photos.ps1 -Target <dir>   -> process that directory (recursively)
#   organize_photos.ps1 -Target <file>  -> rename just that one file
#
# Behavior:
#   - Recurses into subfolders (e.g. pan* folders) to find photos.
#   - A name that already starts with a date (YYYY.MM.DD... or PXL_YYYYMMDD...)
#     is left as-is.
#   - A name with NO date (e.g. raw ARW/CR2/NEF like DSC02799.ARW) is renamed,
#     IN PLACE, to  YYYY.MM.DDHH.MM.SS<original-name>.<ext>  using the EXIF
#     capture date (DateTimeOriginal) read via exiftool.
#   - Files are NOT moved; each stays in the folder it is found in.
#   - No date in name AND no EXIF date -> left alone.
#
# Sidecars (.caption / .xmp) named after the file are renamed to match.
#
# Requires exiftool for the no-date case. Looked up in this order:
#   1. next to this script (exiftool.exe in the same folder)  <- portable
#   2. C:\Users\wxqme\bin\exiftool.exe
#   3. anywhere on PATH
# If not found, no-date files are simply skipped.

param([string]$Target = "")

$extPattern = '\.(jpg|jpeg|heic|cr2|arw|nef|raw|dng|srw|orf|pef|sr2|sr3|raf)$'
$renamed = 0
$skipped = 0

# Resolve exiftool once: next to this script, then a known install, then PATH.
$script:exiftool = $null
$candidates = @(
    (Join-Path $PSScriptRoot "exiftool.exe"),
    "C:\Users\wxqme\bin\exiftool.exe"
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $script:exiftool = $c; break }
}
if (-not $script:exiftool) {
    $cmd = Get-Command exiftool -ErrorAction SilentlyContinue
    if ($cmd) { $script:exiftool = $cmd.Source }
}

# Return the EXIF capture date as "YYYY.MM.DDHH.MM.SS", or $null if absent.
function Get-ExifStamp {
    param([string]$Path)
    if (-not $script:exiftool) { return $null }
    $out = & $script:exiftool -d '%Y.%m.%d%H.%M.%S' -DateTimeOriginal $Path 2>$null
    if ($out -match '(\d{4}\.\d{2}\.\d{2}\d{2}\.\d{2}\.\d{2})') { return $Matches[1] }
    return $null
}

# Rename one undated file in place using its EXIF capture date. Names that
# already carry a date are left alone. $f is a FileInfo.
function Process-File {
    param($f)
    $base = $f.BaseName
    $newName = $f.Name

    # Already has a date in the name -> leave as-is.
    if ($base -match '^\d{4}\.\d{2}\.\d{2}' -or $base -match '^PXL_\d{8}') {
        return
    }

    # Undated -> rename in place using the EXIF capture date.
    $stamp = Get-ExifStamp $f.FullName
    if (-not $stamp) {
        Write-Host "SKIP (no date): $($f.Name)"
        $script:skipped++
        return
    }

    $newName = $stamp + $base + $f.Extension
    $target = Join-Path $f.DirectoryName $newName
    if (Test-Path $target) {
        Write-Host "SKIP (exists): $newName"
        $script:skipped++
        return
    }

    Rename-Item -LiteralPath $f.FullName -NewName $newName
    Write-Host "Renamed: $($f.Name) -> $newName  (in $($f.DirectoryName))"
    $script:renamed++

    foreach ($sidecar in @('caption', 'xmp')) {
        $sidecarPath = Join-Path $f.DirectoryName "$($f.Name).$sidecar"
        if (Test-Path $sidecarPath) {
            Rename-Item -LiteralPath $sidecarPath -NewName "$newName.$sidecar"
        }
    }
}

# Rename undated photos in a directory tree (recursively), in place.
function Process-Directory {
    param([string]$Dir)
    $files = Get-ChildItem -Path $Dir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match $extPattern
    }
    foreach ($f in $files) {
        Process-File $f
    }
}

# --- main ---
if ($Target -and (Test-Path -LiteralPath $Target -PathType Leaf)) {
    Write-Host "Renaming single file: $Target"
    Process-File (Get-Item -LiteralPath $Target)
} else {
    $dir = if ($Target) { $Target } else { (Get-Location).Path }
    Write-Host "Renaming undated photos in: $dir (recursively)"
    Process-Directory $dir
}

Write-Host "Done. Renamed: $renamed | Skipped: $skipped"
