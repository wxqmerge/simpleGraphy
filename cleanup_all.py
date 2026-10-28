#!/usr/bin/env python3
"""Run cleanup_gallery.py over every www_* directory under a base path.

Companion to generate_all.py (same CLI shape). Intended for the server
(/var/www), where the site repos live beside each other:
www_chess, www_daa, www_family, www_misc ...

For each matching directory it runs cleanup_gallery.py in place, removing
orphaned .thumbs/.lr assets (and, after the asset-naming migration, all
legacy stem-named files). Failures are logged and the run continues; exit
code is non-zero if any directory failed.

Examples (on the server):
  python3 cleanup_all.py --dry-run               # preview all sites
  python3 cleanup_all.py                         # clean all sites
  python3 cleanup_all.py --only www_daa          # just one
  python3 cleanup_all.py --exclude www_sothh     # everything except
  python3 cleanup_all.py -- --all                # remove ALL generated files

Cron (after the generation job):
  45 1 * * * cd /var/www && /usr/bin/python3 cleanup_all.py >> /var/www/gallery_clean_cron.log 2>&1
"""

import argparse
import fnmatch
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_BASE = '/var/www'
DEFAULT_PATTERN = 'www_*'
SCRIPT_CANDIDATES = [
    '/var/www/cleanup_gallery.py',
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
        sys.exit(f'ERROR: cleanup_gallery.py not found at {explicit}')
    candidates = [Path(__file__).resolve().parent / 'cleanup_gallery.py']
    candidates.extend(Path(c) for c in SCRIPT_CANDIDATES if c)
    env = os.environ.get('CLEANUP_SCRIPT')
    if env:
        candidates.insert(0, Path(env))
    for c in candidates:
        if c.is_file():
            return c
    sys.exit('ERROR: cleanup_gallery.py not found (use --script or CLEANUP_SCRIPT)')


def run_with_timeout(cmd, timeout):
    """Run cmd, killing the whole process tree on timeout (not just the direct child)."""
    kwargs = {}
    if os.name == 'posix':
        kwargs['start_new_session'] = True
    else:
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(cmd, **kwargs)
    try:
        proc.communicate(timeout=timeout or None)
        return proc.returncode
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                proc.kill()
        else:
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                           capture_output=True)
        proc.communicate()
        raise


def main():
    argv = sys.argv[1:]
    passthrough = []
    if '--' in argv:
        i = argv.index('--')
        argv, passthrough = argv[:i], argv[i + 1:]

    parser = argparse.ArgumentParser(
        description='Run cleanup_gallery.py over every www_* directory.',
        epilog='Flags after -- are passed through to cleanup_gallery.py '
               '(e.g. -- --all or -- --verbose)')
    parser.add_argument('--base', default=os.environ.get('CLEANUP_BASE', DEFAULT_BASE),
                        help=f'Base directory to scan (default: {DEFAULT_BASE})')
    parser.add_argument('--pattern', default=DEFAULT_PATTERN,
                        help=f'Glob for subdirectories (default: {DEFAULT_PATTERN})')
    parser.add_argument('--script', default=None,
                        help='Path to cleanup_gallery.py (default: auto-detect)')
    parser.add_argument('--only', nargs='*', metavar='NAME',
                        help='Process only these directory names')
    parser.add_argument('--exclude', nargs='*', metavar='PATTERN',
                        help='Skip directories matching these glob patterns')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Forward --dry-run to cleanup_gallery.py (and list targets)')
    parser.add_argument('--all', action='store_true',
                        help='Pass --all to cleanup_gallery.py (remove all generated files)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Pass --verbose to cleanup_gallery.py')
    parser.add_argument('--timeout', type=int, default=0,
                        help='Per-directory timeout in seconds (0 = none)')
    parser.add_argument('names', nargs='*', metavar='DIR',
                        help='Explicit directory names to process (overrides --pattern)')
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        parser.error(f"unrecognized arguments before '--': {' '.join(unknown)} "
                     f"(flags for cleanup_gallery.py belong after --)")

    if args.dry_run:
        passthrough.append('--dry-run')
    if args.all:
        passthrough.append('--all')
    if args.verbose:
        passthrough.append('--verbose')

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

    log(f'cleanup_all: {len(targets)} director'
        f'{"y" if len(targets) == 1 else "ies"} under {base} | script={script}')

    for t in targets:
        if not t.is_dir():
            log(f'SKIP {t.name}: not a directory')

    if args.dry_run:
        # cleanup_gallery.py prints its own dry-run plan per directory below
        pass

    results = []
    for t in targets:
        if not t.is_dir():
            results.append((t.name, 'missing', 0.0))
            continue
        cmd = [sys.executable, str(script), str(t)] + passthrough
        log(f'RUN {t.name} ...')
        t0 = time.time()
        try:
            returncode = run_with_timeout(cmd, args.timeout)
            dt = time.time() - t0
            if returncode == 0:
                log(f'DONE {t.name} ({dt:.1f}s)')
                results.append((t.name, 'ok', dt))
            else:
                log(f'FAIL {t.name} (exit {returncode}, {dt:.1f}s)')
                results.append((t.name, f'exit {returncode}', dt))
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
