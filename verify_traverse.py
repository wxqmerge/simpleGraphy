import os
import re

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'galleries', 'index.html')
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# Check loadNextDirectory function exists and has the right logic
if 'findSubdirInTree(dirTreeData, subPath)' in html:
    print("+ Full-path subdir lookup found")
else:
    print("- Full-path subdir lookup NOT found")

if 'dirs: currentSubdirs.slice(), index: subdirIndex, path: currentDirPath' in html:
    print("+ Parent-state push (with path) found")
else:
    print("- Parent-state push (with path) NOT found")

if 'function buildDirNavList()' in html and 'walk(subdir, path + subdir.name' in html:
    print("+ dirNavList built from embedded tree")
else:
    print("- dirNavList NOT built from embedded tree (stale AJAX impl?)")

# Check currentSubdirs initialization (the flat name list ending in || []; )
match = re.search(r'currentSubdirs = (\[[^\]]*\]) \|\| \[\];', html, re.DOTALL)
if match:
    print(f"currentSubdirs: {match.group(1)[:80]}...")
else:
    print("currentSubdirs NOT found")
