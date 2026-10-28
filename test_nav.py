"""
Quick navigation test script.
Tests breadcrumb links and prev/next arrows for all directory levels.

Usage: python test_nav.py
"""
import os
import sys
import html
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_gallery import get_sibling_nav, EXCLUDED_DIRS, collect_dirs_with_images, build_breadcrumbs


# ============================================================
# Breadcrumbs come from generate_gallery.build_breadcrumbs itself,
# so this test exercises the real production code path.
# ============================================================
compute_breadcrumbs = build_breadcrumbs


# ============================================================
# Test harness
# ============================================================
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

passed = 0
failed = 0


def check(label, actual, expected):
    global passed, failed
    status = GREEN + 'PASS' + RESET if actual == expected else RED + 'FAIL' + RESET
    if actual == expected:
        passed += 1
    else:
        failed += 1
        print(f'  {RED}X{RESET} {label}')
        print(f'        Actual:   "{actual}"')
        print(f'        Expected: "{expected}"')


def check_contains(label, actual, expected):
    global passed, failed
    status = GREEN + 'PASS' + RESET if expected in actual else RED + 'FAIL' + RESET
    if expected in actual:
        passed += 1
    else:
        failed += 1
        print(f'  {RED}X{RESET} {label}')
        print(f'        Actual:   "{actual}"')
        print(f'        Expected to contain: "{expected}"')


# ============================================================
# Test cases for simpleGraphy/galleries structure
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERIES_ROOT = os.path.join(SCRIPT_DIR, 'galleries')

print(f'\n{YELLOW}Testing gallery navigation from: {GALLERIES_ROOT}{RESET}\n')


# --- Helper: resolve relative paths to see where they actually go ---
def resolve(base_path, link):
    """Resolve a relative path from base_path."""
    if not link or link.startswith('http'):
        return link
    if link == './':
        return base_path
    resolved = os.path.normpath(os.path.join(base_path, link))
    return resolved


# ============================================================
# Test 1: Breadcrumbs at different depths
# ============================================================
print(f'{YELLOW}=== TEST 1: Breadcrumb Links ==={RESET}')

# Depth-2: galleries/26/ (one level deep from root)
dir_2 = os.path.join(GALLERIES_ROOT, '26')
bc_2 = compute_breadcrumbs(dir_2, GALLERIES_ROOT)
page_base_2 = dir_2

print(f'\n  Depth-2: {os.path.relpath(dir_2, GALLERIES_ROOT)}/')
for item in bc_2:
    resolved = resolve(page_base_2, item['link'])
    print(f'    {item["name"]}: href="{item["link"]}" -> resolves to "{os.path.basename(resolved)}"')

# Check depth-1 breadcrumbs (galleries/26/)
check('  Depth-1 Root link', bc_2[0]['link'], '../index.html')
check('  Depth-1 26/ link', bc_2[1]['link'], 'index.html')


# Depth-2: galleries/26/260330_France_Trip/
dir_3 = os.path.join(GALLERIES_ROOT, '26', '260330_France_Trip')
bc_3 = compute_breadcrumbs(dir_3, GALLERIES_ROOT)
page_base_3 = dir_3

print(f'\n  Depth-2: {os.path.relpath(dir_3, GALLERIES_ROOT)}/')
for item in bc_3:
    resolved = resolve(page_base_3, item['link'])
    print(f'    {item["name"]}: href="{item["link"]}" -> resolves to "{resolved}"')

check('  Depth-2 Root link', bc_3[0]['link'], '../../index.html')
check('  Depth-2 26/ link', bc_3[1]['link'], '../index.html')
check('  Depth-2 France_Trip link', bc_3[2]['link'], 'index.html')


# Depth-3: galleries/26/260330_France_Trip/260318_iceland/
dir_4 = os.path.join(GALLERIES_ROOT, '26', '260330_France_Trip', '260318_iceland')
bc_4 = compute_breadcrumbs(dir_4, GALLERIES_ROOT)
page_base_4 = dir_4

print(f'\n  Depth-3: {os.path.relpath(dir_4, GALLERIES_ROOT)}/')
for item in bc_4:
    resolved = resolve(page_base_4, item['link'])
    print(f'    {item["name"]}: href="{item["link"]}" -> resolves to "{resolved}"')

check('  Depth-3 Root link', bc_4[0]['link'], '../../../index.html')
check('  Depth-3 26/ link', bc_4[1]['link'], '../../index.html')
check('  Depth-3 France_Trip link', bc_4[2]['link'], '../index.html')


# ============================================================
# Test 2: Prev/Next arrows (sibling-only)
# ============================================================
print(f'\n{YELLOW}=== TEST 2: Prev/Next Arrow Navigation ==={RESET}')


# Build the directory set exactly like production does (walk_and_generate):
# every dir with images or image-bearing descendants gets an index.html, and
# get_sibling_nav must only ever link to those dirs.
all_dirs = collect_dirs_with_images(GALLERIES_ROOT)

tested = 0
for d in sorted(all_dirs):
    rel_name = os.path.relpath(d, GALLERIES_ROOT).replace('\\', '/')
    if rel_name == '.':
        continue  # root: no sibling nav by design
    prev, next_ = get_sibling_nav(d, all_dirs, GALLERIES_ROOT)
    for kind, link in (('prev', prev), ('next', next_)):
        if not link:
            continue
        resolved = resolve(d, link)
        # Every non-empty arrow must resolve to an existing index.html page
        check(f'  {rel_name}/ {kind} -> page exists', os.path.isfile(resolved), True)
        tested += 1

# Spot-check the documented nav rules on the canonical structure
if os.path.isdir(os.path.join(GALLERIES_ROOT, '26')):
    prev, next_ = get_sibling_nav(os.path.join(GALLERIES_ROOT, '26'), all_dirs, GALLERIES_ROOT)
    check('  26/ prev (first child of root)', prev, '')

print(f'\n  ({tested} arrow links verified to resolve to real pages)')


# ============================================================
# Test 3: Verify the actual HTML output matches expectations
# ============================================================
print(f'\n{YELLOW}=== TEST 3: HTML Breadcrumb Links ==={RESET}')

# Read generated index.html files and check breadcrumb links
index_files = [
    os.path.join(GALLERIES_ROOT, '26', 'index.html'),
    os.path.join(GALLERIES_ROOT, '26', '260330_France_Trip', 'index.html'),
]

for idx_path in index_files:
    if not os.path.isfile(idx_path):
        print(f'  {YELLOW}SKIPPED{RESET} {os.path.relpath(idx_path, GALLERIES_ROOT)} (no index.html)')
        continue
    
    with open(idx_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract breadcrumb nav line
    import re
    match = re.search(r'class="breadcrumbs">(.*?)</nav>', content, re.DOTALL)
    if not match:
        print(f'  {RED}FAIL{RESET} {os.path.relpath(idx_path, GALLERIES_ROOT)} (no breadcrumbs found)')
        failed += 1
        continue
    
    nav_content = match.group(1).strip()
    rel_dir = os.path.relpath(os.path.dirname(idx_path), GALLERIES_ROOT)
    
    print(f'\n  {rel_dir}/:')
    
    # Extract all hrefs
    hrefs = re.findall(r'href="([^"]*)"', nav_content)
    for i, href in enumerate(hrefs):
        resolved = resolve(os.path.dirname(idx_path), href)
        rel_resolved = os.path.relpath(resolved, GALLERIES_ROOT)
        print(f'    Link {i+1}: "{href}" -> "{rel_resolved}"')
    
    # Check for double-slash bugs
    if '//' in nav_content.replace('https://', '').replace('http://', ''):
        print(f'  {RED}FAIL{RESET} Double slashes detected in breadcrumbs!')
        failed += 1
    else:
        print(f'  {GREEN}OK{RESET} No double-slash issues')
        passed += 1


# ============================================================
# Summary
# ============================================================
total = passed + failed
print(f'\n{"="*50}')
if failed == 0:
    print(f'{GREEN}ALL TESTS PASSED ({passed}/{total}){RESET}\n')
else:
    print(f'{RED}{failed} FAILURES, {passed} PASSED out of {total}{RESET}\n')
    print('Fix the failures and re-run to verify.')

sys.exit(0 if failed == 0 else 1)
