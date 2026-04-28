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

## Cleanup

Remove orphaned thumbnail and LR files:

```bash
python cleanup_gallery.py galleries/
python cleanup_gallery.py galleries/ --dry-run  # Preview only
python cleanup_gallery.py galleries/ --all      # Remove all generated files
```

## Structure

Each directory generates an `index.html` with:
- Inline slideshow data (no external JSON files)
- Preloaded image transitions (no flicker)
- Breadcrumb navigation with relative paths
- Thumbnail grid with lightbox preview

## Supported Formats

Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.heic`, `.heif`
