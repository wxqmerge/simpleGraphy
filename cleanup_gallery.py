#!/usr/bin/env python3
"""
Gallery Cleanup - Removes orphaned thumbnail and LR files.

Scans gallery directories and deletes .thumbs/ and .lr/ files that don't
have corresponding source images (e.g., after deleting photos).

Usage:
    python cleanup_gallery.py galleries/
    python cleanup_gallery.py galleries/ --dry-run   # Preview only
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
                # Extract original filename stem
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
    
    args = parser.parse_args()
    root_path = Path(args.root).resolve()
    
    if not root_path.is_dir():
        print(f"Error: Directory not found: {root_path}")
        return 1
    
    # Counters
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
        
        # Check .thumbs directory
        thumbs_dir = current_path / '.thumbs'
        if thumbs_dir.is_dir():
            orphaned_thumbs = cleanup_thumbs(thumbs_dir, source_stems)
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
            if orphaned_lr:
                lr_paths = [str(Path(p).relative_to(root_path)) for p in orphaned_lr]
                lr_sizes = sum(os.path.getsize(p) for p in orphaned_lr if Path(p).exists())
                print(f"\n{rel_path}/.lr/")
                print(f"  {len(orphaned_lr)} orphaned LR file(s): {lr_paths}")
                total_lr_deleted += len(orphaned_lr)
                total_bytes_freed += lr_sizes
    
    # Summary before deletion
    print("\n" + "=" * 60)
    print(f"Found {total_thumbs_deleted} orphaned thumbnail(s) and {total_lr_deleted} orphaned LR file(s)")
    print(f"Total size to free: {total_bytes_freed / 1024 / 1024:.2f} MB")
    
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


if __name__ == '__main__':
    exit(main())
