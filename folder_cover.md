# Folder Cover Management Plan

## Overview

Allow control over which image represents each folder in the gallery. Every directory gets a `.folder_cover` file with the cover image path. Users can change covers via alt+click in the browser (logs path to F12 console), then apply changes with a CLI command.

---

## 1. Auto-create `.folder_cover` Files During Generation

**File:** `generate_gallery.py`

### New function: `get_folder_cover(dirpath)`
- Reads `{dirpath}/.folder_cover` if it exists
- Strips whitespace from the content
- Resolves the relative path against `dirpath`
- Validates: file exists, extension is in `IMAGE_EXTENSIONS`
- Returns the resolved absolute path, or `None` on any failure

### New function: `ensure_folder_cover(dirpath, root_path)`
- Checks if `{dirpath}/.folder_cover` already exists with a valid (existing) image path
- If valid, returns early — don't overwrite user choice
- If missing or broken, determines the default cover:
  - First, try images directly in `dirpath` (same logic as `get_image_files`)
  - If none, recursively search subdirectories (same `find_first_image` logic)
- If a default image is found:
  - Compute relative path from `dirpath` to the image
  - Write that path to `{dirpath}/.folder_cover`
- Returns the resolved cover path (or `None` if no images exist at all)

### Integration point — the subdirectory loop
- For each subdirectory, call `ensure_folder_cover(subdir, root_path)`:
  - Reads existing `.folder_cover` if valid
  - Creates one with the default image if missing/broken
  - Returns the chosen cover path
- The thumbnail generation (`_dir_thumb.jpg`) and HTML rendering use the returned path

### Integration point — the current directory's own cover
- At the top of `generate_html()`, call `ensure_folder_cover(directory, root_path)` so the current directory also gets a `.folder_cover` if it doesn't have one

---

## 2. Alt+Click Path Logging (Embedded JavaScript)

**File:** `generate_gallery.py` (the embedded HTML/JS template)

### Data attribute on every `<img>`
- Every gallery image `<img>` tag has a `data-gallery-path` attribute containing the relative path from the gallery root to the image (e.g., `26/260102_Little_River/PXL_20260102_183827584.jpg`).

### Event listener (inside the image click handler)
The alt+click check is embedded inside the per-image click handler (not on the document level) because the lightbox handler calls `stopPropagation()`, preventing document-level delegation:

```js
img.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.altKey) {
        console.log('Gallery path:', img.getAttribute('data-gallery-path'));
        return;
    }
    openLightbox(index);
});
```

### Console output
- Alt+click on any gallery image logs `Gallery path: <relative-path>` to the F12 console
- No toast, no clipboard — the user copies the path from the console manually

### Scope
- Works on direct images in the gallery grid (the `<img>` elements inside `.gallery-item` divs)
- Does NOT apply to folder preview thumbnails (`.gallery-item.folder img`) — those don't have `data-gallery-path` since they're generated thumbnails, not source images
- Alt+click on a folder card does nothing special (normal navigation)

---

## 3. `--apply-covers` CLI Flag

**File:** `generate_gallery.py`

### New argument
```python
parser.add_argument(
    '--apply-covers',
    metavar='FILE',
    help='Apply folder covers from a text file (one relative path per line)'
)
```

### New function: `apply_covers(root_path, covers_file)`
- Opens `covers_file`, reads line by line
- For each line:
  - Strips whitespace
  - Skips empty lines and lines starting with `#` (comments)
  - Normalizes path separators (forward slashes)
  - Splits into directory + filename:
    - `dir_part = os.path.dirname(line)` → the gallery subdirectory
    - `file_part = os.path.basename(line)` → the cover image
  - Resolves: `cover_dir = os.path.join(root_path, dir_part)`
  - Validates:
    - `cover_dir` exists as a directory
    - The image file exists at `os.path.join(cover_dir, file_part)`
    - The image extension is in `IMAGE_EXTENSIONS`
  - Writes `{cover_dir}/.folder_cover` containing `file_part`
  - Tracks: updated count, skipped count (with reasons)
- Prints a summary:
  ```
  Applied covers from mycovers.txt:
    Updated: 5 folder(s)
    Skipped: 1 (file not found)
  ```

### Execution flow
- If `--apply-covers` is provided, run `apply_covers()` first, then proceed to generate the gallery

---

## 4. Cleanup Orphaned `.folder_cover` Files

**File:** `cleanup_gallery.py`

### New function: `cleanup_folder_covers(dirpath)`
- Looks for `{dirpath}/.folder_cover`
- If it exists:
  - Reads the content (relative path)
  - Resolves against `dirpath`
  - Checks if the resolved file exists and has a valid image extension
  - If the image is missing or invalid, returns the `.folder_cover` path as orphaned
- Returns a list of orphaned `.folder_cover` paths (0 or 1 per directory)

### Integration into orphan cleanup walk
- After the `.thumbs/` and `.lr/` cleanup blocks, add a `.folder_cover` check

### Integration into the deletion pass
- Same walk, same check, delete the orphaned `.folder_cover` files

### Summary reporting
- Add `total_covers_deleted` counter
- Include in the final summary:
  ```
  Summary:
    Source files found: 1234
    Thumbnails found: 2468 (12 orphaned)
    LR files found: 500 (3 orphaned)
    Folder covers found: 50 (2 orphaned)
    Total size to free: 0.45 MB
  ```

### `--all` mode
- `.folder_cover` files are NOT deleted by `--all` — they are user configuration, not auto-generated output.

---

## 5. Edge Cases and Validation

### `get_folder_cover` / `ensure_folder_cover`
- `.folder_cover` contains a path to an image in a subdirectory (e.g., `vacation/photo.jpg`) — resolves correctly
- `.folder_cover` contains a path to a non-image file — returns `None`, falls through to default
- `.folder_cover` contains an absolute path — rejects it (only relative paths allowed)
- `.folder_cover` is empty or contains only whitespace — returns `None`
- Multiple images with the same name in different subdirectories — path disambiguates correctly

### Alt+click
- User alt+clicks an image — path logged to console, lightbox does NOT open
- User alt+clicks a folder preview thumbnail — no action (no `data-gallery-path`)

### `--apply-covers`
- File doesn't exist — prints error, exits with code 1
- Line references an image outside the gallery root — skips with warning
- Same image referenced multiple times — overwrites (last wins), no error
- Windows paths with backslashes — normalizes to forward slashes before processing

### Cleanup
- `.folder_cover` points to an image that was deleted — detected as orphaned, deleted
- `.folder_cover` points to a valid image that moved — detected as orphaned, deleted (generator will recreate on next run)

---

## 6. File Change Summary

| File | Changes |
|---|---|
| `generate_gallery.py` | New functions: `get_folder_cover()`, `ensure_folder_cover()`, `apply_covers()`. Modified: subdirectory loop, `generate_html()` entry, argument parser. Embedded JS: alt+click check inside image click handler, `data-gallery-path` on `<img>` tags. Folder links use `index.html` |
| `cleanup_gallery.py` | New function: `cleanup_folder_covers()`. Modified: orphan walk, deletion pass, summary output |
| `README.md` | Document `.folder_cover` format, alt+click workflow, `--apply-covers` usage |

---

## 7. Implementation Order (Complete)

1. ~~`get_folder_cover()` + `ensure_folder_cover()` in `generate_gallery.py`~~ ✅
2. ~~Integrate into subdirectory loop and `generate_html()`~~ ✅
3. ~~`--apply-covers` CLI flag + `apply_covers()` function~~ ✅
4. ~~Alt+click JS (console.log) in embedded template~~ ✅
5. ~~`cleanup_folder_covers()` in `cleanup_gallery.py`~~ ✅
6. ~~Integration into cleanup walk + summary~~ ✅
7. ~~README documentation~~ ✅
8. ~~Manual testing with sample gallery structure~~ ✅
9. ~~Fix folder links to use `index.html` (breadcrumbs, folder cards, sibling nav)~~ ✅