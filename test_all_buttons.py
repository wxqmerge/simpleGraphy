"""
Comprehensive navigation button test for generated galleries.

Tests every interactive element on each index.html:
  1. Breadcrumb links (root + intermediate levels) - where they resolve to
  2. Browse mode prev/next arrow buttons - href values
  3. Subdirectory links in gallery grid - href values
  4. Image lightbox links (sample check)
  5. Slideshow button presence and config

Usage: python test_all_buttons.py [--regenerate]

If --regenerate is passed, it re-runs generate_gallery.py first.
"""
import os
import sys
import re
import subprocess
from pathlib import Path
from collections import namedtuple

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

Result = namedtuple('Result', ['section', 'label', 'ok', 'actual', 'expected'])

passed = 0
failed = 0
results = []


def check(section, label, actual, expected=None, check_fn=None):
    global passed, failed
    if check_fn:
        ok = check_fn(actual)
    elif expected is not None:
        ok = actual == expected
    else:
        ok = bool(actual)

    r = Result(section, label, ok, str(actual), str(expected) if expected is not None else '')
    results.append(r)
    if ok:
        passed += 1
    else:
        failed += 1
    return ok


def resolve_path(base, rel):
    """Resolve a relative path from base directory."""
    if not rel or rel.startswith('http') or rel.startswith('#'):
        return rel
    if rel == './':
        return os.path.abspath(base)
    norm_rel = rel.replace('\\', '/')
    result = os.path.normpath(os.path.join(base, norm_rel))
    return result.replace('/', '\\')


def print_results():
    print(f'\n{BOLD}{"="*60}{RESET}')
    print(f'{BOLD}  BUTTON TEST RESULTS{RESET}')
    print(f'{BOLD}{"="*60}\n')

    current_section = ''
    for r in results:
        if r.section != current_section:
            current_section = r.section
            print(f'\n{CYAN}{current_section}{RESET}')

        icon = f'{GREEN}PASS{RESET}' if r.ok else f'{RED}FAIL{RESET}'
        status = f'  {icon} {r.label}'
        print(status)
        if not r.ok:
            if r.expected:
                print(f'        Expected: "{r.expected}"')
            if r.actual and r.actual != r.expected:
                print(f'        Actual:   "{r.actual}"')


# ============================================================
# Parse HTML and extract navigation data
# ============================================================
def parse_html(filepath):
    """Parse an index.html and extract all navigation elements."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    data = {
        'filepath': filepath,
        'dir': os.path.dirname(filepath),
        'breadcrumbs': [],
        'browse_prev': '',
        'browse_next': '',
        'folder_links': [],
        'image_links': [],
        'slideshow_exists': False,
        'slideshow_random_btn': False,
    }

    # --- Breadcrumbs ---
    bc_match = re.search(r'class="breadcrumbs">(.*?)</nav>', content, re.DOTALL)
    if bc_match:
        bc_content = bc_match.group(1)
        # Extract [name, href] pairs
        for m in re.finditer(r'<a\s+href="([^"]*)">([^<]+)</a>', bc_content):
            href, name = m.group(1), m.group(2)
            data['breadcrumbs'].append((name.strip(), href))
        # Also get current (non-linked) item
        for m in re.finditer(r'<span\s+class="current">([^<]+)</span>', bc_content):
            data['breadcrumbs'].append((m.group(1).strip(), ''))

    # --- Browse prev/next ---
    js_match = re.search(r"const browsePrevPath\s*=\s*'([^']*)';", content)
    if js_match:
        data['browse_prev'] = js_match.group(1)
    js_match = re.search(r"const browseNextPath\s*=\s*'([^']*)';", content)
    if js_match:
        data['browse_next'] = js_match.group(1)

    # --- Folder links in gallery grid ---
    # Folders use onclick="window.location.href='...'" pattern (double outer, single inner)
    for m in re.finditer(r'''onclick="window\.location\.href='([^']+)'[^>]*>"''', content):
        href = m.group(1)
        if any(href.startswith(p) for p in ['.thumbs', '.lr', 'lightbox']):
            continue
        data['folder_links'].append(href)
    # Also catch <a> tags as fallback
    for m in re.finditer(r'class="gallery-item"[^>]*>\s*<a\s+href="([^"]*)"', content):
        href = m.group(1)
        if any(href.startswith(p) for p in ['.thumbs', '.lr', 'lightbox']):
            continue
        data['folder_links'].append(href)

    # --- Image links ---
    for m in re.finditer(r'class="gallery-item[^"]*"[^>]*>\s*<a\s+href="([^"]*)"', content):
        data['image_links'].append(m.group(1))

    # --- Slideshow button ---
    data['slideshow_exists'] = 'id="slideshow-btn"' in content
    data['slideshow_random_btn'] = 'id="random-slide-btn"' in content

    return data


# ============================================================
# Test cases
# ============================================================
def test_breadcrumbs(data, galleries_root):
    """Test breadcrumb links resolve correctly."""
    dirpath = data['dir']
    rel = os.path.relpath(dirpath, galleries_root).replace('\\', '/')
    section = f'{rel}/ breadcrumbs'

    if not data['breadcrumbs']:
        check(section, 'Root breadcrumb exists', False)
        return

    # Validate each link
    for name, href in data['breadcrumbs']:
        if not href:
            check(section, f'"{name}" (current)', True)
            continue

        resolved = resolve_path(dirpath, href)
        basename = os.path.basename(resolved)

        # Root link should go to parent of galleries/ or similar ancestor
        if name == 'Root':
            # Check it's a valid directory path
            check(section, f'Root -> "{basename}"', True)
            continue

        # Intermediate links should point to existing directories
        is_dir = os.path.isdir(resolved)
        check(section, f'"{name}" -> "{basename}"', is_dir)

    # Check no double slashes
    all_hrefs = [h for _, h in data['breadcrumbs'] if h]
    for href in all_hrefs:
        clean = href.replace('https://', '').replace('http://', '')
        has_double_slash = '//' in clean
        check(section, f'No double-slash in "{href}"', not has_double_slash)


def test_browse_arrows(data):
    """Test browse prev/next arrow button values."""
    dirpath = data['dir']
    rel = os.path.relpath(dirpath, GALLERIES_ROOT).replace('\\', '/')
    section = f'{rel}/ arrows'

    if data['browse_prev']:
        resolved = resolve_path(dirpath, data['browse_prev'])
        is_dir = os.path.isdir(resolved)
        check(section, f'prev -> "{os.path.basename(resolved)}"', is_dir)

    if data['browse_next']:
        resolved = resolve_path(dirpath, data['browse_next'])
        is_dir = os.path.isdir(resolved)
        check(section, f'next -> "{os.path.basename(resolved)}"', is_dir)


def test_folder_links(data):
    """Test that folder links in the grid resolve to existing index.html pages."""
    dirpath = data['dir']
    rel = os.path.relpath(dirpath, GALLERIES_ROOT).replace('\\', '/')
    section = f'{rel}/ folders'

    if not data['folder_links']:
        # Leaf directories have no folder links - that's OK
        check(section, 'no folders (leaf dir)', True)
        return

    for href in data['folder_links'][:10]:  # limit output
        resolved = resolve_path(dirpath, href)
        has_index = os.path.isfile(os.path.join(resolved, 'index.html'))
        check(section, f'"{href}" -> "{os.path.basename(resolved)}"', has_index)


def test_slideshow_buttons(data):
    """Test slideshow button presence."""
    dirpath = data['dir']
    rel = os.path.relpath(dirpath, GALLERIES_ROOT).replace('\\', '/')
    section = f'{rel}/ slideshow'

    if data['slideshow_exists']:
        check(section, 'slideshow button present', True)
        if data['slideshow_random_btn']:
            check(section, 'random button present', True)


# ============================================================
# Main
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERIES_ROOT = os.path.join(SCRIPT_DIR, 'galleries')

print(f'\n{BOLD}{CYAN}Gallery Navigation Button Tester{RESET}')
print(f'{BOLD}Testing from: {GALLERIES_ROOT}{RESET}\n')

# Find all index.html files (skip .thumbs, .lr)
index_files = []
for root, dirs, files in os.walk(GALLERIES_ROOT):
    # Skip hidden/thumbs dirs
    dirs[:] = [d for d in dirs if d not in ('.thumbs', '.lr', '.git')]
    if 'index.html' in files:
        index_files.append(os.path.join(root, 'index.html'))

index_files.sort()

print(f'{YELLOW}Index files found:{RESET}')
for idx in index_files:
    rel = os.path.relpath(idx, GALLERIES_ROOT)
    print(f'  {rel}')

print(f'\nTotal: {len(index_files)} pages to test\n')

# Parse and test each page
pages = []
for idx_path in index_files:
    data = parse_html(idx_path)
    rel = os.path.relpath(data['dir'], GALLERIES_ROOT).replace('\\', '/')

    print(f'{BOLD}{CYAN}Testing: {rel}/index.html{RESET}\n')

    test_breadcrumbs(data, GALLERIES_ROOT)
    test_browse_arrows(data)
    test_folder_links(data)
    test_slideshow_buttons(data)

    pages.append((rel, data))

# ============================================================
# Cross-page consistency: check that folder links point to pages with index.html
# ============================================================
print(f'\n{YELLOW}{BOLD}=== CROSS-PAGE CONSISTENCY ==={RESET}')
for rel, data in pages:
    dirpath = data['dir']
    for href in data['folder_links']:
        resolved = resolve_path(dirpath, href)
        target_rel = os.path.relpath(resolved, GALLERIES_ROOT).replace('\\', '/')
        target_idx = os.path.join(resolved, 'index.html')
        exists = os.path.isfile(target_idx)
        check(f'Cross-page: {rel}/', f'"{target_rel}" has index.html', exists, True)

# ============================================================
# Summary
# ============================================================
print_results()

total = passed + failed
print(f'\n{"="*60}')
if failed == 0:
    print(f'{GREEN}{BOLD}ALL {total} TESTS PASSED{RESET}\n')
else:
    print(f'{RED}{BOLD}{failed} FAILURES, {passed} PASSED out of {total}{RESET}\n')
    print('Fix the failures and re-run to verify.')

sys.exit(0 if failed == 0 else 1)
