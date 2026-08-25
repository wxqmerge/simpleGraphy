#!/usr/bin/env python3
"""
Caption Generator - Analyzes photos and generates AI captions.

This script generates a queue of images needing captions.
The captions are generated using the vision_vision_analyze_image tool
called by the assistant, then saved as .caption files alongside each image.

Usage:
    python generate_captions.py galleries/
    python generate_captions.py galleries/album_name/
    python generate_captions.py galleries/ --status
    python generate_captions.py galleries/ --list

Arguments:
    root              Directory to scan for images (default: galleries)
    --status          Show captioning progress
    --list            List all images with their caption status
    --export          Export uncaptioned images to a text file for batch processing
"""

import argparse
import os
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif'}
EXCLUDED_DIRS = {'.thumbs', '.lr', '.git', '__pycache__', 'node_modules'}


def get_all_images(root_dir, excluded_dirs=None):
    """Recursively find all image files (excluding generated dirs)."""
    if excluded_dirs is None:
        excluded_dirs = EXCLUDED_DIRS
    images = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = sorted([d for d in dirnames if d not in excluded_dirs])
        for fname in sorted(filenames):
            ext = Path(fname).suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                images.append(os.path.join(dirpath, fname))
    return images


def caption_path(image_path):
    """Get the .caption file path for an image."""
    return image_path + '.caption'


def read_caption(image_path):
    """Read existing caption for an image."""
    cap = caption_path(image_path)
    if os.path.exists(cap):
        with open(cap, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content if content else None
    return None


def write_caption(image_path, text):
    """Write caption for an image."""
    cap = caption_path(image_path)
    with open(cap, 'w', encoding='utf-8') as f:
        f.write(text)


def save_captions_batch(caption_dict):
    """Save a batch of captions. caption_dict: {image_path: caption_text}"""
    saved = 0
    for img_path, caption in caption_dict.items():
        if caption:
            write_caption(img_path, caption)
            saved += 1
    return saved


def main():
    parser = argparse.ArgumentParser(
        description='Generate AI captions for photos in a gallery directory.'
    )
    parser.add_argument('root', nargs='?', default='galleries',
                        help='Root directory to scan (default: galleries)')
    parser.add_argument('--status', action='store_true',
                        help='Show captioning progress')
    parser.add_argument('--list', action='store_true',
                        help='List all images with caption status')
    parser.add_argument('--export', action='store_true',
                        help='Export uncaptioned images to .caption_queue.txt')
    parser.add_argument('--save', nargs=2, metavar=('IMAGE', 'CAPTION'),
                        help='Save a caption for a single image')
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a directory.")
        sys.exit(1)

    # Single image save mode
    if args.save:
        img_path, caption = args.save
        img_path = os.path.join(root, img_path) if not os.path.isabs(img_path) else img_path
        if not os.path.exists(img_path):
            print(f"Error: Image not found: {img_path}")
            sys.exit(1)
        write_caption(img_path, caption)
        print(f"Saved caption for {os.path.basename(img_path)}: {caption}")
        return

    images = get_all_images(root)
    if not images:
        print(f"No images found in {root}")
        return

    captioned = [img for img in images if read_caption(img)]
    uncaptioned = [img for img in images if not read_caption(img)]

    print(f"Directory: {os.path.basename(root)}")
    print(f"Total images: {len(images)}")
    print(f"Captioned:    {len(captioned)}")
    print(f"Uncaptioned:  {len(uncaptioned)}")
    print(f"Progress:     {len(captioned)/len(images)*100:.1f}%")

    if args.list:
        print(f"\n{'Status':<10} {'File':<50} {'Caption'}")
        print('-' * 100)
        for img in images:
            cap = read_caption(img)
            status = "✓" if cap else "✗"
            fname = os.path.relpath(img, root)
            caption_preview = (cap[:60] + '...') if cap and len(cap) > 60 else (cap or '')
            print(f"{status:<10} {fname:<50} {caption_preview}")
        return

    if args.export:
        queue_path = os.path.join(root, '.caption_queue.txt')
        with open(queue_path, 'w', encoding='utf-8') as f:
            for img in uncaptioned:
                f.write(img + '\n')
        print(f"\nExported {len(uncaptioned)} uncaptioned images to {queue_path}")
        return

    # Default: show status summary
    if uncaptioned:
        print(f"\nFirst 10 uncaptioned:")
        for img in uncaptioned[:10]:
            print(f"  {os.path.relpath(img, root)}")
        if len(uncaptioned) > 10:
            print(f"  ... and {len(uncaptioned) - 10} more")


if __name__ == '__main__':
    main()
