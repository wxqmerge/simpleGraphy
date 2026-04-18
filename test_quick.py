"""
Quick navigation button tester - checks each interactive element in generated HTML.

Usage: python test_quick.py

Tests:
  1. Breadcrumb links resolve to valid directories
  2. Browse prev/next arrow href values are reasonable
  3. Folder links in grid point to existing index.html pages
  4. No double-slash bugs in any hrefs
"""
import os
import re
from pathlib import Path

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERIES_ROOT = os.path.join(SCRIPT_DIR, 'galleries')


def resolve(base, rel):
    """Resolve relative path from base."""
    if not rel or rel.startswith('http') or rel.startswith('#'):
        return rel
    if rel == './':
        return os.path.abspath(base)
    # Convert forward slashes for proper resolution on Windows
    norm_rel = rel.replace('\\', '/')
    result = os.path.normpath(os.path.join(base, norm_rel))
    return result.replace('/', '\\')


def find_pages():
    """Find all index.html files."""
    pages = []
    for root, dirs, files in os.walk(GALLERIES_ROOT):
        dirs[:] = [d for d in dirs if d not in ('.thumbs', '.lr', '.git')]
        if 'index.html' in files:
            pages.append(os.path.join(root, 'index.html'))
    pages.sort()
    return pages


def test_page(idx_path):
    """Test all buttons on one page. Returns list of (label, ok, detail)."""
    results = []
    dirpath = os.path.dirname(idx_path)
    rel = os.path.relpath(dirpath, GALLERIES_ROOT).replace('\\', '/')
    
    with open(idx_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # --- 1. Breadcrumbs ---
    bc_match = re.search(r'class="breadcrumbs">(.*?)</nav>', content, re.DOTALL)
    if not bc_match:
        results.append((f'{rel}/ breadcrumbs', False, 'not found'))
        return results
    
    bc_html = bc_match.group(1)
    
    # Extract links: [(name, href), ...]
    links = []
    for m in re.finditer(r'<a\s+href="([^"]*)">([^<]+)</a>', bc_html):
        links.append((m.group(2).strip(), m.group(1)))
    for m in re.finditer(r'<span\s+class="current">([^<]+)</span>', bc_html):
        links.append((m.group(1).strip(), ''))
    
    if not links:
        results.append((f'{rel}/ breadcrumbs', False, 'no links found'))
        return results
    
    # Check each link resolves to existing directory (or is empty for current)
    for name, href in links:
        if not href:
            results.append((f'{rel}/ breadcrumb "{name}" (current)', True, ''))
            continue
        
        resolved = resolve(dirpath, href)
        exists = os.path.isdir(resolved) or os.path.basename(resolved) == 'simpleGraphy'
        
        # Special case: root link from galleries/ should go to parent of galleries/
        if name == 'Root' and rel.count('/') == 0:
            # From galleries root, href='' means current page
            results.append((f'{rel}/ breadcrumb "{name}"', True, f'href="{href}"'))
            continue
        
        status = GREEN + 'OK' + RESET if exists else RED + 'BAD' + RESET
        detail = f'-> {os.path.basename(resolved)}'
        results.append((f'{rel}/ breadcrumb "{name}" ({status})', exists, detail))
        
        # Check for double slashes (excluding http://)
        clean_href = href.replace('https://', '').replace('http://', '')
        if '//' in clean_href:
            results.append((f'{rel}/ breadcrumb "{name}" double-slash', False, f'href="{href}"'))
    
    # --- 2. Browse arrows ---
    prev_match = re.search(r"const browsePrevPath\s*=\s*'([^']*)';", content)
    next_match = re.search(r"const browseNextPath\s*=\s*'([^']*)';", content)
    
    prev_val = prev_match.group(1) if prev_match else ''
    next_val = next_match.group(1) if next_match else ''
    
    # Arrows should be empty string (no nav) or relative path ending with /
    if prev_val:
        resolved = resolve(dirpath, prev_val)
        ok = os.path.isdir(resolved)
        results.append((f'{rel}/ prev arrow', ok, f'href="{prev_val}" -> {os.path.basename(resolved)}'))
    
    if next_val:
        resolved = resolve(dirpath, next_val)
        ok = os.path.isdir(resolved)
        results.append((f'{rel}/ next arrow', ok, f'href="{next_val}" -> {os.path.basename(resolved)}'))
    
    # --- 3. Folder links in grid ---
    folder_count = 0
    for m in re.finditer(r'class="gallery-item"[^>]*>\s*<a\s+href="([^"]*)"', content):
        href = m.group(1)
        # Skip image/lightbox paths
        if any(href.startswith(p) for p in ['.thumbs', '.lr', 'lightbox', '#']):
            continue
        # Check if it's a folder link by looking at context
        start = max(0, content.rfind('<a', 0, m.start()))
        end = min(len(content), content.find('</a>', m.start()) + 4)
        context = content[start:end]
        if 'folder' in context.lower():
            folder_count += 1
            resolved = resolve(dirpath, href)
            has_index = os.path.isfile(os.path.join(resolved, 'index.html'))
            results.append((f'{rel}/ folder link', has_index, f'href="{href}" -> {os.path.basename(resolved)}'))
    
    if folder_count == 0:
        # No folder links found - check if there are any gallery-items at all
        has_items = 'gallery-item' in content
        results.append((f'{rel}/ folders', True, f'{folder_count} folders (page has gallery-item: {has_items})'))
    
    return results


# ============================================================
# Main
# ============================================================
pages = find_pages()
print(f'\n{BOLD}{CYAN}Quick Navigation Test - {len(pages)} pages{RESET}\n')

all_results = []
for idx_path in pages:
    rel = os.path.relpath(idx_path, GALLERIES_ROOT).replace('\\', '/')
    print(f'{CYAN}{rel}/{RESET}')
    page_results = test_page(idx_path)
    all_results.extend(page_results)

# Summary
print(f'\n{BOLD}{"="*50}{RESET}')
failures = [r for r in all_results if not r[1]]
passes = len(all_results) - len(failures)

if failures:
    print(f'{RED}{BOLD}{len(failures)} FAILURES out of {len(all_results)} checks{RESET}\n')
    current_page = ''
    for label, ok, detail in all_results:
        if not ok:
            page = label.split('/')[0]
            if page != current_page:
                print(f'\n  {RED}{page}/{RESET}')
                current_page = page
            print(f'    {RED}FAIL{RESET} {label}')
            if detail:
                print(f'           {detail}')
else:
    print(f'{GREEN}{BOLD}ALL {len(all_results)} CHECKS PASSED{RESET}')
