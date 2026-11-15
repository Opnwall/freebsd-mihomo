#!/usr/bin/env python3
"""Apply a TUN patch strictly, or merge it against its recorded source baseline."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def paths_in_patch(patch):
    paths = []
    for line in patch.read_text().splitlines():
        if line.startswith(('--- a/', '+++ b/')):
            name = line[6:].split('\t')[0]
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe patch path: ' + name)
            if name not in paths:
                paths.append(name)
    if not paths:
        raise ValueError('Empty patch')
    return paths


def read_optional(path):
    return path.read_bytes() if path.is_file() else None


def write_optional(path, data):
    if data is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def run_patch(source, patch, dry=False):
    command = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)]
    if dry:
        command.append('--dry-run')
    return subprocess.run(command, cwd=source, capture_output=True, text=True)


def merge_bytes(current, base, desired, name):
    if current == base or current == desired:
        return desired
    if desired == base:
        return current
    if current is None or base is None or desired is None:
        raise ValueError('Upstream added/deleted a conflicting file: ' + name)
    with tempfile.TemporaryDirectory() as tmp:
        files = [Path(tmp) / n for n in ('current', 'base', 'desired')]
        for path, data in zip(files, (current, base, desired)):
            path.write_bytes(data)
        result = subprocess.run(['git', 'merge-file', '-p', '--diff3', *map(str, files)], capture_output=True)
        if result.returncode != 0:
            raise ValueError('Three-way merge conflict: ' + name)
        return result.stdout


def save_baseline(source, patch, component, version, destination, originals=None):
    names = paths_in_patch(patch)
    originals = originals or {n: read_optional(source / n) for n in names}
    base_dir = destination / 'bases' / component
    base_dir.mkdir(parents=True, exist_ok=True)
    after = {n: read_optional(source / n) for n in names}
    chunks = []
    for name in names:
        before, changed = originals[name], after[name]
        if before == changed:
            continue
        chunks.append('diff --git a/' + name + ' b/' + name + '\n')
        chunks.extend(difflib.unified_diff(
            (before or b'').decode().splitlines(True),
            (changed or b'').decode().splitlines(True),
            fromfile='a/' + name if before is not None else '/dev/null',
            tofile='b/' + name if changed is not None else '/dev/null'))
    patch_data = ''.join(chunks).encode()
    if not patch_data:
        raise ValueError('Patch became empty; native upstream support requires manual review')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / patch.name).write_bytes(patch_data)
    manifest = {'version': version, 'patch': patch.name, 'patch_sha256': digest(patch_data), 'files': {}}
    for name in paths_in_patch(destination / patch.name):
        data = originals[name]
        manifest['files'][name] = digest(data) if data is not None else None
        if data is not None:
            write_optional(base_dir / 'files' / name, data)
    (base_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def apply(source, patch, baseline, component, version, output):
    names = paths_in_patch(patch)
    originals = {n: read_optional(source / n) for n in names}
    check = run_patch(source, patch, dry=True)
    migrated = check.returncode != 0
    if not migrated:
        result = run_patch(source, patch)
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        print(result.stdout, end='')
    else:
        manifest = json.loads((baseline / 'manifest.json').read_text())
        if manifest['patch_sha256'] != digest(patch.read_bytes()):
            raise ValueError('Patch and baseline do not match; refresh baseline manually')
        if set(names) != set(manifest['files']):
            raise ValueError('Patch paths differ from the baseline')
        print('Strict patch failed; attempting a three-way source merge')
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp)
            bases = {}
            for name, expected in manifest['files'].items():
                data = read_optional(baseline / 'files' / name) if expected is not None else None
                if expected is not None and (data is None or digest(data) != expected):
                    raise ValueError('Corrupt baseline: ' + name)
                bases[name] = data
                write_optional(old / name, data)
            result = run_patch(old, patch)
            if result.returncode:
                raise ValueError('Cannot reconstruct baseline patch: ' + result.stdout + result.stderr)
            merged = {name: merge_bytes(originals[name], bases[name], read_optional(old / name), name) for name in names}
        for name, data in merged.items():
            write_optional(source / name, data)
    save_baseline(source, patch, component, version, output / 'patches', originals)
    if migrated:
        (output / 'migrated').write_text('Three-way migration; must compile and pass FreeBSD tests before use.\n')
        print('Three-way migration succeeded; awaiting compilation and FreeBSD tests')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--patch', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--component', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    apply(args.source.resolve(), args.patch.resolve(), args.baseline.resolve(), args.component, args.version, args.output.resolve())


if __name__ == '__main__':
    main()
