import re

with open('galleries/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Check loadNextDirectory function exists and has the right logic
if 'hasImages || hasChildren' in html:
    print("+ hasImages || hasChildren check found")
else:
    print("- hasImages || hasChildren check NOT found")

if 'subdirIndex + 1' in html:
    print("+ subdirIndex + 1 push found")
else:
    print("- subdirIndex + 1 push NOT found")

if 'subdirCache.has' in html:
    print("+ Cache lookup found")
else:
    print("- Cache lookup NOT found")

# Check currentSubdirs initialization
match = re.search(r'currentSubdirs = (\[.*?\])', html)
if match:
    print(f"currentSubdirs: {match.group(1)[:80]}...")
else:
    print("currentSubdirs NOT found")
