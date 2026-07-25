# simpleGraphy

Python-based static HTML photo gallery generator.

## Features

- **Recursive directory browsing** - Navigate through nested photo folders
- **Thumbnail generation** - Automatic thumbnail creation from source images
- **Lightroom optimization** - Optional LR-enhanced image generation for high-contrast scenes
- **Exif data display** - View camera settings in lightbox
- **Slideshow modes**:
  - Sequential: Full recursive traversal with directory navigation
  - Random: Random shuffle with configurable depth
- **Folder covers** - Control which image represents each folder
- **Responsive design** - Works on desktop and mobile
- **Browser caching** - Optimized with cache headers

## Usage

```bash
# Basic gallery generation
python generate_gallery.py galleries/

# With slideshow and random modes
python generate_gallery.py galleries/ --slideshow --random --random-depth 5

# Force regeneration (rebuild all thumbnails)
python generate_gallery.py galleries/ --force
```

## CLI Options

| Option | Description |
|--------|-------------|
| `root` | Gallery root directory (default: galleries) |
| `--slideshow` | Enable slideshow features |
| `--random` | Enable random slideshow mode |
| `--random-depth N` | Max recursion depth for random slideshow (default: unlimited) |
| `--force` | Force rebuild of all thumbnails |
| `--thumb-size N` | Thumbnail width in pixels (default: 400) |
| `--apply-covers FILE` | Apply folder covers from a text file |

## Folder Covers

Each directory can have a `.folder_cover` file that specifies which image represents the folder in the gallery. The file contains a relative path to the cover image.

### Auto-generation

When running `generate_gallery.py`, `.folder_cover` files are automatically created for directories that don't have one. The default cover is the first image in the directory (or the first image found recursively).

### Changing a Cover (Browser)

1. Open the gallery page containing the image you want as a cover
2. Hold **Alt** and **click** the image
3. The relative path is logged to the F12 console (`Gallery path: ...`)
4. Copy the path from the console into a text file, one per line
5. Apply with: `python generate_gallery.py galleries/ --apply-covers mycovers.txt`

### `.folder_cover` Format

A plain text file containing a single relative path to an image:
```
vacation/beach_sunset.jpg
```

### `--apply-covers`

Apply multiple folder covers at once from a text file. Supports comments (`#`) and blank lines:

```
# My custom covers
2024/vacation/beach_sunset.jpg
2024/family/birthday_cake.jpg
```

## Cleanup

Remove orphaned thumbnail, LR, and folder cover files:

```bash
python cleanup_gallery.py galleries/
python cleanup_gallery.py galleries/ --dry-run  # Preview only
python cleanup_gallery.py galleries/ --all      # Remove all generated files
```

Note: `--all` does NOT delete `.folder_cover` files (they are user configuration).

## Structure

Each directory generates an `index.html` with:
- Inline slideshow data (no external JSON files)
- Preloaded image transitions (no flicker)
- Breadcrumb navigation with relative paths
- Thumbnail grid with lightbox preview
- `.folder_cover` for controlling folder preview images

## Supported Formats

Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.heic`, `.heif`
