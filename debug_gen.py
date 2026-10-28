import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# Run from the repo root so relative paths resolve (skip if not on this machine)
if os.path.isdir('D:/simpleGraphy'):
    os.chdir('D:/simpleGraphy')

# Patch the function to add debugging
original_generate_html = None


def patched_generate_html(*args, **kwargs):
    from generate_gallery import get_subdirectory_list, get_slideshow_images

    # *args/**kwargs passthrough: stays valid as generate_html's signature evolves
    directory = args[0] if args else kwargs.get('directory')
    output_dir = args[1] if len(args) > 1 else kwargs.get('output_dir', directory)
    enable_slideshow = kwargs.get('enable_slideshow', False)

    sequential_images = []
    subdirs_list = []

    if enable_slideshow:
        sequential_images = get_slideshow_images(directory, output_dir)
        subdirs_list = get_subdirectory_list(directory)
        print(f"DEBUG generate_html for {directory}")
        print(f"  enable_slideshow={enable_slideshow}")
        print(f"  sequential_images count: {len(sequential_images)}")
        print(f"  subdirs_list count: {len(subdirs_list)}")
        if subdirs_list:
            print(f"  first 5 subdirs: {subdirs_list[:5]}")

    # Call original with the exact same arguments
    return original_generate_html(*args, **kwargs)


import generate_gallery
original_generate_html = generate_gallery.generate_html
generate_gallery.generate_html = patched_generate_html

# Now run the generation
if __name__ == '__main__':
    from generate_gallery import parse_args, walk_and_generate
    
    args = parse_args()
    args.root = 'D:/xampp/htdocs/www_misc'
    args.output_root = None
    args.thumb_size = 400
    args.force = False
    args.random_depth = None
    args.slideshow = True
    args.random = True
    
    root_path = os.path.abspath(args.root)
    output_root = os.path.abspath(args.output_root or args.root)
    
    walk_and_generate(root_path, output_root, args.thumb_size, args.force, args.random_depth, args.slideshow, args.random)
