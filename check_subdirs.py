import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else 'D:/xampp/htdocs/www_misc/index.html'
with open(PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# Find the currentSubdirs initialization line (emitted as: currentSubdirs = [...] || [];)
match = re.search(r'currentSubdirs = (\[[^\]]*\]) \|\| \[\];', html)
if match:
    print(f"Found currentSubdirs assignment:")
    print(match.group(1)[:200])
else:
    print("currentSubdirs NOT found - checking nearby code...")
    idx = html.find('Sequential slideshow pool')
    if idx >= 0:
        print(html[idx:idx+500])
