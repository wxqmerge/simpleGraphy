import sys
sys.stdout.reconfigure(encoding='utf-8')

# Patch the function to add debugging
original_generate_html = None

def patched_generate_html(directory, output_dir, root_path, thumb_size, force=False, parent_path=None, random_depth=None, enable_slideshow=False, enable_random=False):
    from generate_gallery import get_subdirectory_list, get_slideshow_images, get_random_pool
    
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
    
    # Call original
    return original_generate_html(directory, output_dir, root_path, thumb_size, force, parent_path, random_depth, enable_slideshow, enable_random)

import generate_gallery
original_generate_html = generate_gallery.generate_html
generate_gallery.generate_html = patched_generate_html

# Now run the generation
if __name__ == '__main__':
    import os
    os.chdir('D:/xampp/htdocs/simpleGraphy')
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
