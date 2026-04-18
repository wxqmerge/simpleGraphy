#!/usr/bin/env python3
"""
Gallery Generator - Creates responsive photo galleries with thumbnails and lightbox viewer.

Usage:
    python generate_gallery.py galleries/
    python generate_gallery.py galleries/ --thumb-size 400 --force
    python generate_gallery.py galleries/ --slideshow
    python generate_gallery.py galleries/ --random --random-depth 2

Arguments:
    --root, -r          Root directory to scan (default: galleries)
    --output-root, -o   Where to write index.html files (default: same as --root)
    --thumb-size, -t    Max thumbnail dimension in pixels (default: 400)
    --force, -f         Force rebuild all thumbnails even if they exist
    --slideshow         Enable sequential slideshow (embeds current-dir images)
    --random            Enable random slideshow (embeds recursive image pool)
    --random-depth      Max recursion depth for random pool (default: unlimited)
"""

import argparse
import os
import html
import json
import warnings
import sys
from io import StringIO
from pathlib import Path
from datetime import datetime
from PIL import Image, ExifTags

# Increase max image pixels to handle panoramas
Image.MAX_IMAGE_PIXELS = 500_000_000


# Register HEIF support if available
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    try:
        import piheif
        piheif.register()
        HEIF_SUPPORT = True
    except ImportError:
        HEIF_SUPPORT = False


# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif'}

# Excluded directories (not included in galleries)
EXCLUDED_DIRS = {'.thumbs', '.lr', '.git', '__pycache__', 'node_modules'}


def format_size(size_bytes):
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_dir_size(dir_path):
    """Get total size of all files in a directory (non-recursive)."""
    total = 0
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total


def get_recursive_dir_size(dir_path, excluded_dirs=None):
    """Get total size of all files recursively."""
    if excluded_dirs is None:
        excluded_dirs = set()
    total = 0
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir() and entry.name not in excluded_dirs:
                total += get_recursive_dir_size(entry.path, excluded_dirs)
    except (PermissionError, OSError):
        pass
    return total


def count_files_recursive(dir_path, pattern=None, excluded_dirs=None):
    """Count files recursively matching optional pattern."""
    if excluded_dirs is None:
        excluded_dirs = set()
    count = 0
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                if pattern is None or entry.name.endswith(pattern):
                    count += 1
            elif entry.is_dir() and entry.name not in excluded_dirs:
                count += count_files_recursive(entry.path, pattern, excluded_dirs)
    except (PermissionError, OSError):
        pass
    return count


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate responsive photo galleries with thumbnails and lightbox viewer.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_gallery.py galleries/
  python generate_gallery.py galleries/ --thumb-size 250
  python generate_gallery.py galleries/ --output-root public/galleries/ --force
  python generate_gallery.py galleries/ --slideshow
  python generate_gallery.py galleries/ --random --random-depth 2

Output Structure:
   Each directory with images gets an index.html and .thumbs/ subdirectory.
   Thumbnails are 400px max dimension JPG files (HEIF converted automatically).
         """
    )
    
    parser.add_argument(
        'root',
        nargs='?',
        default='galleries',
        help='Root directory to scan for images (default: galleries)'
    )
    
    parser.add_argument(
        '--output-root', '-o',
        default=None,
        help='Where to write index.html files (default: same as --root)'
    )
    
    parser.add_argument(
        '--thumb-size', '-t',
        type=int,
        default=400,
        help='Maximum thumbnail dimension in pixels (default: 400)'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force rebuild all thumbnails even if they exist'
    )
    
    parser.add_argument(
        '--slideshow',
        action='store_true',
        help='Enable sequential slideshow (embeds current directory images)'
    )
    
    parser.add_argument(
        '--random',
        action='store_true',
        help='Enable random slideshow (embeds recursive image pool)'
    )
    
    parser.add_argument(
        '--random-depth', '-d',
        type=int,
        default=None,
        help='Max recursion depth for random pool (default: unlimited)'
    )
    
    return parser.parse_args()


def get_image_files(directory):
    """Get list of image files in directory (not subdirectories)."""
    images = []
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                ext = Path(entry.path).suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    images.append(entry.path)
    except PermissionError as e:
        print(f"  [WARN] Permission denied: {directory}")
    except OSError as e:
        print(f"  [WARN] Error scanning {directory}: {e}")
    
    return sorted(images, key=lambda x: os.path.basename(x).lower())


def get_subdirectories(directory):
    """Get list of subdirectories (excluding excluded dirs)."""
    dirs = []
    try:
        for entry in os.scandir(directory):
            if entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                dirs.append(entry.path)
    except PermissionError as e:
        print(f"  [WARN] Permission denied: {directory}")
    
    return sorted(dirs, key=lambda x: os.path.basename(x).lower())


def get_slideshow_images(directory, output_dir):
    """Collect images from current directory only (non-recursive).
    Returns list of dicts with image paths and metadata."""
    images = []
    
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                ext = Path(entry.path).suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    base_name = Path(entry.name).stem
                    
                    # Determine lightbox source (LR if available)
                    lr_dir = Path(output_dir) / '.lr'
                    lr_file = lr_dir / f"{base_name}_LR.jpg"
                    
                    rel_full = entry.name
                    lightbox_src = f'.lr/{base_name}_LR.jpg' if lr_file.exists() else rel_full
                    
                    images.append({
                        'full': lightbox_src,
                        'fullRes': rel_full,
                        'filename': entry.name
                    })
    except (PermissionError, OSError):
        pass
    
    return sorted(images, key=lambda x: x['filename'].lower())


def get_subdirectory_list(directory):
    """Get list of subdirectories for slideshow traversal."""
    dirs = []
    
    try:
        for entry in os.scandir(directory):
            if entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                dirs.append(entry.name)
    except (PermissionError, OSError):
        pass
    
    return sorted(dirs)


def collect_dirs_with_images(root_path):
    """Collect all subdirectories with images or children in DFS order (excludes root)."""
    result = []
    
    def scan(path):
        # Don't add the root directory itself
        if path != root_path:
            has_direct = bool(get_image_files(path))
            has_children = False
            try:
                for d in os.listdir(path):
                    if d not in EXCLUDED_DIRS:
                        full_path = os.path.join(path, d)
                        if os.path.isdir(full_path):
                            has_children = True
                            break
            except (PermissionError, OSError):
                pass
            if has_direct or has_children:
                result.append(path)
        try:
            dirs = sorted(os.listdir(path))
            for d in dirs:
                if d not in EXCLUDED_DIRS:
                    full_path = os.path.join(path, d)
                    if os.path.isdir(full_path):
                        scan(full_path)
        except (PermissionError, OSError):
            pass
    
    scan(root_path)
    return result


def get_sibling_nav(current_dir, all_dirs_with_images, root_path):
    """Get prev/next paths - sibling only navigation at all levels.
    
    Navigation rules:
      prev = previous sibling directory, or parent if no previous sibling
      next = next sibling directory, or parent if no next sibling
    """
    current_abs = os.path.abspath(current_dir)
    root_abs = os.path.abspath(root_path)
    
    def get_siblings(dir_abs):
        """Get all sibling directories (sorted by name)."""
        parent = os.path.dirname(dir_abs)
        try:
            entries = sorted(os.listdir(parent), key=lambda x: x.lower())
        except (PermissionError, OSError):
            return []
        result = []
        for e in entries:
            if e in EXCLUDED_DIRS:
                continue
            full = os.path.join(parent, e)
            if os.path.isdir(full):
                result.append(full)
        return result
    
    siblings = get_siblings(current_abs)
    
    # Find current index in siblings
    try:
        idx = [os.path.abspath(s) for s in siblings].index(current_abs)
    except ValueError:
        return '', ''
    
    # Next sibling
    next_path = ''
    if idx + 1 < len(siblings):
        next_path = os.path.relpath(siblings[idx + 1], current_dir).replace(os.sep, '/') + '/'
    
    # Prev sibling - find previous sibling, or go to parent if none
    prev_path = ''
    if idx > 0:
        prev_path = os.path.relpath(siblings[idx - 1], current_dir).replace(os.sep, '/') + '/'
    else:
        # No previous sibling at this level - parent is the prev
        parent = os.path.dirname(current_abs)
        if parent and parent != root_abs:
            prev_path = os.path.relpath(parent, current_dir).replace(os.sep, '/') + '/'
    
    return prev_path, next_path


def generate_slideshow_json(directory, output_dir):
    """Generate slideshow.json for a directory."""
    json_data = {
        'images': get_slideshow_images(directory, output_dir),
        'subdirs': get_subdirectory_list(directory)
    }
    
    json_file = os.path.join(output_dir, 'slideshow.json')
    
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, separators=(',', ':'))
        return True
    except IOError as e:
        print(f"  [ERROR] Failed to write {json_file}: {e}")
        return False


def get_random_pool(root_dir, output_root, max_depth=None):
    """Collect all images recursively for random slideshow.
    
    Args:
        root_dir: Root directory to start from
        output_root: Output root for path calculation
        max_depth: Maximum recursion depth (None = unlimited)
    
    Returns:
        List of dicts with 'full', 'fullRes', 'filename'
    """
    pool = []
    
    def collect_recursive(dir_path, rel_prefix='', depth=0):
        if max_depth is not None and depth > max_depth:
            return
            
        for entry in os.scandir(dir_path):
            if entry.is_file():
                ext = Path(entry.path).suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    base_name = Path(entry.name).stem
                    
                    # Determine lightbox source (LR if available)
                    lr_dir = Path(output_root) / rel_prefix.strip('/') / '.lr'
                    lr_file = lr_dir / f"{base_name}_LR.jpg"
                    
                    rel_full = os.path.relpath(entry.path, output_root).replace(os.sep, '/')
                    lightbox_src = f"{rel_prefix}.lr/{base_name}_LR.jpg" if lr_file.exists() else rel_full
                    
                    pool.append({
                        'full': lightbox_src,
                        'fullRes': rel_full,
                        'filename': entry.name
                    })
            elif entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                new_prefix = rel_prefix + entry.name + '/'
                collect_recursive(entry.path, new_prefix, depth + 1)
    
    try:
        collect_recursive(root_dir)
    except (PermissionError, OSError):
        pass
    
    return pool


def get_exif_data(image_path):
    """Extract EXIF data from image file."""
    exif_data = {
        'width': 0,
        'height': 0,
        'filesize': '',
        'copyright': '',
        'camera': '',
        'focal_length': '',
        'orientation': 1  # Default: no rotation needed
    }
    
    try:
        # Get file size
        file_size = Path(image_path).stat().st_size
        if file_size >= 1_000_000:
            exif_data['filesize'] = f'{file_size / 1_000_000:.1f} MB'
        elif file_size >= 1_000:
            exif_data['filesize'] = f'{file_size / 1_000:.0f} KB'
        else:
            exif_data['filesize'] = f'{file_size} B'
        
        with Image.open(image_path) as img:
            exif_data['width'] = img.width
            exif_data['height'] = img.height
            
            # Load EXIF data fully (required for some images)
            if hasattr(img, 'load_end'):
                try:
                    img.load_end()
                except:
                    pass
            
            # Get EXIF tags
            exif_dict = None
            if hasattr(img, 'getexif'):
                try:
                    exif_dict = img.getexif()
                except:
                    pass
            
            if exif_dict:
                try:
                    if len(exif_dict) == 0:
                        exif_dict = None
                except TypeError:
                    # If getexif() returns something without __len__, skip it
                    exif_dict = None
            
            if exif_dict:
                # Copyright (tag 33432)
                copyright_tag = exif_dict.get(33432)
                if copyright_tag:
                    exif_data['copyright'] = str(copyright_tag)
                
                # Camera info (Make = tag 271, Model = tag 272)
                make = exif_dict.get(271)
                model = exif_dict.get(272)
                if make and model:
                    exif_data['camera'] = f'{make} {model}'
                elif model:
                    exif_data['camera'] = str(model)
                elif make:
                    exif_data['camera'] = str(make)
                
                # Focal length (tag 37386) and 35mm equiv (tag 42035)
                focal_35 = exif_dict.get(42035)
                focal = exif_dict.get(37386)
                
                # Helper to convert EXIF fraction tuple to float
                def parse_focal(val):
                    if isinstance(val, (tuple, list)) and len(val) >= 2:
                        try:
                            return val[0] / val[1]
                        except:
                            return None
                    try:
                        return float(val)
                    except:
                        return None
                
                fl_35 = parse_focal(focal_35)
                fl = parse_focal(focal)
                
                if fl_35 is not None:
                    exif_data['focal_length'] = f'{fl_35:.0f}mm (35mm equiv)'
                elif fl is not None:
                    exif_data['focal_length'] = f'{fl:.0f}mm'
                
                # Orientation tag (tag 274) - critical for proper display
                orientation = exif_dict.get(274, 1)
                exif_data['orientation'] = orientation if orientation else 1
                        
    except Exception as e:
        pass
    
    return exif_data


def should_rebuild(source_path, thumb_path, force):
    """Check if thumbnail needs to be rebuilt."""
    if force:
        return True
    
    if not thumb_path.exists():
        return True
    
    source_mtime = Path(source_path).stat().st_mtime
    thumb_mtime = thumb_path.stat().st_mtime
    
    return source_mtime > thumb_mtime


def apply_orientation(img, orientation):
    """Apply EXIF orientation transformation to image."""
    if orientation == 1:
        return img  # Normal, no transform needed
    elif orientation == 2:
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 3:
        return img.rotate(180, expand=False)
    elif orientation == 4:
        return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    elif orientation == 5:
        return img.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 6:
        return img.transpose(Image.Transpose.ROTATE_270)
    elif orientation == 7:
        return img.transpose(Image.Transpose.ROTATE_90).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 8:
        return img.transpose(Image.Transpose.ROTATE_90)
    return img


def needs_lr_version(source_path, width, height):
    """Check if image needs a low-res version."""
    is_heif = Path(source_path).suffix.lower() in {'.heic', '.heif'}
    dimension_sum = width + height
    
    # Need LR if h+w > 3000 or if it's a HEIF file
    return dimension_sum > 3000 or is_heif


def generate_lr_image(source_path, lr_dir, lr_size_max=2000):
    """Generate low-res version of image (h+w < 2000)."""
    try:
        source_path = Path(source_path)
        base_name = source_path.stem
        ext = source_path.suffix.lower()
        
        # Create LR filename with _LR suffix
        lr_name = f"{base_name}_LR.jpg"
        lr_path = lr_dir / lr_name
        
        if not lr_path.exists():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=Image.DecompressionBombWarning)
                with Image.open(source_path) as img:
                    # Load and apply orientation
                    orientation = 1
                    try:
                        if hasattr(img, 'load_end'):
                            img.load_end()
                        if hasattr(img, 'getexif'):
                            exif_dict = img.getexif()
                            if exif_dict:
                                orientation = exif_dict.get(274, 1)
                                if orientation == 0:
                                    orientation = 1
                    except:
                        pass
                    
                    img = apply_orientation(img, orientation)
                    
                    # Convert to RGB
                    if img.mode in ('RGBA', 'P', 'LA'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Scale down to max h+w = 3000
                    width, height = img.size
                    dimension_sum = width + height
                    
                    if dimension_sum > lr_size_max:
                        scale = lr_size_max / dimension_sum
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Ensure LR directory exists
                    lr_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Save as JPEG
                    img.save(lr_path, 'JPEG', quality=85, optimize=True)
            
            return True
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to create LR for {source_path.name}: {e}")
        return False


def generate_thumbnail(source_path, thumb_path, thumb_size):
    """Generate thumbnail from source image."""
    try:
        # Convert to Path objects if strings
        if isinstance(thumb_path, str):
            thumb_path = Path(thumb_path)
        if isinstance(source_path, str):
            source_path = Path(source_path)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=Image.DecompressionBombWarning)
            with Image.open(source_path) as img:
                # Load EXIF and get orientation
                orientation = 1
                try:
                    if hasattr(img, 'load_end'):
                        img.load_end()
                    
                    if hasattr(img, 'getexif'):
                        exif_dict = img.getexif()
                        if exif_dict:
                            orientation = exif_dict.get(274, 1)  # Tag 274 is Orientation
                            # Treat 0 as 1 (normal orientation)
                            if orientation == 0:
                                orientation = 1
                except Exception as e:
                    # If EXIF parsing fails, use default orientation
                    pass
                
                # Apply orientation transformation
                img = apply_orientation(img, orientation)
                
                # Skip extremely large images (panoramas > 100MP)
                if img.width * img.height > 1000_000_000:
                    print(f"    [SKIP] Very large image: {os.path.basename(source_path)} ({img.width}x{img.height})")
                    # Still create a small thumbnail
                    img = img.resize((thumb_size, int(thumb_size * img.height / img.width)), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary (for JPEG output)
                if img.mode in ('RGBA', 'P', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Clamp aspect ratio to 2:1 (landscape) or 1:2 (portrait)
                width, height = img.size
                aspect_ratio = width / height
                
                if aspect_ratio > 2.0:
                    # Too wide - crop to 2:1
                    new_width = int(height * 2)
                    left = (width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, height))
                elif aspect_ratio < 0.5:
                    # Too tall - crop to 1:2
                    new_height = int(width * 2)
                    top = (height - new_height) // 2
                    img = img.crop((0, top, width, top + new_height))
                
                # Calculate new size maintaining aspect ratio
                img.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                
                # Ensure thumbnail directory exists
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save as JPEG with good quality (EXIF stripped automatically by not including it)
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
                
                return True
                
    except Exception as e:
        import traceback
        print(f"  [ERROR] Failed to create thumbnail for {os.path.basename(source_path)}: {e}")
        traceback.print_exc()
        return False


def generate_html(directory, output_dir, root_path, thumb_size, force=False, parent_path=None, random_depth=None, enable_slideshow=False, enable_random=False, browse_prev='', browse_next=''):
    """Generate index.html for a directory."""
    images = get_image_files(directory)
    subdirs = get_subdirectories(directory)
    
    # Skip if no images and no subdirectories
    if not images and not subdirs:
        return False
    
    dir_name = os.path.basename(directory.rstrip('/')) or 'Gallery'
    dir_name_safe = html.escape(dir_name)
    
    # Build breadcrumb navigation
    rel_path = os.path.relpath(directory, root_path).replace('\\', '/')
    if rel_path == '.':
        breadcrumbs = [{'name': 'Root', 'link': './'}]
    else:
        parts = [p for p in rel_path.split('/') if p]
        current_depth = len(parts)
        # Root goes to parent of root_path
        breadcrumbs = [{'name': 'Root', 'link': '../' * current_depth}]
        for i, part in enumerate(parts):
            # Each intermediate link: go up to ancestor depth, landing exactly at it
            breadcrumbs.append({
                'name': html.escape(part),
                'link': '../' * (current_depth - i - 1)
            })
    
    breadcrumb_html = ''
    for i, item in enumerate(breadcrumbs):
        if i < len(breadcrumbs) - 1:
            # Add link with separator after (except for last item)
            breadcrumb_html += f'<a href="{item["link"]}">{item["name"]}</a>/'
        else:
            # Last item is current, no link, no separator after
            breadcrumb_html += f'<span class="current">{item["name"]}</span>'
    
    # Generate image grid items
    image_items = []
    thumbs_dir = os.path.join(output_dir, '.thumbs')
    os.makedirs(thumbs_dir, exist_ok=True)
    
    for img_path in images:
        basename = os.path.basename(img_path)
        thumb_name = Path(basename).stem + '_thumb.jpg'
        thumb_path = Path(thumbs_dir) / thumb_name
        
        if should_rebuild(img_path, thumb_path, force):
            generate_thumbnail(img_path, thumb_path, thumb_size)
        
        rel_thumb = f'.thumbs/{thumb_name}'
        rel_full = os.path.relpath(img_path, output_dir).replace(os.sep, '/')
        safe_basename = html.escape(basename)
        
        # Get EXIF data
        exif = get_exif_data(img_path)
        exif_json = json.dumps(exif)
        # Escape HTML special characters for safe embedding in HTML attributes
        exif_json = (exif_json
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))
        
        # Determine if landscape (width > height after orientation is applied)
        width = exif.get('width', 0)
        height = exif.get('height', 0)
        orientation = exif.get('orientation', 1)
        
        # Account for EXIF orientation in aspect ratio calculation
        display_width = width
        display_height = height
        if orientation in [5, 6, 7, 8]:
            display_width, display_height = height, width
        
        is_landscape = display_width > display_height if (display_width and display_height) else False
        item_class = 'gallery-item landscape' if is_landscape else 'gallery-item portrait'
        
        # Check if LR version is needed and generate it
        lr_dir = Path(output_dir) / '.lr'
        rel_lr = None
        
        if needs_lr_version(img_path, width, height):
            generate_lr_image(img_path, lr_dir)
            base_name = Path(basename).stem
            lr_name = f"{base_name}_LR.jpg"
            if (lr_dir / lr_name).exists():
                rel_lr = f'.lr/{lr_name}'
        
        # Use LR for lightbox if available, otherwise use full
        lightbox_src = rel_lr if rel_lr else rel_full
        
        image_items.append(f'''
            <div class="{item_class}">
                <img src="{rel_thumb}" alt="{safe_basename}" data-full="{lightbox_src}" data-full-res="{rel_full}" data-exif="{exif_json}">
                <div class="overlay">
                    <span class="filename">{safe_basename}</span>
                </div>
            </div>''')
    
    # Generate subdirectory items
    subdir_items = []
    for subdir in subdirs:
        subdir_name = os.path.basename(subdir)
        subdir_path = os.path.relpath(subdir, output_dir).replace(os.sep, '/') + '/'
        safe_subdir_name = html.escape(subdir_name)
        
        # Count photos and sub-albums recursively
        photo_count = 0
        album_count = 0
        
        def count_recursive(path):
            nonlocal photo_count, album_count
            for entry in os.scandir(path):
                if entry.is_file():
                    ext = Path(entry.path).suffix.lower()
                    if ext in IMAGE_EXTENSIONS:
                        photo_count += 1
                elif entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                    album_count += 1
                    count_recursive(entry.path)
        
        try:
            count_recursive(subdir)
        except (PermissionError, OSError):
            pass
        
        # Generate a preview thumbnail for the directory
        # First try images in current folder
        subdir_images = get_image_files(subdir)
        source_image = None
        
        if subdir_images:
            source_image = subdir_images[0]
        else:
            # Recursively find first image in subfolders
            def find_first_image(path, depth=0):
                if depth > 3:  # Limit recursion depth
                    return None
                for entry in os.scandir(path):
                    if entry.is_file():
                        ext = Path(entry.path).suffix.lower()
                        if ext in IMAGE_EXTENSIONS:
                            return entry.path
                    elif entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                        result = find_first_image(entry.path, depth + 1)
                        if result:
                            return result
                return None
            
            try:
                source_image = find_first_image(subdir)
            except (PermissionError, OSError):
                pass
        
        rel_thumb = None
        if source_image:
            thumb_name = Path(os.path.basename(source_image)).stem + '_dir_thumb.jpg'
            thumb_path = Path(thumbs_dir) / thumb_name
            
            if should_rebuild(source_image, thumb_path, force):
                generate_thumbnail(source_image, thumb_path, thumb_size)
            
            rel_thumb = f'.thumbs/{thumb_name}'
        
        preview_html = ''
        if rel_thumb:
            preview_html = f'<img src="{rel_thumb}" alt="Preview">'
        
        stats_text = f'{photo_count} photo{"s" if photo_count != 1 else ""}, {album_count} album{"s" if album_count != 1 else ""}'
        
        subdir_items.append(f'''
            <div class="gallery-item folder" onclick="window.location.href='{subdir_path}'">
                {preview_html}
                <div class="folder-overlay">
                    <span class="folder-name">{safe_subdir_name}</span>
                    <span class="folder-stats">{stats_text}</span>
                </div>
            </div>''')
    
    # Count items for display
    total_images = len(images)
    total_folders = len(subdir_items)
    
    # Sequential slideshow: recursive pool (all images in order)
    if enable_slideshow:
        sequential_images = get_slideshow_images(directory, output_dir)
        subdirs_list = get_subdirectory_list(directory)
        # Use recursive pool for full traversal (same as random but sequential)
        sequential_recursive_pool = get_random_pool(directory, output_dir, max_depth=random_depth) if enable_random else get_random_pool(directory, output_dir)
        sequential_recursive_json = json.dumps(sequential_recursive_pool, separators=(',', ':'))
        # Also embed current dir images for immediate display
        sequential_json = json.dumps(sequential_images, separators=(',', ':'))
    else:
        sequential_images = []
        sequential_json = '[]'
        subdirs_list = []
        sequential_recursive_pool = []
        sequential_recursive_json = '[]'
    
    # Random slideshow pool: recursive from this directory
    if enable_random:
        random_pool = get_random_pool(directory, output_dir, max_depth=random_depth)
        random_json = json.dumps(random_pool, separators=(',', ':'))
    else:
        random_pool = []
        random_json = '[]'
    
    # Build gallery grid HTML
    grid_html = ''.join(subdir_items + image_items)
    
   # Pre-compute slideshow elements to avoid nested f-string issues (Python 3.10)
    slideshow_header_html = ''
    slideshow_header_block = ''
    if enable_slideshow and (sequential_images or sequential_recursive_pool):
        seq_count = len(sequential_recursive_pool) if sequential_recursive_pool else len(sequential_images)
        slideshow_header_html += '<button class="slideshow-btn" onclick="startSlideshow(\'sequential\')">▶ Slideshow (' + str(seq_count) + ')</button>'
    if random_pool:
        slideshow_header_html += '<button class="slideshow-btn random-btn" onclick="startSlideshow(\'random\')">🎲 Random (' + str(len(random_pool)) + ')</button>'
    if slideshow_header_html:
        slideshow_header_block = '''        <div class="slideshow-header">
                ''' + slideshow_header_html + '''
                <div class="slideshow-options">
                    <label><input type="checkbox" id="fullres-check"> Full Res</label>
                </div>
            </div>'''
    
    # Pre-compute JS blocks to avoid nested f-string issues (Python 3.10)
    sequential_js_block = ''
    if enable_slideshow:
        sequential_js_block = '''// Sequential slideshow pool (all images for full traversal)
        const sequentialRecursivePoolData = ''' + sequential_recursive_json + ''';
        if (sequentialRecursivePoolData && sequentialRecursivePoolData.length > 0) {
            sequentialImageList = sequentialRecursivePoolData;
        }

        // Current directory images for immediate display
        let sequentialImageData = ''' + sequential_json + ''';
        
        // Subdirectories for depth-first traversal
        currentSubdirs = ''' + json.dumps(subdirs_list, separators=(',', ':')) + ''' || [];'''
    
    random_js_block = ''
    if enable_random:
        random_js_block = '''// Random slideshow pool (recursive from current dir)
        const randomPoolData = ''' + random_json + ''';
        if (randomPoolData) {
            randomPool = randomPoolData;
        }'''
    
   # Browse mode directory navigation (sibling-level)
    browse_dir_nav_block = ''
    if browse_prev or browse_next:
        browse_dir_nav_block = '''// Browse mode sibling directory navigation
        const browsePrevPath = ''' + json.dumps(browse_prev) + ''';
        const browseNextPath = ''' + json.dumps(browse_next) + ''';
        
        document.addEventListener('DOMContentLoaded', function() {
            const prevBtn = document.getElementById('browse-dir-prev');
            const nextBtn = document.getElementById('browse-dir-next');
            
            if (prevBtn) {
                if (!browsePrevPath) {
                    prevBtn.classList.add('disabled');
                } else {
                    prevBtn.addEventListener('click', function(e) {
                        e.preventDefault();
                        window.location.href = browsePrevPath;
                    });
                }
            }
            
            if (nextBtn) {
                if (!browseNextPath) {
                    nextBtn.classList.add('disabled');
                } else {
                    nextBtn.addEventListener('click', function(e) {
                        e.preventDefault();
                        window.location.href = browseNextPath;
                    });
                }
            }
        });'''
    
    # Generate complete HTML
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{dir_name_safe} - Gallery</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .header-main {{
            flex: 1;
            min-width: 200px;
        }}
        
        h1 {{
            font-size: 2em;
            margin-bottom: 15px;
            color: #fff;
        }}
        
        .browse-dir-nav {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }}
        
        .browse-dir-btn {{
            background: none;
            border: 1px solid #444;
            color: #4fc3f7;
            font-size: 1.2em;
            cursor: pointer;
            padding: 4px 8px;
            line-height: 1;
            opacity: 0.5;
            transition: opacity 0.2s, color 0.2s, border-color 0.2s;
            border-radius: 3px;
        }}
        
        .browse-dir-btn:hover {{
            opacity: 1;
            color: #fff;
            border-color: #4fc3f7;
        }}
        
        .browse-dir-btn.disabled {{
            visibility: hidden;
            pointer-events: none;
        }}
        
        .breadcrumbs {{
            color: #888;
            font-size: 0.9em;
        }}
        
        .breadcrumbs a {{
            color: #4fc3f7;
            text-decoration: none;
        }}
        
        .breadcrumbs a:hover {{
            text-decoration: underline;
        }}
        
        .breadcrumbs .current {{
            color: #888;
        }}
        
        .stats {{
            margin-top: 10px;
            color: #666;
            font-size: 0.9em;
        }}
        
        /* Slideshow button */
        .slideshow-btn {{
            display: inline-block;
            margin-top: 12px;
            padding: 8px 16px;
            background: rgba(79, 195, 247, 0.2);
            border: 1px solid #4fc3f7;
            color: #4fc3f7;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.2s;
        }}
        
        .slideshow-btn:hover {{
            background: rgba(79, 195, 247, 0.3);
        }}
        
        .slideshow-header {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        .slideshow-btn.random-btn {{
            background: rgba(108, 92, 231, 0.2);
            border-color: #6c5ce7;
            color: #a29bfe;
        }}
        
        .slideshow-btn.random-btn:hover {{
            background: rgba(108, 92, 231, 0.3);
        }}
        
        .slideshow-options {{
            display: flex;
            gap: 15px;
            align-items: center;
            font-size: 14px;
            color: var(--text-primary);
        }}
        
        .slideshow-options label {{
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        
        .slideshow-options input[type="checkbox"] {{
            cursor: pointer;
        }}
        
        .full-res-active .slideshow-progress::after {{
            content: ' [FULL RES]';
            color: #ffd700;
        }}
        
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            grid-auto-rows: auto;
            gap: 15px;
            padding-bottom: 20px;
        }}
        
        .gallery-item {{
            position: relative;
            border-radius: 8px;
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            background: #16213e;
        }}
        
        .gallery-item img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        .gallery-item:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4);
        }}
        
        /* Landscape items span 2 columns */
        .gallery-item.landscape {{
            grid-column: span 2;
        }}
        
        .gallery-item.folder {{
            cursor: pointer;
            background: #16213e;
            border: 2px solid #2a2a4e;
        }}
        
        .gallery-item.folder:hover {{
            border-color: #4fc3f7;
        }}
        
        .folder-overlay {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(transparent, rgba(0,0,0,0.9));
            padding: 40px 15px 12px;
            text-align: center;
        }}
        
        .folder-name {{
            display: block;
            font-size: 1em;
            font-weight: 600;
            color: #fff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.8);
            margin-bottom: 6px;
            word-break: break-word;
        }}
        
        .folder-stats {{
            display: block;
            font-size: 0.8em;
            color: #bbb;
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        }}
        
        .gallery-item.folder:hover {{
            border-color: #4fc3f7;
        }}
        
        .folder-content {{
            text-align: center;
        }}
        
        .folder-icon {{
            font-size: 3em;
            display: block;
            margin-bottom: 8px;
        }}
        
        .folder-name {{
            font-size: 0.9em;
            color: #ccc;
            word-break: break-word;
        }}
        
        .overlay {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(transparent, rgba(0,0,0,0.8));
            padding: 30px 10px 10px;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        
        .gallery-item:hover .overlay {{
            opacity: 1;
        }}
        
        .filename {{
            font-size: 0.8em;
            color: #fff;
            display: block;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        /* Lightbox Modal */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            z-index: 1000;
        }}
        
        .lightbox.active {{
            display: flex !important;
        }}
        
        .lightbox-content-wrapper {{
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        /* Landscape layout (EXIF on top) */
        .lightbox.landscape .lightbox-content-wrapper {{
            flex-direction: column;
        }}
        
        .lightbox.landscape .lightbox-exif {{
            width: 100%;
            padding: 15px 40px;
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            min-height: 60px;
            background: rgba(0, 0, 0, 0.7);
        }}
        
        .lightbox.landscape .lightbox-image-container {{
            width: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding-bottom: 10px;
            flex-grow: 1;
        }}
        
        .lightbox.landscape .lightbox-image-container img {{
            max-width: 90vw !important;
            max-height: calc(75vh - 80px) !important;
            width: auto !important;
            height: auto !important;
            display: block !important;
        }}
        
        /* Portrait layout (EXIF on left) */
        .lightbox.portrait .lightbox-content-wrapper {{
            flex-direction: row;
            align-items: flex-start;
        }}
        
        .lightbox.portrait .lightbox-exif {{
            width: 280px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.7);
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
        }}
        
        .lightbox.portrait .lightbox-image-container {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            flex: 1;
            min-width: 0;
            padding-left: 20px;
        }}
        
        .lightbox.portrait .lightbox-image-container img {{
            max-width: calc(70vw - 300px) !important;
            max-height: 85vh !important;
            width: auto !important;
            height: auto !important;
            display: block !important;
        }}
        
        /* Default image sizing - applies to all lightbox images */
        .lightbox-image-container img {{
            max-width: 100%;
            max-height: 90vh;
            width: auto;
            height: auto;
            display: block;
        }}
        
        .lightbox-close {{
            position: absolute;
            top: 20px;
            right: 30px;
            font-size: 3em;
            color: #fff;
            cursor: pointer;
            line-height: 1;
            z-index: 1001;
        }}
        
        .lightbox-close:hover {{
            color: #4fc3f7;
        }}
        
        /* Navigation arrows */
        .lightbox-nav {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: #fff;
            font-size: 3em;
            padding: 20px 15px;
            cursor: pointer;
            border-radius: 8px;
            transition: background 0.2s;
            z-index: 1001;
        }}
        
        .lightbox-nav:hover {{
            background: rgba(79, 195, 247, 0.3);
        }}
        
        .lightbox-nav.prev {{
            left: 20px;
        }}
        
        .lightbox-nav.next {{
            right: 20px;
        }}
        
        /* EXIF display */
        .lightbox-exif {{
            display: block;
            color: #fff;
            font-size: 0.9em;
            min-height: 60px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.7);
        }}
        
        .exif-header {{
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 15px;
            color: #4fc3f7;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 8px;
        }}
        
        .exif-item {{
            margin-bottom: 12px;
            padding: 4px 0;
            border-radius: 4px;
            transition: background 0.2s;
        }}
        
        .exif-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}
        
        .exif-item .label {{
            color: #888;
            font-weight: 500;
            display: inline-block;
            min-width: 80px;
        }}
        
        .exif-item .value {{
            color: #eee;
        }}
        
        /* Filename display below image */
        .lightbox-filename {{
            text-align: center;
            padding: 10px 0;
            color: #aaa;
            font-size: 0.85em;
            letter-spacing: 0.5px;
            white-space: nowrap;
            z-index: 1002;
        }}
        
        .full-res-hint {{
            color: #4fc3f7;
            font-size: 0.85em;
            margin-left: 8px;
            opacity: 0.9;
        }}
        
        /* Slideshow controls overlay */
        .slideshow-controls {{
            position: absolute;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            gap: 20px;
            background: rgba(0, 0, 0, 0.7);
            padding: 10px 20px;
            border-radius: 30px;
            z-index: 1002;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        
        .lightbox.slideshow-active .slideshow-controls {{
            opacity: 1;
        }}
        
        .slideshow-progress {{
            color: #fff;
            font-size: 0.9em;
            min-width: 80px;
            text-align: center;
        }}
        
        .slideshow-playpause {{
            background: none;
            border: none;
            color: #4fc3f7;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0 5px;
            line-height: 1;
        }}
        
        .slideshow-playpause:hover {{
            color: #fff;
        }}

        .slideshow-dir-nav {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .slideshow-dir-name {{
            color: #bbb;
            font-size: 0.85em;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            min-width: 60px;
        }}

        .slideshow-dir-btn {{
            background: none;
            border: none;
            color: #4fc3f7;
            font-size: 1.2em;
            cursor: pointer;
            padding: 0 2px;
            line-height: 1;
            opacity: 0.6;
            transition: opacity 0.2s, color 0.2s;
        }}

        .slideshow-dir-btn:hover {{
            opacity: 1;
            color: #fff;
        }}

        .slideshow-dir-btn.disabled {{
            visibility: hidden;
            pointer-events: none;
        }}
        
        /* Timer progress bar */
        .slideshow-timer-bar {{
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            background: #4fc3f7;
            width: 0%;
            transition: width 0.1s linear;
        }}
        
        .lightbox.slideshow-active {{
            cursor: default;
        }}
        
        /* EXIF orientation transforms */
        .lightbox-image-container img[data-orientation="6"] {{
            transform: rotate(90deg);
            transform-origin: center;
        }}
        
        .lightbox-image-container img[data-orientation="8"] {{
            transform: rotate(-90deg);
            transform-origin: center;
        }}
        
        .lightbox-image-container img[data-orientation="3"] {{
            transform: rotate(180deg);
            transform-origin: center;
        }}
        
        .lightbox-image-container img[data-orientation="4"] {{
            transform: scaleX(-1);
            transform-origin: center;
        }}
        
        .lightbox-image-container img[data-orientation="5"] {{
            transform: scaleY(-1);
            transform-origin: center;
        }}
        
        .lightbox-image-container img[data-orientation="7"] {{
            transform: rotate(-90deg) scaleX(-1);
            transform-origin: center;
        }}
        
        /* Adjust sizing for rotated images */
        .lightbox-image-container img[data-orientation="6"],
        .lightbox-image-container img[data-orientation="7"],
        .lightbox-image-container img[data-orientation="8"] {{
            /* Portrait orientation, swap max dimensions */
            max-width: calc(90vh - 120px) !important;
            max-height: calc(65vw - 200px) !important;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 15px;
            }}
            
            h1 {{
                font-size: 1.5em;
            }}
            
            .gallery-grid {{
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                gap: 10px;
            }}
            
            .lightbox-content img {{
                 max-height: 70vh;
             }}
             
             .lightbox.portrait .lightbox-image-container img {{
                 max-width: calc(55vw - 180px);
             }}
             
             .lightbox.portrait .lightbox-exif {{
                 width: 180px;
             }}
         }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-main">
                <div class="browse-dir-nav">
                    <button class="browse-dir-btn" id="browse-dir-prev" title="Previous Directory">&#8592;</button>
                    <h1>{dir_name_safe}</h1>
                    <button class="browse-dir-btn" id="browse-dir-next" title="Next Directory">&#8594;</button>
                </div>
                <nav class="breadcrumbs">{breadcrumb_html}</nav>
                <div class="stats">
                    {total_folders} folder{'s' if total_folders != 1 else ''}, 
                    {total_images} image{'s' if total_images != 1 else ''}
                </div>
            </div>
            {slideshow_header_block}
        </header>
        
        <div class="gallery-grid">
{grid_html if grid_html.strip() else '            <p style="color: #666; grid-column: 1/-1; text-align: center;">No images or folders found.</p>'}
        </div>
    </div>
    
   <!-- Lightbox Modal -->
    <div class="lightbox" id="lightbox">
        <span class="lightbox-close">&times;</span>
        <button class="lightbox-nav prev" id="prev-btn">&#10094;</button>
        <button class="lightbox-nav next" id="next-btn">&#10095;</button>
        
        <!-- Slideshow controls -->
        <div class="slideshow-controls" id="slideshow-controls">
            <span class="slideshow-progress" id="slideshow-progress">1 / 10</span>
            <div class="slideshow-dir-nav">
                <button class="slideshow-dir-btn" id="dir-prev-btn" title="Previous Directory">&#8592;</button>
                <span class="slideshow-dir-name" id="slideshow-dir-name"></span>
                <button class="slideshow-dir-btn" id="dir-next-btn" title="Next Directory">&#8594;</button>
            </div>
            <button class="slideshow-playpause" id="slideshow-playpause" title="Pause">⏸</button>
        </div>
        <div class="slideshow-timer-bar" id="slideshow-timer-bar"></div>
        
        <div class="lightbox-content-wrapper">
            <div class="lightbox-exif" id="lightbox-exif"></div>
            <div class="lightbox-image-container">
                <img id="lightbox-img" src="" alt="">
            </div>
            <div class="lightbox-filename" id="lightbox-filename"></div>
        </div>
    </div>
    
    <script>
        // HTML escape function for EXIF display
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        const lightbox = document.getElementById('lightbox');
        const lightboxImg = document.getElementById('lightbox-img');
        const lightboxExif = document.getElementById('lightbox-exif');
        const lightboxFilename = document.getElementById('lightbox-filename');
        const closeBtn = document.querySelector('.lightbox-close');
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        
       // Slideshow controls
        const slideshowControls = document.getElementById('slideshow-controls');
        const slideshowProgress = document.getElementById('slideshow-progress');
        const slideshowPlaypause = document.getElementById('slideshow-playpause');
        const slideshowTimerBar = document.getElementById('slideshow-timer-bar');
        const dirPrevBtn = document.getElementById('dir-prev-btn');
        const dirNextBtn = document.getElementById('dir-next-btn');
        const slideshowDirName = document.getElementById('slideshow-dir-name');
        
        // Image navigation state
        let imageList = [];
        let currentIndex = 0;
        
        // Slideshow state
        let sequentialImageList = [];
        let randomPool = [];
        let currentMode = null;
        let slideshowIndex = 0;
        let slideshowInterval = null;
        let slideshowPlaying = false;
        const SLIDESHOW_INTERVAL_MS = 3000;
        
       // Sequential traversal state (depth-first)
        let currentDirPath = '';
        let subdirQueue = [];
        let currentSubdirs = [];
        let subdirIndex = 0;
        const subdirCache = new Map();

        // Directory navigation (sequential mode)
        let dirNavList = [];
        let currentDirIndex = -1;
        
        // Options
        let useFullRes = false;
        
        // Build image list for navigation
        const images = document.querySelectorAll('.gallery-item img[data-full]');
        imageList = Array.from(images).map(img => ({{
            full: img.getAttribute('data-full'),
            fullRes: img.getAttribute('data-full-res'),
            exif: img.getAttribute('data-exif'),
            filename: img.alt || ''
        }}));
        
       {sequential_js_block}
         
         {random_js_block}
         
         {browse_dir_nav_block}
         
         // Set lightbox orientation based on image dimensions
        function setOrientation(width, height) {{
            if (height > width) {{
                lightbox.classList.add('portrait');
                lightbox.classList.remove('landscape');
            }} else {{
                lightbox.classList.add('landscape');
                lightbox.classList.remove('portrait');
            }}
        }}
        
        // Open lightbox with full HD image at specific index
        function openLightbox(index) {{
            if (index < 0 || index >= imageList.length) return;
            
            currentIndex = index;
            const imageData = imageList[currentIndex];
            
            // Clear previous state but keep 'active' off until image loads
            lightbox.classList.remove('active', 'portrait', 'landscape');
            
            // Set default to landscape until orientation is determined
            lightbox.classList.add('landscape');
            
            // Set up image loading
            const newSrc = imageData.full;
            if (lightboxImg.src === newSrc) {{
                // Image already loaded from cache
                if (lightboxImg.naturalWidth && lightboxImg.naturalHeight) {{
                    setOrientation(lightboxImg.naturalWidth, lightboxImg.naturalHeight);
                    lightbox.classList.add('active');
                    document.body.style.overflow = 'hidden';
                }}
            }} else {{
                // New image, wait for load
                lightboxImg.onload = function() {{
                    setOrientation(lightboxImg.naturalWidth, lightboxImg.naturalHeight);
                    lightbox.classList.add('active');
                    document.body.style.overflow = 'hidden';
                }};
                lightboxImg.src = newSrc;
            }}
            
               // Parse and display EXIF data
            if (imageData.exif) {{
                try {{
                    const exif = JSON.parse(imageData.exif);
                    
                    // Build EXIF HTML
                    let exifHtml = '<div class="exif-header">EXIF Info</div>';
                    
                    // Size (dimensions)
                    if (exif.width && exif.height) {{
                        exifHtml += `<div class="exif-item"><span class="label">Size:</span> <span class="value">${{exif.width}}×${{exif.height}}</span></div>`;
                    }}
                    
                    // File size
                    if (exif.filesize) {{
                        exifHtml += `<div class="exif-item"><span class="label">File:</span> <span class="value">${{exif.filesize}}</span></div>`;
                    }}
                    
                    // Camera
                    if (exif.camera) {{
                        exifHtml += `<div class="exif-item"><span class="label">Camera:</span> <span class="value">${{escapeHtml(exif.camera)}}</span></div>`;
                    }}
                    
                    // Focal length
                    if (exif.focal_length) {{
                        exifHtml += `<div class="exif-item"><span class="label">Lens:</span> <span class="value">${{escapeHtml(exif.focal_length)}}</span></div>`;
                    }}
                    
                    // Copyright
                    if (exif.copyright) {{
                        exifHtml += `<div class="exif-item"><span class="label">Copyright:</span> <span class="value">${{escapeHtml(exif.copyright)}}</span></div>`;
                    }}
                    
                    lightboxExif.innerHTML = exifHtml;
                    
                    // Apply EXIF orientation transform
                    if (exif.orientation && exif.orientation !== 1) {{
                        lightboxImg.setAttribute('data-orientation', exif.orientation);
                    }} else {{
                        lightboxImg.removeAttribute('data-orientation');
                    }}
                }} catch (err) {{
                    console.error('Error parsing EXIF:', err);
                    lightboxExif.innerHTML = '<div class="exif-header">EXIF Info</div><div class="exif-item">No EXIF data available</div>';
                    lightboxImg.removeAttribute('data-orientation');
                }}
            }} else {{
                lightboxExif.innerHTML = '<div class="exif-header">EXIF Info</div><div class="exif-item">No EXIF data available</div>';
                lightboxImg.removeAttribute('data-orientation');
            }}
            
            // Display filename at bottom
            lightboxFilename.textContent = imageData.filename || '';
            
            // Set up click handler for full-res if available
            if (imageData.fullRes && imageData.fullRes !== imageData.full) {{
                lightboxImg.style.cursor = 'pointer';
                lightboxImg.onclick = function(e) {{
                    e.stopPropagation();
                    // Use temp <a> element to avoid popup blocker
                    const a = document.createElement('a');
                    a.href = imageData.fullRes;
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }};
                
                // Show hint for full-res click
                lightboxFilename.innerHTML = `${{imageData.filename || ''}} <span class="full-res-hint">(click image for full res)</span>`;
            }} else {{
                lightboxImg.style.cursor = 'default';
                lightboxImg.onclick = null;
                lightboxFilename.textContent = imageData.filename || '';
            }}
        }}
        
        // Navigate to next/previous image
        function showNext() {{
            currentIndex = (currentIndex + 1) % imageList.length;
            openLightbox(currentIndex);
        }}
        
        function showPrev() {{
            currentIndex = (currentIndex - 1 + imageList.length) % imageList.length;
            openLightbox(currentIndex);
        }}
        
        // ========== Slideshow Functions ==========
        
        async function fetchDirectoryData(subdirPath) {{
            try {{
                const response = await fetch(subdirPath + 'slideshow.json');
                if (!response.ok) throw new Error('Failed to fetch');
                const data = await response.json();
                return data;
            }} catch (error) {{
                console.error('Error fetching slideshow data from', subdirPath, error);
                return null;
            }}
        }}
        
      async function loadNextDirectory() {{
             while (subdirIndex < currentSubdirs.length) {{
                 const subdir = currentSubdirs[subdirIndex];
                 
                 console.log('Loading subdir:', subdir);
                 
                 // Use cache if available, otherwise fetch
                 let data;
                 if (subdirCache.has(subdir)) {{
                     data = subdirCache.get(subdir);
                 }} else {{
                     data = await fetchDirectoryData(subdir + '/');
                     if (data) subdirCache.set(subdir, data);
                 }}
                 
                 // Enter directory if it has images OR has subdirectories to traverse
                 const hasImages = data && data.images && data.images.length > 0;
                 const hasChildren = data && data.subdirs && data.subdirs.length > 0;
                 
                 if (!hasImages && !hasChildren) {{
                     console.log('Skipping empty subdir:', subdir);
                     subdirIndex++;
                     continue;
                 }}
                 
                 // Save parent state for when we return from children
                 subdirQueue.push({{ dirs: currentSubdirs.slice(), index: subdirIndex + 1 }});
                 subdirIndex++;
                 
                 currentDirPath = subdir + '/';
                 subdirCache.set(subdir, data);
                 
                 if (hasImages) {{
                     sequentialImageList = data.images;
                     slideshowIndex = 0;
                     currentSubdirs = data.subdirs || [];
                     subdirIndex = 0;
                     
                     console.log('Entered dir:', subdir, 'with', sequentialImageList.length, 'images');
                     openSlideshowImage(slideshowIndex);
                     return true;
                 }} else if (hasChildren) {{
                     // Directory has no images but has children - recurse into children
                     currentSubdirs = data.subdirs || [];
                     subdirIndex = 0;
                     
                     console.log('Recurse into:', subdir, 'no direct images');
                     const loaded = await loadNextDirectory();
                     if (loaded) return true;
                     // If recursion didn't find images, continue to next sibling
                 }}
             }}
             
             if (subdirQueue.length > 0) {{
                 const parentState = subdirQueue.pop();
                 currentSubdirs = parentState.dirs;
                 subdirIndex = parentState.index;
                 
                 return await loadNextDirectory();
             }}
             
             console.log('No more directories to traverse');
             return false;
         }}
        
      function startSlideshow(mode) {{
             if (mode === 'sequential') {{
                 currentMode = 'sequential';
                 slideshowIndex = 0;
                 
                 currentDirPath = '';
                 subdirQueue = [];
                 subdirIndex = 0;
                 
                 // Use the embedded recursive pool (all images)
                 if (sequentialImageList.length === 0) {{
                     alert('No images available for slideshow.');
                     return;
                 }}
                 
                 console.log('Sequential slideshow starting with', sequentialImageList.length, 'images');
                 
                 // Build directory navigation list
                 buildDirNavList();
                 
             }} else if (mode === 'random') {{
                if (randomPool.length === 0) {{
                    alert('No images available for random slideshow.');
                    return;
                }}
                currentMode = 'random';
                slideshowIndex = Math.floor(Math.random() * randomPool.length);
            }} else {{
                alert('Invalid slideshow mode.');
                return;
            }}
            
            slideshowPlaying = true;
            lightbox.classList.add('slideshow-active');
            updateSlideshowPlayPauseIcon();
            openSlideshowImage(slideshowIndex);
            startSlideshowTimer();
            updateDirNavDisplay();
        }}
        
        function stopSlideshow() {{
            slideshowPlaying = false;
            lightbox.classList.remove('slideshow-active');
            stopSlideshowTimer();
            slideshowControls.style.display = 'none';
        }}
        
        async function buildDirNavList() {{
            dirNavList = [];
            currentDirIndex = -1;
            
            // Scan all directories depth-first to find those with images
            const scannedDirs = new Map();
            
            async function scanDir(dirPath, parentScanned) {{
                // Check cache first
                let data = subdirCache.get(dirPath);
                if (!data) {{
                    try {{
                        const resp = await fetch(dirPath + 'slideshow.json');
                        if (resp.ok) {{
                            data = await resp.json();
                            subdirCache.set(dirPath, data);
                        }} else {{
                            return;
                        }}
                    }} catch (e) {{
                        return;
                    }}
                }}
                
                const hasImages = data && data.images && data.images.length > 0;
                const subdirs = data.subdirs || [];
                
                if (hasImages) {{
                    dirNavList.push({{ path: dirPath, name: dirPath.split('/').pop() || '.', imageCount: data.images.length }});
                }}
                
                for (const subdir of subdirs) {{
                    const subdirPath = dirPath + subdir + '/';
                    if (!scannedDirs.has(subdirPath)) {{
                        scannedDirs.set(subdirPath, true);
                        await scanDir(subdirPath, scannedDirs);
                    }}
                }}
            }}
            
            // Start scanning from root
            await scanDir('', new Map());
            
            // Find current directory index
            if (currentDirPath && dirNavList.length > 0) {{
                for (let i = 0; i < dirNavList.length; i++) {{
                    if (dirNavList[i].path === currentDirPath) {{
                        currentDirIndex = i;
                        break;
                    }}
                }}
            }}
            
            updateDirNavDisplay();
        }}
        
        function updateDirNavDisplay() {{
            if (currentMode !== 'sequential') {{
                slideshowDirName.textContent = '';
                dirPrevBtn.style.display = 'none';
                dirNextBtn.style.display = 'none';
                return;
            }}
            
            dirPrevBtn.style.display = '';
            dirNextBtn.style.display = '';
            
            if (dirNavList.length === 0) {{
                slideshowDirName.textContent = '';
                dirPrevBtn.classList.add('disabled');
                dirNextBtn.classList.add('disabled');
                return;
            }}
            
            if (currentDirIndex >= 0 && currentDirIndex < dirNavList.length) {{
                slideshowDirName.textContent = dirNavList[currentDirIndex].name || '.';
            }} else {{
                slideshowDirName.textContent = '';
            }}
            
            dirPrevBtn.classList.toggle('disabled', currentDirIndex <= 0);
            dirNextBtn.classList.toggle('disabled', currentDirIndex >= dirNavList.length - 1);
        }}
        
        async function dirNavPrev() {{
            if (currentDirIndex <= 0 || dirNavList.length === 0) return;
            
            const targetIndex = currentDirIndex - 1;
            const targetDir = dirNavList[targetIndex];
            currentDirIndex = targetIndex;
            updateDirNavDisplay();
            
            // Navigate to the target directory
            currentDirPath = targetDir.path;
            subdirQueue = [];
            subdirIndex = 0;
            
            try {{
                const resp = await fetch(targetDir.path + 'slideshow.json');
                if (resp.ok) {{
                    const data = await resp.json();
                    if (data.images && data.images.length > 0) {{
                        sequentialImageList = data.images;
                        slideshowIndex = data.images.length - 1;
                        currentSubdirs = data.subdirs || [];
                        openSlideshowImage(slideshowIndex);
                        resetSlideshowTimer();
                        return;
                    }}
                }}
            }} catch (e) {{
                console.error('Failed to load directory:', targetDir.path, e);
            }}
            
            // Fallback: use recursive pool for this directory
            if (window._sequentialRecursivePool && window._sequentialRecursivePool.length > 0) {{
                sequentialImageList = window._sequentialRecursivePool;
                slideshowIndex = 0;
                openSlideshowImage(slideshowIndex);
                resetSlideshowTimer();
            }}
        }}
        
        async function dirNavNext() {{
            if (currentDirIndex >= dirNavList.length - 1 || dirNavList.length === 0) return;
            
            const targetIndex = currentDirIndex + 1;
            const targetDir = dirNavList[targetIndex];
            currentDirIndex = targetIndex;
            updateDirNavDisplay();
            
            // Navigate to the target directory
            currentDirPath = targetDir.path;
            subdirQueue = [];
            subdirIndex = 0;
            
            try {{
                const resp = await fetch(targetDir.path + 'slideshow.json');
                if (resp.ok) {{
                    const data = await resp.json();
                    if (data.images && data.images.length > 0) {{
                        sequentialImageList = data.images;
                        slideshowIndex = 0;
                        currentSubdirs = data.subdirs || [];
                        openSlideshowImage(slideshowIndex);
                        resetSlideshowTimer();
                        return;
                    }}
                }}
            }} catch (e) {{
                console.error('Failed to load directory:', targetDir.path, e);
            }}
            
            // Fallback: use recursive pool for this directory
            if (window._sequentialRecursivePool && window._sequentialRecursivePool.length > 0) {{
                sequentialImageList = window._sequentialRecursivePool;
                slideshowIndex = 0;
                openSlideshowImage(slideshowIndex);
                resetSlideshowTimer();
            }}
        }}
        
        function openSlideshowImage(index) {{
            if (index < 0 || index >= (currentMode === 'sequential' ? sequentialImageList.length : randomPool.length)) return;
            
            slideshowIndex = index;
            const imageData = currentMode === 'sequential' ? sequentialImageList[index] : randomPool[index];
            
            lightbox.classList.add('active', 'slideshow-active');
            lightbox.classList.remove('portrait');
            lightbox.classList.add('landscape');
            slideshowControls.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            
            // Update orientation without removing active class to prevent flicker
            const newSrc = useFullRes ? imageData.fullRes : imageData.full;
            if (lightboxImg.src === newSrc) {{
                if (lightboxImg.naturalWidth && lightboxImg.naturalHeight) {{
                    setOrientation(lightboxImg.naturalWidth, lightboxImg.naturalHeight);
                    updateSlideshowProgress();
                }}
            }} else {{
                lightboxImg.onload = function() {{
                    setOrientation(lightboxImg.naturalWidth, lightboxImg.naturalHeight);
                    updateSlideshowProgress();
                }};
                lightboxImg.onerror = function() {{
                    console.error('Failed to load slideshow image:', newSrc);
                    lightboxFilename.textContent = (imageData.filename || '') + ' [failed to load]';
                }};
                lightboxImg.src = newSrc;
            }}
            
            lightboxFilename.textContent = imageData.filename || '';
            lightboxExif.innerHTML = '';
            lightboxImg.removeAttribute('data-orientation');
            
            // Set up click handler for full-res if available (same as openLightbox)
            const hasFullRes = imageData.fullRes && imageData.fullRes !== imageData.full;
            if (hasFullRes) {{
                lightboxImg.style.cursor = 'pointer';
                lightboxFilename.innerHTML = `${{imageData.filename || ''}} <span class="full-res-hint">(click image for full res)</span>`;
                lightboxImg.onclick = function(e) {{
                    e.stopPropagation();
                    const a = document.createElement('a');
                    a.href = imageData.fullRes;
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }};
            }} else {{
                lightboxImg.style.cursor = 'default';
                lightboxImg.onclick = null;
                lightboxFilename.textContent = imageData.filename || '';
            }}
        }}
        
        async function slideshowNext() {{
            if (currentMode === 'sequential') {{
                if (slideshowIndex < sequentialImageList.length - 1) {{
                    slideshowIndex = slideshowIndex + 1;
                    openSlideshowImage(slideshowIndex);
                }} else {{
                    const loaded = await loadNextDirectory();
                    if (!loaded) {{
                        slideshowPlaying = false;
                        lightbox.classList.remove('slideshow-active');
                        stopSlideshowTimer();
                        slideshowControls.style.display = 'none';
                        alert('End of slideshow');
                        closeLightbox();
                    }}
                }}
            }} else {{
                slideshowIndex = Math.floor(Math.random() * randomPool.length);
                openSlideshowImage(slideshowIndex);
            }}
            resetSlideshowTimer();
        }}
        
        function toggleSlideshowPlayPause() {{
            slideshowPlaying = !slideshowPlaying;
            updateSlideshowPlayPauseIcon();
            if (slideshowPlaying) {{
                startSlideshowTimer();
            }} else {{
                stopSlideshowTimer();
            }}
        }}
        
        function updateSlideshowPlayPauseIcon() {{
            slideshowPlaypause.textContent = slideshowPlaying ? '⏸' : '▶';
            slideshowPlaypause.title = slideshowPlaying ? 'Pause' : 'Play';
        }}
        
       function updateSlideshowProgress() {{
            const total = currentMode === 'sequential' ? sequentialImageList.length : randomPool.length;
            slideshowProgress.textContent = `${{slideshowIndex + 1}} / ${{total}}`;
        }}
        
        function startSlideshowTimer() {{
            if (slideshowInterval) return;
            
            let elapsed = 0;
            const step = 50;  // Update every 50ms
            
            slideshowInterval = setInterval(() => {{
                elapsed += step;
                const progress = Math.min((elapsed / SLIDESHOW_INTERVAL_MS) * 100, 100);
                slideshowTimerBar.style.width = progress + '%';
                
                if (elapsed >= SLIDESHOW_INTERVAL_MS && slideshowPlaying) {{
                    slideshowNext();
                    elapsed = 0;
                }}
            }}, step);
        }}
        
        function stopSlideshowTimer() {{
            if (slideshowInterval) {{
                clearInterval(slideshowInterval);
                slideshowInterval = null;
            }}
            slideshowTimerBar.style.width = '0%';
        }}
        
        function resetSlideshowTimer() {{
            stopSlideshowTimer();
            if (slideshowPlaying) {{
                startSlideshowTimer();
            }}
        }}
        
        // Click on thumbnails to open lightbox
        images.forEach((img, index) => {{
            img.addEventListener('click', (e) => {{
                e.preventDefault();
                e.stopPropagation();
                openLightbox(index);
            }});
        }});
        
     // Navigation buttons
        prevBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            if (lightbox.classList.contains('slideshow-active')) {{
                const total = currentMode === 'sequential' ? sequentialImageList.length : randomPool.length;
                slideshowIndex = (slideshowIndex - 1 + total) % total;
                openSlideshowImage(slideshowIndex);
                resetSlideshowTimer();
            }} else {{
                showPrev();
            }}
        }});
        
        nextBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            if (lightbox.classList.contains('slideshow-active')) {{
                slideshowNext();
            }} else {{
                showNext();
            }}
        }});
        
       // Slideshow play/pause button
        slideshowPlaypause.addEventListener('click', (e) => {{
            e.stopPropagation();
            toggleSlideshowPlayPause();
        }});
        
        // Directory navigation buttons (sequential mode only)
        dirPrevBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            if (currentMode === 'sequential') {{
                dirNavPrev();
            }}
        }});
        
      dirNextBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            if (currentMode === 'sequential') {{
                dirNavNext();
            }}
        }});
        
        // Close lightbox
        function closeLightbox() {{
            stopSlideshow();
            lightbox.classList.remove('active');
            lightbox.classList.remove('portrait');
            lightbox.classList.remove('landscape');
            document.body.style.overflow = '';
            setTimeout(() => {{
                lightboxImg.src = '';
            }}, 200);
        }}
        
        closeBtn.addEventListener('click', closeLightbox);
        
        lightbox.addEventListener('click', (e) => {{
            // Don't advance if clicking on controls, buttons, or image itself
            const isControlClick = e.target.closest('.slideshow-controls') || 
                                   e.target.closest('.lightbox-nav') ||
                                   e.target.closest('.lightbox-close') ||
                                   e.target.tagName === 'IMG';
            
            if (isControlClick) return;
            
            if (e.target === lightbox || e.target.classList.contains('lightbox-image-container')) {{
                if (lightbox.classList.contains('slideshow-active')) {{
                    // In slideshow mode, clicking advances to next image
                    slideshowNext();
                }} else {{
                    closeLightbox();
                }}
            }}
        }});
        
    // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (!lightbox.classList.contains('active')) return;
            
            switch(e.key) {{
                case 'Escape':
                    closeLightbox();
                    break;
                case 'ArrowLeft':
                    if (lightbox.classList.contains('slideshow-active')) {{
                        const total = currentMode === 'sequential' ? sequentialImageList.length : randomPool.length;
                        slideshowIndex = (slideshowIndex - 1 + total) % total;
                        openSlideshowImage(slideshowIndex);
                        resetSlideshowTimer();
                    }} else {{
                        showPrev();
                    }}
                    break;
                case 'ArrowRight':
                    if (lightbox.classList.contains('slideshow-active')) {{
                        slideshowNext();
                    }} else {{
                        showNext();
                    }}
                    break;
                case ' ':
                    if (lightbox.classList.contains('slideshow-active')) {{
                        e.preventDefault();
                        toggleSlideshowPlayPause();
                    }}
                    break;
            }}
        }});
        
        // Full-res toggle
        document.getElementById('fullres-check').addEventListener('change', function(e) {{
            useFullRes = e.target.checked;
            if (lightbox.classList.contains('slideshow-active')) {{
                openSlideshowImage(slideshowIndex);
            }}
        }});
    </script>
</body>
</html>'''
    
    # Write HTML file
    html_path = os.path.join(output_dir, 'index.html')
    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return True
    except IOError as e:
        print(f"  [ERROR] Failed to write {html_path}: {e}")
        return False


def process_directory(directory, output_dir, root_path, thumb_size, force, random_depth=None, enable_slideshow=False, enable_random=False, browse_prev='', browse_next=''):
    """Process a single directory and generate its index.html and slideshow.json."""
    images = get_image_files(directory)
    subdirs = get_subdirectories(directory)
    
    # Skip if no content
    if not images and not subdirs:
        return 0
    
    print(f"  Processing: {os.path.relpath(directory, root_path) or 'root'}")
    
    success = 0
    if generate_html(directory, output_dir, root_path, thumb_size, force=force, random_depth=random_depth, enable_slideshow=enable_slideshow, enable_random=enable_random, browse_prev=browse_prev, browse_next=browse_next):
        success += 1
    
    # Only generate slideshow.json if slideshow features are enabled
    if enable_slideshow or enable_random:
        if generate_slideshow_json(directory, output_dir):
            success += 1
    
    return success


def calculate_metrics(root_path, output_root):
    """Calculate gallery metrics."""
    metrics = {}
    
    # Total size of all index.html files
    html_files = count_files_recursive(output_root, '.html', EXCLUDED_DIRS)
    html_size = 0
    for dirpath, _, filenames in os.walk(output_root):
        if any(d in EXCLUDED_DIRS for d in dirpath.split(os.sep)):
            continue
        for f in filenames:
            if f == 'index.html':
                try:
                    html_size += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    metrics['html_count'] = html_files
    metrics['html_size'] = html_size
    
    # Total size of original photos
    photo_size = get_recursive_dir_size(root_path, EXCLUDED_DIRS)
    metrics['photo_count'] = count_files_recursive(root_path, excluded_dirs=EXCLUDED_DIRS)
    # Filter to only image extensions for count
    metrics['photo_count'] = 0
    for dirpath, _, filenames in os.walk(root_path):
        if any(d in EXCLUDED_DIRS for d in dirpath.split(os.sep)):
            continue
        for f in filenames:
            if Path(f).suffix.lower() in IMAGE_EXTENSIONS:
                metrics['photo_count'] += 1
                try:
                    photo_size += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    metrics['photo_size'] = photo_size
    
    # Total size of thumbnails
    thumb_size = 0
    thumb_count = 0
    for dirpath, _, filenames in os.walk(root_path):
        if '.thumbs' not in dirpath:
            continue
        for f in filenames:
            try:
                thumb_size += os.path.getsize(os.path.join(dirpath, f))
                thumb_count += 1
            except OSError:
                pass
    metrics['thumb_count'] = thumb_count
    metrics['thumb_size'] = thumb_size
    
    # Total size of LR images
    lr_size = 0
    lr_count = 0
    for dirpath, _, filenames in os.walk(root_path):
        if '.lr' not in dirpath:
            continue
        for f in filenames:
            try:
                lr_size += os.path.getsize(os.path.join(dirpath, f))
                lr_count += 1
            except OSError:
                pass
    metrics['lr_count'] = lr_count
    metrics['lr_size'] = lr_size
    
    # Total size of slideshow.json files
    json_count = 0
    json_size = 0
    for dirpath, _, filenames in os.walk(output_root):
        if any(d in EXCLUDED_DIRS for d in dirpath.split(os.sep)):
            continue
        for f in filenames:
            if f == 'slideshow.json':
                try:
                    json_size += os.path.getsize(os.path.join(dirpath, f))
                    json_count += 1
                except OSError:
                    pass
    metrics['json_count'] = json_count
    metrics['json_size'] = json_size
    
    return metrics


def print_metrics(metrics):
    """Print formatted metrics summary."""
    print("\n" + "=" * 50)
    print("GALLERY METRICS")
    print("=" * 50)
    print(f"Original Photos:   {metrics['photo_count']:6,} files  ({format_size(metrics['photo_size'])})")
    print(f"Thumbnails:        {metrics['thumb_count']:6,} files  ({format_size(metrics['thumb_size'])})")
    print(f"LR Images:         {metrics['lr_count']:6,} files  ({format_size(metrics['lr_size'])})")
    print(f"Index HTML Files:  {metrics['html_count']:6,} files  ({format_size(metrics['html_size'])})")
    print(f"Slideshow JSON:    {metrics.get('json_count', 0):6,} files  ({format_size(metrics.get('json_size', 0))})")
    print("-" * 50)
    total_generated = metrics['thumb_size'] + metrics['lr_size'] + metrics['html_size'] + metrics.get('json_size', 0)
    print(f"Total Generated:   {format_size(total_generated)}")
    if metrics['photo_size'] > 0:
        ratio = (total_generated / metrics['photo_size']) * 100
        print(f"Overhead:          {ratio:.1f}% of original photos")
    print("=" * 50)


def walk_and_generate(root_path, output_root, thumb_size, force, random_depth=None, enable_slideshow=False, enable_random=False):
    """Recursively walk directory tree and generate galleries."""
    total_pages = 0
    
    # Collect all directories with images (for sibling navigation)
    all_dirs_with_images = collect_dirs_with_images(root_path)
    
    # Process directories in depth-first order (bottom-up)
    to_process = []
    
    def collect_dirs(path, depth=0):
        dirs = get_subdirectories(path)
        for d in dirs:
            collect_dirs(d, depth + 1)
            to_process.append((d, depth))
    
    collect_dirs(root_path)
    
    # Sort by depth (deepest first), then alphabetically
    to_process.sort(key=lambda x: (-x[1], os.path.basename(x[0]).lower()))
    
    # Add root directory
    to_process.append((root_path, 0))
    
    print(f"\nGenerating gallery for: {root_path}")
    print("-" * 50)
    
    for dir_path, _ in to_process:
        rel_dir = os.path.relpath(dir_path, root_path)
        output_dir = os.path.join(output_root, rel_dir) if rel_dir != '.' else output_root
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Get sibling navigation for this directory
        browse_prev, browse_next = get_sibling_nav(dir_path, all_dirs_with_images, root_path)
        
        pages = process_directory(dir_path, output_dir, root_path, thumb_size, force, random_depth, enable_slideshow, enable_random, browse_prev=browse_prev, browse_next=browse_next)
        total_pages += pages
    
    print("-" * 50)
    print(f"\nComplete! Generated {total_pages} gallery page(s).")
    
    # Calculate metrics
    metrics = calculate_metrics(root_path, output_root)
    print_metrics(metrics)
    
    return total_pages, metrics


class TeeStream:
    """Write to both stdout and a file."""
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file
        
    def write(self, message):
        self.original.write(message)
        self.log_file.write(message)
        self.log_file.flush()
        
    def flush(self):
        self.original.flush()
        self.log_file.flush()


def main():
    """Main entry point."""
    args = parse_args()
    
    root_path = os.path.abspath(args.root)
    output_root = os.path.abspath(args.output_root or args.root)
    
    # Set up logging to parent directory (default behavior)
    log_file = None
    try:
        parent_dir = os.path.dirname(root_path)
        log_path = os.path.join(parent_dir, 'gallery.log')
        log_file = open(log_path, 'w', encoding='utf-8')
        sys.stdout = TeeStream(sys.stdout, log_file)
        sys.stderr = TeeStream(sys.stderr, log_file)
    except IOError as e:
        print(f"[WARN] Could not create log file at {log_path}: {e}")
    
    # Validate root directory
    if not os.path.isdir(root_path):
        print(f"Error: Root directory does not exist: {root_path}")
        return 1
    
    # Check for HEIF support
    if not HEIF_SUPPORT:
        print("\n[WARN] HEIF/HEIC support not available!")
        print("      Install pillow-heif or piheif for HEIF file support:")
        print("      pip install pillow-heif")
        print()
    
    # Walk directory tree and generate galleries
    result = walk_and_generate(root_path, output_root, args.thumb_size, args.force, args.random_depth, args.slideshow, args.random)
    
    if isinstance(result, tuple):
        total_pages, metrics = result
    else:
        total_pages = result
        metrics = None
    
    if total_pages == 0:
        print("\nNo directories with images or subdirectories found.")
    
    # Restore stdout and close log file
    if log_file:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log_file.close()
    
    return 0


if __name__ == '__main__':
    exit(main())
