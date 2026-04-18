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

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif'}


def find_source_images(directory):
    """Find all source images in a directory (not subdirs)."""
    sources = set()
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                ext = Path(entry.path).suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    # Store stem (filename without extension)
                    sources.add(entry.name.rsplit('.', 1)[0])
    except (PermissionError, OSError) as e:
        print(f"  [WARN] Error scanning {directory}: {e}")
    return sources


def cleanup_thumbs(thumbs_dir, source_stems):
    """Remove orphaned thumbnails."""
    deleted = []
    try:
        for entry in os.scandir(thumbs_dir):
            if entry.is_file() and entry.name.endswith('_thumb.jpg'):
                # Skip directory preview thumbnails - they're previews for subdirectories
                # and their source images are in those subdirectories, not the current folder
                if entry.name.endswith('_dir_thumb.jpg'):
                    continue
                
                # Extract original filename stem for regular thumbnails
                # e.g., "IMG_123_thumb.jpg" -> "IMG_123"
                stem = entry.name.rsplit('_thumb', 1)[0]
                if stem not in source_stems:
                    deleted.append(entry.path)
    except (PermissionError, OSError) as e:
        print(f"  [WARN] Error scanning {thumbs_dir}: {e}")
    return deleted


def cleanup_lr(lr_dir, source_stems):
    """Remove orphaned LR files."""
    deleted = []
    try:
        for entry in os.scandir(lr_dir):
            if entry.is_file() and entry.name.endswith('_LR.jpg'):
                # Extract original filename stem
                # e.g., "IMG_123_LR.jpg" -> "IMG_123"
                stem = entry.name.rsplit('_LR', 1)[0]
                if stem not in source_stems:
                    deleted.append(entry.path)
    except (PermissionError, OSError) as e:
        print(f"  [WARN] Error scanning {lr_dir}: {e}")
    return deleted


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
        help='Remove ALL generated files (index.html, .thumbs/, .lr/, slideshow.json)'
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
    total_thumbs_deleted = 0
    total_lr_deleted = 0
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
        
        # Get source image stems in this directory
        source_stems = find_source_images(current_path)
        total_source_files += len(source_stems)
        
        if args.verbose:
            print(f"\n{rel_path or 'root'}: {len(source_stems)} source file(s)")
        
        # Check .thumbs directory
        thumbs_dir = current_path / '.thumbs'
        if thumbs_dir.is_dir():
            orphaned_thumbs = cleanup_thumbs(thumbs_dir, source_stems)
            
            # Count thumbnails in this directory
            try:
                thumb_count = sum(1 for e in os.scandir(thumbs_dir) if e.is_file() and e.name.endswith('_thumb.jpg'))
                total_thumbs_found += thumb_count
                if args.verbose and thumb_count > 0:
                    print(f"    .thumbs/: {thumb_count} thumbnail(s), {len(orphaned_thumbs)} orphaned")
            except:
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
            orphaned_lr = cleanup_lr(lr_dir, source_stems)
            
            # Count LR files in this directory
            try:
                lr_count = sum(1 for e in os.scandir(lr_dir) if e.is_file() and e.name.endswith('_LR.jpg'))
                total_lr_found += lr_count
                if args.verbose and lr_count > 0:
                    print(f"    .lr/: {lr_count} LR file(s), {len(orphaned_lr)} orphaned")
            except:
                pass
            
            if orphaned_lr:
                lr_paths = [str(Path(p).relative_to(root_path)) for p in orphaned_lr]
                lr_sizes = sum(os.path.getsize(p) for p in orphaned_lr if Path(p).exists())
                print(f"\n{rel_path}/.lr/")
                print(f"  {len(orphaned_lr)} orphaned LR file(s): {lr_paths}")
                total_lr_deleted += len(orphaned_lr)
                total_bytes_freed += lr_sizes
    
    # Summary before deletion
    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Source files found: {total_source_files}")
    print(f"  Thumbnails found: {total_thumbs_found} ({total_thumbs_deleted} orphaned)")
    print(f"  LR files found: {total_lr_found} ({total_lr_deleted} orphaned)")
    print(f"  Total size to free: {total_bytes_freed / 1024 / 1024:.2f} MB")
    
    if args.dry_run:
        print("\n[Dry run - no files deleted]")
        return 0
    
    # Delete orphaned files
    print("\nDeleting orphaned files...")
    
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_path = Path(dirpath)
        rel_path = current_path.relative_to(root_path)
        
        if any(part.startswith('.') for part in rel_path.parts):
            continue
        
        source_stems = find_source_images(current_path)
        
        # Delete orphaned thumbnails
        thumbs_dir = current_path / '.thumbs'
        if thumbs_dir.is_dir():
            orphaned_thumbs = cleanup_thumbs(thumbs_dir, source_stems)
            for thumb_path in orphaned_thumbs:
                try:
                    os.remove(thumb_path)
                except OSError as e:
                    print(f"  [ERROR] Failed to delete {thumb_path}: {e}")
        
        # Delete orphaned LR files
        lr_dir = current_path / '.lr'
        if lr_dir.is_dir():
            orphaned_lr = cleanup_lr(lr_dir, source_stems)
            for lr_path in orphaned_lr:
                try:
                    os.remove(lr_path)
                except OSError as e:
                    print(f"  [ERROR] Failed to delete {lr_path}: {e}")
    
    print("\nDone! Deleted:")
    print(f"  - {total_thumbs_deleted} thumbnail(s)")
    print(f"  - {total_lr_deleted} LR file(s)")
    print(f"  - Freed {total_bytes_freed / 1024 / 1024:.2f} MB")
    
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
        
        # Remove index.html files
        if 'index.html' in filenames:
            html_file = current_path / 'index.html'
            try:
                size = os.path.getsize(html_file)
                if not dry_run:
                    html_file.unlink()
                deleted_files.append((html_file, size))
                total_freed += size
            except OSError as e:
                print(f"  [ERROR] Failed to delete {html_file}: {e}")
        
        # Remove slideshow.json files
        if 'slideshow.json' in filenames:
            json_file = current_path / 'slideshow.json'
            try:
                size = os.path.getsize(json_file)
                if not dry_run:
                    json_file.unlink()
                deleted_files.append((json_file, size))
                total_freed += size
            except OSError as e:
                print(f"  [ERROR] Failed to delete {json_file}: {e}")
        
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
