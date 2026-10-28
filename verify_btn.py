import sys
sys.stdout.reconfigure(encoding='utf-8')

PATH = sys.argv[1] if len(sys.argv) > 1 else 'D:/xampp/htdocs/www_misc/index.html'
with open(PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# Find the slideshow-header div
idx = html.find('<div class="slideshow-header"')
if idx >= 0:
    print("Slideshow button:")
    print(html[idx:idx+400])

# Find currentSubdirs initialization
idx2 = html.find('currentSubdirs = [' )
if idx2 >= 0:
    print("\ncurrentSubdirs initialization:")
    print(html[idx2:idx2+300])
else:
    print("\ncurrentSubdirs NOT found")
