import re
import sys

with open('D:/xampp/htdocs/www_misc/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Check for slideshow buttons
if '▶ Slideshow' in html:
    match = re.search(r'> Slideshow \((\d+)\)', html)
    if match:
        print(f"+ Sequential slideshow button found: Slideshow ({match.group(1)})")
    else:
        print("+ Sequential slideshow button found (count unknown)")
else:
    print("- Sequential slideshow button NOT found")

if 'Random' in html and 'random-btn' in html:
    match = re.search(r'Random \((\d+)\)', html)
    if match:
        print(f"+ Random slideshow button found: Random ({match.group(1)})")
    else:
        print("+ Random slideshow button found (count unknown)")
else:
    print("- Random slideshow button NOT found")

# Check currentSubdirs
match = re.search(r'currentSubdirs = (\[.*?\])', html)
if match:
    subdirs = eval(match.group(1))
    print(f"currentSubdirs: {len(subdirs)} dirs - {subdirs[:5]}...")
