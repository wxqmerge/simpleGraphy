import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

PATH = sys.argv[1] if len(sys.argv) > 1 else 'D:/xampp/htdocs/www_misc/index.html'
with open(PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# Find the actual slideshow-header div in HTML body
idx = html.find('<div class="slideshow-header"')
if idx >= 0:
    print("Found slideshow-header div:")
    print(html[idx:idx+600])
else:
    print("slideshow-header div NOT found")
