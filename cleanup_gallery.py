#!/usr/bin/env python3
"""
Gallery Cleanup - Removes orphaned thumbnail and LR files.

Scans gallery directories and deletes .thumbs/ and .lr/ files that don't
have corresponding source images (e.g., after deleting photos).

Usage:
    python cleanup_gallery.py galleries/
    python cleanup_gallery.py galleries/ --dry-run   # Preview only
    python cleanup_gallery.py galleries/ --all        # Remove all generated files
"""

import argparse
import os
from pathlib import Path

# Supported image/video extensions and excluded dirs (mirror generate_gallery.py)
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.m4v'}
EXCLUDED_DIRS = {'.thumbs', '.lr', '.git', '__pycache__', 'node_modules'}

# Marker present in every index.html produced by generate_gallery.py
GENERATED_HTML_MARKER = 'cover-toast'


def asset_key(basename):
    """Mirror of generate_gallery.asset_key - keep the two in sync."""
    p = Path(basename)
    return p.stem + '_' + p.suffix.lower().lstrip('.')


def resolve_cover(subdir):
    """Resolve a subdirectory's .folder_cover to an image path, or None."""
    cover_file = subdir / '.folder_cover'
    try:
        rel_path = cover_file.read_text(encoding='utf-8', errors='replace').strip()
    except (IOError, OSError):
        return None
    rel_path = rel_path.replace('\\', '/')
    if not rel_path or os.path.isabs(rel_path):
        return None
    resolved = os.path.normpath(os.path.join(str(subdir), rel_path))
    if not os.path.isfile(resolved):
        return None
    if Path(resolved).suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    return resolved


def collect_expected(dirpath):
    """Compute the set of .thumbs/.lr filenames generate_gallery.py owns here.

    Returns None when the source directory cannot be scanned - callers MUST
    then skip the directory instead of treating every asset as orphaned.
    """
    expected_thumbs = set()
    expected_lr = set()
    unknown_dir_thumbs = False
    source_count = 0
    try:
        entries = list(os.scandir(dirpath))
    except (PermissionError, OSError) as e:
        print(f"  [WARN] Error scanning {dirpath}: {e}")
        return None
    for entry in entries:
        try:
            if entry.is_file():
                ext = Path(entry.name).suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    source_count += 1
                    expected_thumbs.add(asset_key(entry.name) + '_thumb.jpg')
                    expected_lr.add(asset_key(entry.name) + '_LR.jpg')
                elif ext in VIDEO_EXTENSIONS:
                    expected_thumbs.add(asset_key(entry.name) + '_video_thumb.jpg')
            elif entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                cover = resolve_cover(Path(entry.path))
                if cover:
                    expected_thumbs.add(asset_key(os.path.basename(cover)) + '_dir_thumb.jpg')
                else:
                    # No resolvable cover: we cannot know which file the folder
                    # preview uses, so never orphan dir thumbs here.
                    unknown_dir_thumbs = True
        except OSError as e:
            print(f"  [WARN] Error scanning {dirpath}: {e}")
            return None
    return {'thumbs': expected_thumbs, 'lr': expected_lr,
            'unknown_dir_thumbs': unknown_dir_thumbs, 'source_count': source_count}


def cleanup_thumbs(thumbs_dir, expected):
    """Return orphaned thumbnails (names not owned by the generator anymore)."""
    deleted = []
    try:
        for entry in os.scandir(thumbs_dir):
            if not (entry.is_file() and entry.name.endswith('_thumb.jpg')):
                continue
            if entry.name in expected['thumbs']:
                continue
            if entry.name.endswith('_dir_thumb.jpg') and expected['unknown_dir_thumbs']:
                continue
            deleted.append(entry.path)
    except (PermissionError, OSError) as e:
        # Scan failure is not evidence of orphanhood
        print(f"  [WARN] Error scanning {thumbs_dir}: {e}")
        return []
    return deleted


def cleanup_lr(lr_dir, expected):
    """Return orphaned LR files."""
    deleted = []
    try:
        for entry in os.scandir(lr_dir):
            if entry.is_file() and entry.name.endswith('_LR.jpg'):
                if entry.name not in expected['lr']:
                    deleted.append(entry.path)
    except (PermissionError, OSError) as e:
        print(f"  [WARN] Error scanning {lr_dir}: {e}")
        return []
    return deleted


def cleanup_folder_covers(dirpath):
    """Check if .folder_cover exists and points to a valid image.
    
    Returns a list of orphaned .folder_cover paths (0 or 1 per directory).
    """
    cover_file = dirpath / '.folder_cover'
    if not cover_file.is_file():
        return []
    
    try:
        rel_path = cover_file.read_text(encoding='utf-8').strip()
    except UnicodeDecodeError:
        # Genuinely invalid content - treat as broken cover
        return [str(cover_file)]
    except (IOError, OSError):
        # Transient I/O failure is not evidence of orphanhood
        return []
    
    if not rel_path:
        return [str(cover_file)]
    
    # Reject absolute paths
    if os.path.isabs(rel_path):
        return [str(cover_file)]
    
    # Resolve against dirpath (covers may be written on Windows, read on Linux)
    rel_path = rel_path.replace('\\', '/')
    resolved = os.path.normpath(os.path.join(str(dirpath), rel_path))
    
    # Check if file exists and has valid extension
    if not os.path.isfile(resolved):
        return [str(cover_file)]
    
    ext = Path(resolved).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        return [str(cover_file)]
    
    return []


def main():
    parser = argparse.ArgumentParser(
        description='Remove orphaned thumbnail and LR files from galleries.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_gallery.py galleries/           # Delete orphaned files
  python cleanup_gallery.py galleries/ --dry-run # Preview what would be deleted
  python cleanup_gallery.py galleries/ --all     # Remove all generated files
"""
    )
    
    parser.add_argument(
        'root',
        default='galleries',
        nargs='?',
        help='Root gallery directory (default: galleries)'
    )
    
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview deletions without actually deleting'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed source file counts per directory'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Remove ALL generated files (index.html, .thumbs/, .lr/)'
    )
    
    args = parser.parse_args()
    root_path = Path(args.root).resolve()
    
    if not root_path.is_dir():
        print(f"Error: Directory not found: {root_path}")
        return 1
    
    if args.all:
        return cleanup_all(root_path, args.dry_run)
    
    # Original orphan cleanup mode
    total_source_files = 0
    total_thumbs_found = 0
    total_lr_found = 0
    total_covers_found = 0
    total_thumbs_deleted = 0
    total_lr_deleted = 0
    total_covers_deleted = 0
    total_bytes_freed = 0
    
    print(f"Scanning: {root_path}")
    print("-" * 60)
    
    # Walk through all directories
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_path = Path(dirpath)
        rel_path = current_path.relative_to(root_path)
        
        # Skip excluded directories
        if any(part.startswith('.') for part in rel_path.parts):
            continue
        
        # Compute expected generated assets (None = scan failed, never delete)
        expected = collect_expected(current_path)
        if expected is None:
            continue
        total_source_files += expected['source_count']
        
        if args.verbose:
            print(f"\n{rel_path or 'root'}: {expected['source_count']} source file(s)")
        
        # Check .thumbs directory
        thumbs_dir = current_path / '.thumbs'
        if thumbs_dir.is_dir():
            orphaned_thumbs = cleanup_thumbs(thumbs_dir, expected)
            
            # Count thumbnails in this directory
            try:
                thumb_count = sum(1 for e in os.scandir(thumbs_dir) if e.is_file() and e.name.endswith('_thumb.jpg'))
                total_thumbs_found += thumb_count
                if args.verbose and thumb_count > 0:
                    print(f"    .thumbs/: {thumb_count} thumbnail(s), {len(orphaned_thumbs)} orphaned")
            except (PermissionError, OSError):
                pass
            
            if orphaned_thumbs:
                thumb_paths = [str(Path(p).relative_to(root_path)) for p in orphaned_thumbs]
                thumb_sizes = sum(os.path.getsize(p) for p in orphaned_thumbs if Path(p).exists())
                print(f"\n{rel_path}/.thumbs/")
                print(f"  {len(orphaned_thumbs)} orphaned thumbnail(s): {thumb_paths}")
                total_thumbs_deleted += len(orphaned_thumbs)
                total_bytes_freed += thumb_sizes
        
        # Check .lr directory
        lr_dir = current_path / '.lr'
        if lr_dir.is_dir():
            orphaned_lr = cleanup_lr(lr_dir, expected)
            
            # Count LR files in this directory
            try:
                lr_count = sum(1 for e in os.scandir(lr_dir) if e.is_file() and e.name.endswith('_LR.jpg'))
                total_lr_found += lr_count
                if args.verbose and lr_count > 0:
                    print(f"    .lr/: {lr_count} LR file(s), {len(orphaned_lr)} orphaned")
            except (PermissionError, OSError):
                pass
            
            if orphaned_lr:
                lr_paths = [str(Path(p).relative_to(root_path)) for p in orphaned_lr]
                lr_sizes = sum(os.path.getsize(p) for p in orphaned_lr if Path(p).exists())
                print(f"\n{rel_path}/.lr/")
                print(f"  {len(orphaned_lr)} orphaned LR file(s): {lr_paths}")
                total_lr_deleted += len(orphaned_lr)
                total_bytes_freed += lr_sizes
        
        # Check .folder_cover
        cover_file = current_path / '.folder_cover'
        if cover_file.is_file():
            total_covers_found += 1
            orphaned_covers = cleanup_folder_covers(current_path)
            if orphaned_covers:
                cover_paths = [str(Path(p).relative_to(root_path)) for p in orphaned_covers]
                cover_sizes = sum(os.path.getsize(p) for p in orphaned_covers if Path(p).exists())
                print(f"\n{rel_path}/.folder_cover")
                print(f"  {len(orphaned_covers)} orphaned cover(s): {cover_paths}")
                total_covers_deleted += len(orphaned_covers)
                total_bytes_freed += cover_sizes
    
    # Summary before deletion
    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Source files found: {total_source_files}")
    print(f"  Thumbnails found: {total_thumbs_found} ({total_thumbs_deleted} orphaned)")
    print(f"  LR files found: {total_lr_found} ({total_lr_deleted} orphaned)")
    print(f"  Folder covers found: {total_covers_found} ({total_covers_deleted} orphaned)")
    print(f"  Total size to free: {total_bytes_freed / 1024 / 1024:.2f} MB")
    
    if args.dry_run:
        print("\n[Dry run - no files deleted]")
        return 0
    
    # Delete orphaned files
    print("\nDeleting orphaned files...")
    
    deleted_thumbs = 0
    deleted_lr = 0
    deleted_covers = 0
    deleted_bytes = 0
    
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_path = Path(dirpath)
        rel_path = current_path.relative_to(root_path)
        
        if any(part.startswith('.') for part in rel_path.parts):
            continue
        
        expected = collect_expected(current_path)
        if expected is None:
            # Could not scan sources - delete nothing in this directory
            continue
        
        # Delete orphaned thumbnails
        thumbs_dir = current_path / '.thumbs'
        if thumbs_dir.is_dir():
            for thumb_path in cleanup_thumbs(thumbs_dir, expected):
                try:
                    size = os.path.getsize(thumb_path)
                    os.remove(thumb_path)
                    deleted_thumbs += 1
                    deleted_bytes += size
                except OSError as e:
                    print(f"  [ERROR] Failed to delete {thumb_path}: {e}")
        
        # Delete orphaned LR files
        lr_dir = current_path / '.lr'
        if lr_dir.is_dir():
            for lr_path in cleanup_lr(lr_dir, expected):
                try:
                    size = os.path.getsize(lr_path)
                    os.remove(lr_path)
                    deleted_lr += 1
                    deleted_bytes += size
                except OSError as e:
                    print(f"  [ERROR] Failed to delete {lr_path}: {e}")
        
        # Delete orphaned .folder_cover files
        for cover_path in cleanup_folder_covers(current_path):
            try:
                size = os.path.getsize(cover_path)
                os.remove(cover_path)
                deleted_covers += 1
                deleted_bytes += size
            except OSError as e:
                print(f"  [ERROR] Failed to delete {cover_path}: {e}")
    
    print("\nDone! Deleted:")
    print(f"  - {deleted_thumbs} thumbnail(s)")
    print(f"  - {deleted_lr} LR file(s)")
    print(f"  - {deleted_covers} folder cover(s)")
    print(f"  - Freed {deleted_bytes / 1024 / 1024:.2f} MB")
    
    return 0


def cleanup_all(root_path, dry_run=False):
    """Remove ALL generated files and directories."""
    deleted_files = []
    deleted_dirs = []
    total_freed = 0
    
    print(f"Removing all generated files from: {root_path}")
    print("-" * 60)
    
    # Walk through all directories
    for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
        current_path = Path(dirpath)
        rel_path = current_path.relative_to(root_path)
        
        # Skip hidden directories (except .git which we don't touch)
        if any(part.startswith('.') and part not in {'.git'} for part in rel_path.parts):
            continue
        
        # Remove index.html files (only ones we generated, never hand-authored pages)
        if 'index.html' in filenames:
            html_file = current_path / 'index.html'
            try:
                # cover-toast sits near </body>, so scan the whole file
                content = html_file.read_text(encoding='utf-8', errors='replace')
                if GENERATED_HTML_MARKER not in content:
                    print(f"  [SKIP] Not generated by gallery tool: {html_file}")
                else:
                    size = os.path.getsize(html_file)
                    if not dry_run:
                        html_file.unlink()
                    deleted_files.append((html_file, size))
                    total_freed += size
            except OSError as e:
                print(f"  [ERROR] Failed to delete {html_file}: {e}")
        
        # Remove .thumbs directories
        thumbs_dir = current_path / '.thumbs'
        if thumbs_dir.is_dir():
            try:
                thumb_size = sum(
                    os.path.getsize(os.path.join(dirpath2, f))
                    for dirpath2, _, files in os.walk(thumbs_dir)
                    for f in files
                )
                if not dry_run:
                    import shutil
                    shutil.rmtree(thumbs_dir)
                deleted_dirs.append((thumbs_dir, thumb_size))
                total_freed += thumb_size
            except OSError as e:
                print(f"  [ERROR] Failed to delete {thumbs_dir}: {e}")
        
        # Remove .lr directories
        lr_dir = current_path / '.lr'
        if lr_dir.is_dir():
            try:
                lr_size = sum(
                    os.path.getsize(os.path.join(dirpath2, f))
                    for dirpath2, _, files in os.walk(lr_dir)
                    for f in files
                )
                if not dry_run:
                    import shutil
                    shutil.rmtree(lr_dir)
                deleted_dirs.append((lr_dir, lr_size))
                total_freed += lr_size
            except OSError as e:
                print(f"  [ERROR] Failed to delete {lr_dir}: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Files deleted: {len(deleted_files)}")
    for f, size in deleted_files:
        print(f"    - {f.relative_to(root_path)} ({size:,} bytes)")
    print(f"  Directories removed: {len(deleted_dirs)}")
    for d, size in deleted_dirs:
        print(f"    - {d.relative_to(root_path)} ({size:,} bytes)")
    print(f"  Total freed: {total_freed / 1024 / 1024:.2f} MB")
    
    if dry_run:
        print("\n[Dry run - no files deleted]")
    else:
        print("\nDone! All generated files removed.")
    
    return 0


if __name__ == '__main__':
    exit(main())
