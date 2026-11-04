#!/usr/bin/env python3
"""Stage exports in a clean, freshly fetched worktree; never commit or push."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from sync_state import (SyncError, active_paths, exported_path, files, read_json,
                        require, sha, within, write_json)


def normalized(data):
    if b'\0' in data:
        return data
    try:
        data.decode('utf-8')
    except UnicodeError:
        return data
    return data.replace(b'\r\n', b'\n')


def merge_bytes(remote, baseline, cloud):
    if normalized(remote) == normalized(baseline):
        return cloud
    if normalized(cloud) in (normalized(baseline), normalized(remote)):
        return remote
    for content in (remote, baseline, cloud):
        require(b'\0' not in content, 'Both sides changed a binary file; review required')
        try:
            content.decode('utf-8')
        except UnicodeError:
            raise SyncError('Both sides changed a non-UTF-8 file; review required')
    with tempfile.TemporaryDirectory(prefix='youdao-merge-') as temporary:
        paths = []
        for name, content in [('remote', remote), ('base', baseline), ('cloud', cloud)]:
            path = Path(temporary) / name
            path.write_bytes(normalized(content))
            path.chmod(0o600)
            paths.append(str(path))
        result = subprocess.run(['git', 'merge-file', '-p', *paths], capture_output=True)
        require(result.returncode == 0, 'Cloud/remote merge conflict; resolve before pushing')
        return result.stdout


def prepare(root, before, repo, current, previous=None, archived=None):
    root, before, repo = Path(root).resolve(), Path(before).resolve(), Path(repo).resolve()
    require(not repo.is_relative_to(root) and not root.is_relative_to(repo),
            'Export and Git worktree must be separate directories')
    top = Path(subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], text=True).strip())
    require(top.resolve() == repo, 'Repository argument must be its root')
    require(not subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain']),
            'Use a clean worktree from the latest remote commit')
    list(files(repo))  # Reject symlinks before any writes.
    baseline_root = before / 'files'
    require((before / 'manifest.json').is_file(), 'Missing raw export baseline')
    baseline_manifest = read_json(before / 'manifest.json')
    current_paths = active_paths(root, current)
    require(all(p.is_file() for p in current_paths.values()), 'Cloud export is incomplete')
    old_for_new = {}
    if previous:
        old_ids = {item['id']: exported_path(baseline_root, item) for item in previous['files']}
        for identifier, path in current_paths.items():
            if identifier in old_ids:
                old_for_new[str(path.relative_to(root))] = str(old_ids[identifier].relative_to(baseline_root))

    planned, preserved, moved_preserved = {}, [], set()
    source_hashes = {}
    for source in files(root):
        relative = str(source.relative_to(root))
        old_relative = old_for_new.get(relative, relative)
        baseline = within(baseline_root, old_relative)
        target = within(repo, relative)
        remote = target if target.is_file() else within(repo, old_relative)
        source_hashes[relative] = sha(source)
        content = None  # None means copy the unchanged source bytes at apply time.
        if baseline.is_file():
            require(sha(baseline) == baseline_manifest[old_relative]['sha256'], 'Baseline snapshot was modified')
            require(remote.is_file(), 'An exported file was deleted in GitHub; review before restoring it')
            base_bytes, remote_bytes, cloud_bytes = baseline.read_bytes(), remote.read_bytes(), source.read_bytes()
            if normalized(remote_bytes) != normalized(base_bytes):
                content = merge_bytes(remote_bytes, base_bytes, cloud_bytes)
                preserved.append(relative)
                if relative != old_relative:
                    moved_preserved.add(old_relative)
        elif remote.is_file():
            require(remote.read_bytes() == source.read_bytes(), 'New export collides with a remote-only file')
        planned[relative] = (source, content)

    deletions = []
    for relative in (archived or {}).get('archive_paths', []):
        require(relative not in planned and not within(root, relative).exists(), 'Archive plan overlaps active exports')
        target = within(repo, relative)
        if target.is_file():
            require(relative in moved_preserved or sha(target) == baseline_manifest.get(relative, {}).get('sha256'),
                    'Remote edits to an obsolete file need review before removal')
            deletions.append(target)

    # Merge conflicts and removal conflicts were checked before mutating the worktree.
    for relative, (source, content) in planned.items():
        require(sha(source) == source_hashes[relative], 'Local export changed during preparation')
        target = within(repo, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            shutil.copy2(source, target)
        else:
            target.write_bytes(content)
    for path in deletions:
        path.unlink()
    subprocess.run(['git', '-C', str(repo), 'add', '--all'], check=True, capture_output=True)
    tracked = {p.decode() for p in subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).split(b'\0') if p}
    ignored = sorted(set(planned) - tracked)
    require(not ignored, 'Some export files are ignored; review the ignore rules instead of forcing credentials into Git')
    return {'summary': {'export_files': len(planned), 'repository_files': len(tracked),
                        'preserved_remote_edits': len(preserved), 'removed_archived_paths': len(deletions)},
            'preserved_remote_paths': preserved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'before', 'repo', 'current', 'report'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--previous')
    parser.add_argument('--archive-report')
    args = parser.parse_args()
    os.umask(0o077)
    result = prepare(args.root, args.before, args.repo, read_json(args.current),
                     read_json(args.previous) if args.previous else None,
                     read_json(args.archive_report) if args.archive_report else None)
    write_json(args.report, result)
    print(result['summary'])


if __name__ == '__main__':
    try:
        main()
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
