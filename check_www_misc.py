import re
import json
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else 'D:/xampp/htdocs/www_misc/index.html'
with open(PATH, 'r', encoding='utf-8') as f:
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

# Check currentSubdirs (parse as JSON - never eval scanned content)
match = re.search(r'currentSubdirs = (\[[^\n]*?\]) \|\| \[\];', html)
if match:
    try:
        subdirs = json.loads(match.group(1).replace('<\\/', '</'))
        print(f"currentSubdirs: {len(subdirs)} dirs - {subdirs[:5]}...")
    except ValueError:
        print(f"currentSubdirs: unparsable JSON: {match.group(1)[:120]}...")
else:
    print("currentSubdirs NOT found")
