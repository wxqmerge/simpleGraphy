# Organize photos into per-date (YYMMDD) folders.
#
# Usage:
#   organize_photos.ps1                 -> organize the current directory
#   organize_photos.ps1 -Target <dir>   -> organize that directory
#   organize_photos.ps1 -Target <file>  -> rename just that one file
#
# Naming rules (checked in order):
#   1. Name already starts with a date  -> YYYY.MM.DD...  or  PXL_YYYYMMDD...
#        -> moved as-is into the matching YYMMDD folder (no rename).
#   2. Name has NO date (e.g. raw ARW/CR2/NEF like DSC02799.ARW)
#        -> capture date read from EXIF (DateTimeOriginal) via exiftool,
#           file renamed to  YYYY.MM.DDHH.MM.SS<original-name>.<ext>
#           and moved into the matching YYMMDD folder.
#   3. No date in name AND no EXIF date -> left alone.
#
# Sidecars (.caption / .xmp) named after the file are moved along and
# renamed to match when the photo is renamed.
#
# Requires exiftool for rule 2. Looked up in this order:
#   1. next to this script (exiftool.exe in the same folder)  <- portable
#   2. C:\Users\wxqme\bin\exiftool.exe
#   3. anywhere on PATH
# If not found, rule-2 files are simply skipped.

param([string]$Target = "")

$extensions = @('JPG','jpg','jpeg','JPEG','HEIC','heic','CR2','cr2','ARW','arw','NEF','nef','RAW','raw','DNG','dng','SRW','srw','ORF','orf','PEF','pef','SR2','sr2','SR3','sr3','RAF','raf')
$moved = 0
$skipped = 0
$renamed = 0

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

# Apply the naming rules to one file and move (renaming if needed) it into its
# YYMMDD folder, carrying sidecars. $f is a FileInfo.
function Process-File {
    param($f)
    $base = $f.BaseName
    $folderName = $null
    $newName = $f.Name

    if ($base -match '^\d{4}\.\d{2}\.\d{2}') {
        $dateRaw = $base.Substring(0, 10)
        $dateClean = $dateRaw -replace '\.', ''
        $folderName = $dateClean.Substring(2, 6)
    }
    elseif ($base -match '^PXL_\d{8}') {
        $folderName = $base.Substring(6, 6)
    }
    else {
        $stamp = Get-ExifStamp $f.FullName
        if ($stamp) {
            $newName = $stamp + $base + $f.Extension
            $datePart = $stamp.Substring(0, 10)
            $folderName = ($datePart -replace '\.', '').Substring(2, 6)
        }
    }

    if (-not $folderName) {
        Write-Host "SKIP (no date): $($f.Name)"
        $script:skipped++
        return
    }

    $folder = Join-Path $f.DirectoryName $folderName
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
        Write-Host "Created: $folder"
    }

    $target = Join-Path $folder $newName
    if (Test-Path $target) {
        Write-Host "SKIP (exists): $($f.Name)"
        $script:skipped++
        return
    }

    Move-Item -Path $f.FullName -Destination $target -Force
    if ($newName -ne $f.Name) {
        Write-Host "Renamed+Moved: $($f.Name) -> $folder/$newName"
        $script:renamed++
    } else {
        Write-Host "Moved: $($f.Name) -> $folder/"
    }
    $script:moved++

    foreach ($sidecar in @('caption', 'xmp')) {
        $sidecarPath = Join-Path $f.DirectoryName "$($f.Name).$sidecar"
        if (Test-Path $sidecarPath) {
            Move-Item -Path $sidecarPath -Destination (Join-Path $folder "$newName.$sidecar") -Force
        }
    }
}

# Apply the naming rules to every photo in a directory.
function Process-Directory {
    param([string]$Dir)
    foreach ($ext in $extensions) {
        $files = Get-ChildItem -Path (Join-Path $Dir "*.$ext") -File -ErrorAction SilentlyContinue
        foreach ($f in $files) {
            Process-File $f
        }
    }
}

# --- main ---
if ($Target -and (Test-Path -LiteralPath $Target -PathType Leaf)) {
    Write-Host "Organizing single file: $Target"
    Process-File (Get-Item -LiteralPath $Target)
} else {
    $dir = if ($Target) { $Target } else { (Get-Location).Path }
    Write-Host "Organizing photos in: $dir"
    Process-Directory $dir
}

Write-Host "Done. Moved: $moved | Renamed: $renamed | Skipped: $skipped"
