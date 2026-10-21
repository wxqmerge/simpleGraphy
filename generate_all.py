#!/usr/bin/env python3
"""Generate galleries for every www_* directory under a base path.

Intended for the server (/var/www), where legacy site dirs live beside each
other: www_chess, www_daa, www_family, www_misc, www_sothh ...

For each matching directory it runs generate_gallery.py in place, so every
directory with images gets an index.html + .thumbs/. Failures are logged and
the run continues; exit code is non-zero if any directory failed.

Examples (on the server):
  python3 generate_all.py                          # all www_* in /var/www
  python3 generate_all.py --dry-run                # show what would run
  python3 generate_all.py --only www_daa www_misc  # just these
  python3 generate_all.py --exclude www_sothh      # everything except
  python3 generate_all.py -- --slideshow --random  # flags for generate_gallery.py
  python3 generate_all.py --force -- --thumb-size 300

Cron (daily 01:30, after the main gallery job):
  30 1 * * * cd /var/www && /usr/bin/python3 generate_all.py >> /var/www/gallery_all_cron.log 2>&1
"""

import argparse
import fnmatch
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_BASE = '/var/www'
DEFAULT_PATTERN = 'www_*'
SCRIPT_CANDIDATES = [
    None,  # filled: dir of this script
    '/var/www/html/mattshare/generate_gallery.py',
]


def ts():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def log(msg):
    print(f'[{ts()}] {msg}', flush=True)


def find_script(explicit):
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        sys.exit(f'ERROR: generate_gallery.py not found at {explicit}')
    candidates = []
    here = Path(__file__).resolve().parent / 'generate_gallery.py'
    candidates.append(here)
    candidates.extend(Path(c) for c in SCRIPT_CANDIDATES if c)
    env = os.environ.get('GALLERY_SCRIPT')
    if env:
        candidates.insert(0, Path(env))
    for c in candidates:
        if c.is_file():
            return c
    sys.exit('ERROR: generate_gallery.py not found (use --script or GALLERY_SCRIPT)')


def main():
    argv = sys.argv[1:]
    passthrough = []
    if '--' in argv:
        i = argv.index('--')
        argv, passthrough = argv[:i], argv[i + 1:]

    parser = argparse.ArgumentParser(
        description='Run generate_gallery.py over every www_* directory.',
        epilog='Flags after -- are passed through to generate_gallery.py '
               '(e.g. -- --slideshow --random --thumb-size 300)')
    parser.add_argument('--base', default=os.environ.get('GALLERY_BASE', DEFAULT_BASE),
                        help=f'Base directory to scan (default: {DEFAULT_BASE})')
    parser.add_argument('--pattern', default=DEFAULT_PATTERN,
                        help=f'Glob for subdirectories (default: {DEFAULT_PATTERN})')
    parser.add_argument('--script', default=None,
                        help='Path to generate_gallery.py (default: auto-detect)')
    parser.add_argument('--only', nargs='*', metavar='NAME',
                        help='Process only these directory names')
    parser.add_argument('--exclude', nargs='*', metavar='PATTERN',
                        help='Skip directories matching these glob patterns')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Pass --force to generate_gallery.py')
    parser.add_argument('--timeout', type=int, default=0,
                        help='Per-directory timeout in seconds (0 = none)')
    parser.add_argument('--dry-run', action='store_true',
                        help='List what would be processed, run nothing')
    parser.add_argument('names', nargs='*', metavar='DIR',
                        help='Explicit directory names to process (overrides --pattern)')
    args, unknown = parser.parse_known_args(argv)
    passthrough.extend(unknown)
    if args.force:
        passthrough.append('--force')

    base = Path(args.base)
    if not base.is_dir():
        sys.exit(f'ERROR: base directory not found: {base}')

    script = find_script(args.script)

    if args.names:
        targets = [base / n for n in args.names]
    elif args.only:
        targets = [base / n for n in args.only]
    else:
        targets = sorted(p for p in base.iterdir()
                         if p.is_dir() and not p.is_symlink()
                         and fnmatch.fnmatch(p.name, args.pattern))

    if args.exclude:
        targets = [t for t in targets
                   if not any(fnmatch.fnmatch(t.name, pat) for pat in args.exclude)]

    if not targets:
        log(f'No directories matching {args.pattern!r} in {base}')
        return 0

    log(f'generate_all: {len(targets)} director'
        f'{"y" if len(targets) == 1 else "ies"} under {base} | script={script}')

    if args.dry_run:
        for t in targets:
            status = 'OK' if t.is_dir() else 'MISSING'
            log(f'  [{status}] would run: {sys.executable} {script} {t}'
                + (f' {" ".join(passthrough)}' if passthrough else ''))
        return 0

    results = []
    for t in targets:
        if not t.is_dir():
            log(f'SKIP {t.name}: not a directory')
            results.append((t.name, 'missing', 0.0))
            continue
        cmd = [sys.executable, str(script), str(t)] + passthrough
        log(f'RUN {t.name} ...')
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, timeout=args.timeout or None)
            dt = time.time() - t0
            if proc.returncode == 0:
                log(f'DONE {t.name} ({dt:.1f}s)')
                results.append((t.name, 'ok', dt))
            else:
                log(f'FAIL {t.name} (exit {proc.returncode}, {dt:.1f}s)')
                results.append((t.name, f'exit {proc.returncode}', dt))
        except subprocess.TimeoutExpired:
            dt = time.time() - t0
            log(f'FAIL {t.name} (timeout after {dt:.0f}s)')
            results.append((t.name, 'timeout', dt))
        except Exception as e:
            dt = time.time() - t0
            log(f'FAIL {t.name}: {e}')
            results.append((t.name, 'error', dt))

    ok = sum(1 for _, s, _ in results if s == 'ok')
    log(f'=== Summary: {ok}/{len(results)} ok ===')
    for name, status, dt in results:
        log(f'  {name:<20} {status:<10} {dt:>7.1f}s')
    return 0 if ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
