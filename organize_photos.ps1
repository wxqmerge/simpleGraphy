$extensions = @('JPG','jpg','jpeg','JPEG','HEIC','heic','CR2','cr2','ARW','arw','NEF','nef','RAW','raw','DNG','dng','SRW','srw','ORF','orf','PEF','pef','SR2','sr2','SR3','sr3','RAF','raf')
$moved = 0
$skipped = 0

foreach ($ext in $extensions) {
    $files = Get-ChildItem -Path "*.$ext" -File -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $base = $f.BaseName
        $folder = $null

        if ($base -match '^\d{4}\.\d{2}\.\d{2}') {
            $dateRaw = $base.Substring(0, 10)
            $dateClean = $dateRaw -replace '\.', ''
            $folder = $dateClean.Substring(2, 2) + $dateClean.Substring(4, 4)
        }
        elseif ($base -match '^PXL_\d{8}') {
            $folder = $base.Substring(6, 2) + $base.Substring(8, 4)
        }

        if (-not $folder) { continue }

        if (-not (Test-Path $folder)) {
            New-Item -ItemType Directory -Path $folder | Out-Null
            Write-Host "Created: $folder"
        }

        $target = Join-Path $folder $f.Name
        if (Test-Path $target) {
            Write-Host "SKIP: $($f.Name)"
            $skipped++
            continue
        }

        Move-Item -Path $f.FullName -Destination $folder -Force
        Write-Host "Moved: $($f.Name) -> $folder/"
        $moved++

        foreach ($sidecar in @('caption', 'xmp')) {
            $sidecarPath = Join-Path $f.DirectoryName "$base.$sidecar"
            if (Test-Path $sidecarPath) {
                Move-Item -Path $sidecarPath -Destination $folder -Force
            }
        }
    }
}

Write-Host "Done. Moved: $moved | Skipped: $skipped"
