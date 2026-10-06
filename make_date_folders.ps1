# Move photos into per-date (YYMMDD) folders, at the top level of a folder.
#
# Usage:
#   make_date_folders.ps1                 -> organize the current directory
#   make_date_folders.ps1 -Target <dir>   -> organize that directory
#   make_date_folders.ps1 -Target <file>  -> move just that one file
#
# Behavior (top level only; subfolders are NOT scanned):
#   - A name that already starts with a date (YYYY.MM.DD... or PXL_YYYYMMDD...)
#     is moved as-is into the matching YYMMDD folder.
#   - A name with NO date (e.g. raw ARW/CR2/NEF like DSC02799.ARW) is renamed
#     to  YYYY.MM.DDHH.MM.SS<original-name>.<ext>  using the EXIF capture date
#     (DateTimeOriginal) read via exiftool, then moved into the matching YYMMDD
#     folder.
#   - No date in name AND no EXIF date -> left alone.
#
# Sidecars (.caption / .xmp) named after the file are moved along and renamed
# to match when the photo is renamed.
#
# Requires exiftool for the no-date case. Looked up in this order:
#   1. next to this script (exiftool.exe in the same folder)  <- portable
#   2. C:\Users\wxqme\bin\exiftool.exe
#   3. anywhere on PATH
# If not found, no-date files are simply skipped.

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

# Move one photo into its YYMMDD folder (renaming undated files first). $f is a
# FileInfo.
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

# Move photos at the top level of a directory into their YYMMDD folders.
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
    Write-Host "Organizing photos in: $dir (top level only)"
    Process-Directory $dir
}

Write-Host "Done. Moved: $moved | Renamed: $renamed | Skipped: $skipped"
