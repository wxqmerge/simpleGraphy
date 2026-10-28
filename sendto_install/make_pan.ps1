param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Files)

$usage = @'
Usage: make_pan.ps1 <file1> [file2] [file3] ...

Moves the selected files into a folder named pan_xxxxx, created
next to the FIRST file.

  - If the first file's name contains DSC<digits> (e.g. DSC02799),
    the folder is pan_02799 (the digits after DSC).
  - If the first file's name has no DSC<digits>, a unique 5-digit
    pan_xxxxx is used (one that does not already exist next to it).

Also moves .caption / .xmp sidecar files along.
Never overwrites: files whose name already exists in the target
are skipped.
'@

if (-not $Files) { Write-Host $usage; exit 1 }

$paths = @()
foreach ($p in $Files) {
    $t = $p.Trim('"')
    if ($t) { $paths += $t }
}

$files = @()
foreach ($p in $paths) {
    if (Test-Path -LiteralPath $p -PathType Leaf) {
        $files += (Resolve-Path -LiteralPath $p).Path
    }
    elseif (Test-Path -LiteralPath $p -PathType Container) {
        Write-Host "SKIP not a file: $p"
    }
    else {
        Write-Host "SKIP not found: $p"
    }
}

if ($files.Count -eq 0) {
    Write-Host "ERROR: no readable files selected."
    Write-Host $usage
    exit 1
}

$first = Get-Item -LiteralPath $files[0]
$base = $first.DirectoryName

$m = [regex]::Match($first.Name, 'DSC(\d+)', 'IgnoreCase')
if ($m.Success) {
    $destName = 'pan_' + $m.Groups[1].Value
    Write-Host "First file: $($first.Name)  ->  $destName"
}
else {
    $existing = @{}
    foreach ($d in (Get-ChildItem -LiteralPath $base -Directory -Filter 'pan_*')) {
        $existing[$d.Name.ToLowerInvariant()] = $true
    }
    $r = Get-Random -Minimum 10000 -Maximum 100000
    while ($existing.ContainsKey(("pan_$r").ToLowerInvariant())) {
        # stay inside the 5-digit range
        if ($r -ge 99999) { $r = 10000 } else { $r++ }
    }
    $destName = "pan_$r"
    Write-Host "First file: $($first.Name)  (no DSC number)  ->  $destName"
}

$dest = Join-Path $base $destName
if (-not (Test-Path -LiteralPath $dest -PathType Container)) {
    try {
        # fails terminably if $dest exists as a file
        New-Item -ItemType Directory -Path $dest -ErrorAction Stop | Out-Null
    }
    catch {
        Write-Error "Cannot create folder: $dest"
        exit 1
    }
    Write-Host "Created: $dest"
}
else {
    Write-Host "Existing: $dest"
}

$moved = 0
$skipped = 0
foreach ($f in $files) {
    $item = Get-Item -LiteralPath $f
    if ($item.DirectoryName -eq $dest) {
        Write-Host "SKIP already inside: $($item.Name)"
        $skipped++
        continue
    }
    $target = Join-Path $dest $item.Name
    if (Test-Path -LiteralPath $target) {
        Write-Host "SKIP exists: $($item.Name)"
        $skipped++
        continue
    }
    Move-Item -LiteralPath $f -Destination $dest
    Write-Host "Moved: $($item.Name)"
    $moved++
    foreach ($ext in '.caption', '.xmp') {
        $src = $f + $ext
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            $sideName = $item.Name + $ext
            $sideTarget = Join-Path $dest $sideName
            if (Test-Path -LiteralPath $sideTarget) {
                Write-Host "SKIP exists: $sideName"
            }
            else {
                Move-Item -LiteralPath $src -Destination $sideTarget
                Write-Host "Moved: $sideName"
            }
        }
    }
}

Write-Host ""
Write-Host "Done. Moved: $moved  Skipped: $skipped  Folder: $dest"
