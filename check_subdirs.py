import re

with open('D:/xampp/htdocs/www_misc/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the currentSubdirs initialization line
match = re.search(r'currentSubdirs = (.+?);\s*\|\| \[\];', html, re.DOTALL)
if match:
    print(f"Found currentSubdirs assignment:")
    print(match.group(1)[:200])
else:
    # Try alternate pattern
    match = re.search(r'currentSubdirs = (\[.*?\]);', html, re.DOTALL)
    if match:
        print(f"Found currentSubdirs (alt): {match.group(1)[:200]}")
    else:
        print("currentSubdirs NOT found - checking nearby code...")
        idx = html.find('Sequential slideshow images')
        if idx >= 0:
            print(html[idx:idx+500])
