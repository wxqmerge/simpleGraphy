#!/usr/bin/env python3
"""
Gallery Generator - Creates responsive photo galleries with thumbnails and lightbox viewer.

Usage:
    python generate_gallery.py galleries/
    python generate_gallery.py galleries/ --thumb-size 200 --force

Arguments:
    --root, -r          Root directory to scan (default: galleries)
    --output-root, -o   Where to write index.html files (default: same as --root)
    --thumb-size, -t    Max thumbnail dimension in pixels (default: 200)
    --force, -f         Force rebuild all thumbnails even if they exist
"""

import argparse
import os
import html
import json
import warnings
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
EXCLUDED_DIRS = {'.thumbs', '.git', '__pycache__', 'node_modules'}


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

Output Structure:
  Each directory with images gets an index.html and .thumbs/ subdirectory.
  Thumbnails are 200px max dimension JPG files (HEIF converted automatically).
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
                
                if focal_35:
                    try:
                        fl = float(focal_35)
                        exif_data['focal_length'] = f'{fl:.0f}mm (35mm equiv)'
                    except (ValueError, TypeError):
                        pass
                elif focal:
                    try:
                        fl = float(focal)
                        exif_data['focal_length'] = f'{fl:.0f}mm'
                    except (ValueError, TypeError):
                        pass
                
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
    
    # Need LR if h+w > 5000 or if it's a HEIF file
    return dimension_sum > 5000 or is_heif


def generate_lr_image(source_path, lr_dir, lr_size_max=3000):
    """Generate low-res version of image (h+w < 3000)."""
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
                if img.width * img.height > 100_000_000:
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


def generate_html(directory, output_dir, root_path, thumb_size, force=False, parent_path=None):
    """Generate index.html for a directory."""
    images = get_image_files(directory)
    subdirs = get_subdirectories(directory)
    
    # Skip if no images and no subdirectories
    if not images and not subdirs:
        return False
    
    dir_name = os.path.basename(directory.rstrip('/')) or 'Gallery'
    dir_name_safe = html.escape(dir_name)
    
    # Build breadcrumb navigation
    rel_path = os.path.relpath(directory, root_path)
    if rel_path == '.':
        breadcrumbs = [{'name': 'Root', 'link': './'}]
    else:
        breadcrumbs = [{'name': 'Root', 'link': '../' * (rel_path.count(os.sep) + 1)}]
        parts = rel_path.split(os.sep)
        path_so_far = ''
        for i, part in enumerate(parts):
            path_so_far = os.path.join(path_so_far, part) if path_so_far else part
            link_depth = len(parts) - i
            breadcrumbs.append({
                'name': html.escape(part),
                'link': '../' * link_depth + (path_so_far.replace(os.sep, '/') + '/' if i < len(parts) - 1 else '')
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
    
    # Build gallery grid HTML
    grid_html = ''.join(subdir_items + image_items)
    
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
        }}
        
        h1 {{
            font-size: 2em;
            margin-bottom: 15px;
            color: #fff;
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
        
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
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
        
        /* Landscape layout (EXIF on bottom) */
        .lightbox.landscape .lightbox-content-wrapper {{
            flex-direction: column;
        }}
        
        .lightbox.landscape .lightbox-image-container {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            padding-bottom: 20px;
            flex-grow: 1;
        }}
        
        .lightbox.landscape .lightbox-image-container img {{
            max-width: calc(100vw - 40px) !important;
            max-height: calc(70vh - 60px) !important;
            object-fit: contain !important;
            width: auto !important;
            height: auto !important;
        }}
        
        .lightbox.landscape .lightbox-exif {{
            width: 100%;
            padding: 0 40px 30px;
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            min-height: 60px;
        }}
        
        /* Portrait layout (EXIF on side) */
        .lightbox.portrait .lightbox-content-wrapper {{
            flex-direction: row;
            align-items: center;
        }}
        
        .lightbox.portrait .lightbox-image-container {{
            display: flex;
            justify-content: center;
            margin-right: 30px;
            align-items: center;
        }}
        
        .lightbox.portrait .lightbox-image-container img {{
            max-width: calc(65vw - 200px) !important;
            max-height: calc(90vh - 40px) !important;
            object-fit: contain !important;
            width: auto !important;
            height: auto !important;
        }}
        
        .lightbox.portrait .lightbox-exif {{
            width: 250px;
            padding: 20px;
        }}
        
        /* Default image sizing - applies to all lightbox images */
        .lightbox-image-container img {{
            max-width: 100%;
            max-height: 90vh;
            object-fit: contain;
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
            color: #fff;
            font-size: 0.9em;
        }}
        
        .exif-item {{
            margin-bottom: 12px;
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
        
        /* Portrait layout: EXIF items stacked vertically */
        .lightbox.portrait .lightbox-exif {{
            display: flex;
            flex-direction: column;
        }}
        
        /* Filename display at bottom */
        .lightbox-filename {{
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            color: #fff;
            font-size: 0.9em;
            text-align: center;
            padding: 8px 16px;
            background: rgba(0, 0, 0, 0.6);
            border-radius: 4px;
            white-space: nowrap;
            z-index: 1002;
        }}
        
        .full-res-hint {{
            color: #4fc3f7;
            font-size: 0.85em;
            margin-left: 8px;
            opacity: 0.9;
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
            <h1>{dir_name_safe}</h1>
            <nav class="breadcrumbs">{breadcrumb_html}</nav>
            <div class="stats">
                {total_folders} folder{'s' if total_folders != 1 else ''}, 
                {total_images} image{'s' if total_images != 1 else ''}
            </div>
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
        <div class="lightbox-content-wrapper">
            <div class="lightbox-image-container">
                <img id="lightbox-img" src="" alt="">
            </div>
            <div class="lightbox-exif" id="lightbox-exif"></div>
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
        
        // Image navigation state
        let imageList = [];
        let currentIndex = 0;
        
        // Build image list for navigation
        const images = document.querySelectorAll('.gallery-item img[data-full]');
        imageList = Array.from(images).map(img => ({{
            full: img.getAttribute('data-full'),  // LR version if available
            fullRes: img.getAttribute('data-full-res'),  // Full resolution version
            exif: img.getAttribute('data-exif'),
            filename: img.alt || ''
        }}));
        
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
                    let exifHtml = '';
                    
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
                    lightboxExif.innerHTML = '';
                    lightboxImg.removeAttribute('data-orientation');
                }}
            }} else {{
                lightboxExif.innerHTML = '';
                lightboxImg.removeAttribute('data-orientation');
            }}
            
            // Display filename at bottom
            lightboxFilename.textContent = imageData.filename || '';
            
            // Set up click handler for full-res if available
            if (imageData.fullRes && imageData.fullRes !== imageData.full) {{
                lightboxImg.style.cursor = 'pointer';
                lightboxImg.onclick = function(e) {{
                    e.stopPropagation();
                    window.open(imageData.fullRes, '_blank');
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
            showPrev();
        }});
        
        nextBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            showNext();
        }});
        
        // Close lightbox
        function closeLightbox() {{
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
            if (e.target === lightbox || e.target.classList.contains('lightbox-image-container')) {{
                closeLightbox();
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
                    showPrev();
                    break;
                case 'ArrowRight':
                    showNext();
                    break;
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


def process_directory(directory, output_dir, root_path, thumb_size, force):
    """Process a single directory and generate its index.html."""
    images = get_image_files(directory)
    subdirs = get_subdirectories(directory)
    
    # Skip if no content
    if not images and not subdirs:
        return 0
    
    print(f"  Processing: {os.path.relpath(directory, root_path) or 'root'}")
    
    if generate_html(directory, output_dir, root_path, thumb_size, force):
        return 1
    return 0


def walk_and_generate(root_path, output_root, thumb_size, force):
    """Recursively walk directory tree and generate galleries."""
    total_pages = 0
    
    # Process directories in depth-first order (bottom-up)
    # This ensures we process leaf directories first
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
        
        pages = process_directory(dir_path, output_dir, root_path, thumb_size, force)
        total_pages += pages
    
    print("-" * 50)
    print(f"\nComplete! Generated {total_pages} gallery page(s).")
    
    return total_pages


def main():
    """Main entry point."""
    args = parse_args()
    
    root_path = os.path.abspath(args.root)
    output_root = os.path.abspath(args.output_root or args.root)
    
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
    total_pages = walk_and_generate(root_path, output_root, args.thumb_size, args.force)
    
    if total_pages == 0:
        print("\nNo directories with images or subdirectories found.")
    
    return 0


if __name__ == '__main__':
    exit(main())
