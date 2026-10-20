# Rename undated photos by their EXIF capture date, in place.
# Version: 1.1

#
# Usage:
#   rename_dates.ps1                 -> process the current directory (recursively)
#   rename_dates.ps1 -Target <dir>   -> process that directory (recursively)
#   rename_dates.ps1 -Target <file>  -> rename just that one file
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
#   2. %USERPROFILE%\bin\exiftool.exe
#   3. anywhere on PATH
# If not found, no-date files are simply skipped.

param([string]$Target = "")

$extPattern = '\.(jpg|jpeg|heic|cr2|arw|nef|raw|dng|srw|orf|pef|sr2|sr3|raf)$'
$renamed = 0
$skipped = 0

# Resolve exiftool once: next to this script, then %USERPROFILE%\bin, then PATH.
$script:exiftool = $null
$candidates = @(
    (Join-Path $PSScriptRoot "exiftool.exe"),
    (Join-Path $env:USERPROFILE "bin\exiftool.exe")
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $script:exiftool = $c; break }
}
if (-not $script:exiftool) {
    $cmd = Get-Command exiftool -ErrorAction SilentlyContinue
    if ($cmd) { $script:exiftool = $cmd.Source }
}

# Verify exiftool actually runs
if ($script:exiftool) {
    $ver = (cmd /c "`"$($script:exiftool)`" -ver" 2>$null) -join ' '
    Write-Host "rename_dates v1.1 | exiftool $ver ($($script:exiftool))"
} else {
    Write-Host "rename_dates v1.1 | WARNING: exiftool not found - undated files will be skipped"
}

# Return the EXIF capture date as "YYYY.MM.DDHH.MM.SS", or $null if absent.
function Get-ExifStamp {
    param([string]$Path)
    if (-not $script:exiftool) { return $null }
    $tags = @('DateTimeOriginal', 'CreateDate', 'DateTime', 'ModifyDate')
    $pattern = '(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})'
    foreach ($tag in $tags) {
        $out = (cmd /c "`"$($script:exiftool)`" -$tag `"$Path`"" 2>$null) -join ' '
        $m = [regex]::Match($out, $pattern)
        if ($m.Success) {
            $stamp = "$($m.Groups[1].Value).$($m.Groups[2].Value).$($m.Groups[3].Value)$($m.Groups[4].Value).$($m.Groups[5].Value).$($m.Groups[6].Value)"
            if ($stamp -match '^\d{4}\.\d{2}\.\d{4}\.\d{2}\.\d{2}$') {
                return $stamp
            }
        }
    }
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
    $files = Get-ChildItem -Path $Dir -Recurse -ErrorAction SilentlyContinue | Where-Object {
        -not $_.PSIsContainer -and $_.Name -match $extPattern
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
