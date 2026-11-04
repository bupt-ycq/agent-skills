#!/usr/bin/env python3
"""Snapshot, inventory, audit and reversibly archive Youdao exports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import unquote


class SyncError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise SyncError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.chmod(0o600)


def within(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    require(not rel.is_absolute() and '..' not in rel.parts and '.git' not in rel.parts,
            'Unsafe relative export path')
    candidate = root / rel
    require(candidate.resolve().is_relative_to(root), 'Path escapes export directory')
    return candidate


def files(root):
    root = Path(root)
    for p in root.rglob('*'):
        if '.git' in p.relative_to(root).parts:
            continue
        require(not p.is_symlink(), 'Symlink in export; review before copying')
        if p.is_file():
            yield p


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def exported_path(root, item):
    # Mirrors the inspected upstream _optimize_file_name implementation.
    name = item['name'].replace('\n', '').strip().replace('<', '_')
    name = re.sub(r'[\\/":|*?#>]', '', name)
    require(bool(name), 'Empty normalized filename')
    path = within(root, str(Path(item['folder']) / name))
    if path.suffix in ('.note', '.clip', '') and path.with_suffix('.md').is_file():
        path = path.with_suffix('.md')
    return path


def active_paths(root, inventory):
    result = {row['id']: exported_path(root, row) for row in inventory['files']}
    require(len(result) == len(inventory['files']), 'Duplicate cloud file ID')
    require(len(set(result.values())) == len(result), 'Colliding normalized export paths')
    return result


def markdown_links(text):
    offset = 0
    while True:
        start = text.find('](', offset)
        if start < 0:
            return
        index, depth = start + 2, 1
        while index < len(text) and depth:
            if text[index] == '\\':
                index += 2
                continue
            if text[index] == '(':
                depth += 1
            elif text[index] == ')':
                depth -= 1
            if depth:
                index += 1
        if depth:
            return
        yield text[start + 2:index].strip()
        offset = index + 1


def snapshot(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(root.is_dir(), 'Source directory does not exist')
    require(not output.exists() and not output.is_relative_to(root),
            'Snapshot must be a new directory outside the export')
    entries = list(files(root))
    output.mkdir(parents=True, mode=0o700)
    manifest = {}
    for p in entries:
        relative = str(p.relative_to(root))
        target = within(output / 'files', relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        digest = sha(target)
        require(digest == sha(p), 'Source changed during snapshot; take a fresh snapshot')
        manifest[relative] = {'sha256': digest, 'size': p.stat().st_size,
                              'mtime_ns': p.stat().st_mtime_ns}
    write_json(output / 'manifest.json', manifest)
    return {'snapshot_files': len(manifest)}


def inventory(project, output):
    project = Path(project).resolve()
    original_cwd = Path.cwd()
    sys.path.insert(0, str(project))
    api = None
    try:
        os.chdir(project)
        from core.api import YoudaoNoteApi
        api = YoudaoNoteApi()
        require(not api.login_by_cookies(), 'Cannot load Youdao login configuration')
        request = api.session.request

        def checked_request(method, url, **kwargs):
            kwargs.setdefault('timeout', (10, 45))
            response = request(method, url, **kwargs)
            require(response.status_code == 200, 'Youdao HTTP request failed')
            return response

        api.session.request = checked_request
        root = api.get_root_dir_info_id().get('fileEntry', {}).get('id')
        require(bool(root), 'Youdao login did not return a root directory')
        configured_folder = read_json(project / 'config.json').get('ydnote_dir', '')
        if configured_folder:
            root_data = api.get_dir_info_by_id(root)
            entries = root_data.get('entries')
            require(isinstance(entries, list), 'Invalid root directory response')
            for key in ('count', 'total'):
                value = root_data.get(key)
                require(not isinstance(value, int) or value <= len(entries),
                        'Root directory response may be truncated; resolve pagination')
            selected = [e['fileEntry']['id'] for e in entries
                        if e['fileEntry']['dir'] and e['fileEntry']['name'] == configured_folder]
            require(len(selected) == 1, 'Configured Youdao directory is missing or ambiguous')
            root = selected[0]
        queue, seen, folders, notes = [(root, '')], set(), [], []
        while queue:
            folder_id, parent = queue.pop()
            require(folder_id not in seen, 'Duplicate or cyclic directory ID')
            seen.add(folder_id)
            data = api.get_dir_info_by_id(folder_id)
            entries = data.get('entries')
            require(isinstance(entries, list), 'Invalid directory response')
            for key in ('count', 'total'):
                value = data.get(key)
                require(not isinstance(value, int) or value <= len(entries),
                        'Directory response may be truncated; resolve pagination')
            folders.append({'path': parent, 'id': folder_id, 'returned': len(entries),
                            'count': data.get('count'), 'total': data.get('total')})
            for entry in entries:
                row = entry['fileEntry']
                if row['dir']:
                    relative = str(Path(parent) / row['name'])
                    within(project, relative)
                    queue.append((row['id'], relative))
                else:
                    notes.append({'folder': parent, 'id': row['id'], 'name': row['name'],
                                  'modified': row.get('modifyTimeForSort'),
                                  'created': row.get('createTimeForSort')})
        write_json(output, {'folders': folders, 'files': notes})
        return {'cloud_folders': len(folders), 'cloud_files': len(notes)}
    finally:
        if api:
            api.session.close()
        os.chdir(original_cwd)


def audit(root, inv):
    root = Path(root).resolve()
    current = active_paths(root, inv)
    missing = [str(p.relative_to(root)) for p in current.values() if not p.is_file()]
    unconverted = [str(p.relative_to(root)) for p in current.values()
                   if p.is_file() and p.suffix in ('.note', '.clip')]
    empty = [str(p.relative_to(root)) for p in current.values()
             if p.is_file() and p.stat().st_size == 0]
    broken, checked, remote_images = [], 0, 0
    local = list(files(root))
    for p in local:
        if p.suffix.lower() != '.md':
            continue
        text = p.read_text(errors='replace')
        remote_images += len(re.findall(r'!\[.*?\]\(https?://[^\s)]*note\.youdao\.com[^\s)]*\)', text))
        for link in markdown_links(text):
            if link.startswith(('images/', 'attachments/')):
                checked += 1
                if not (p.parent / unquote(link)).is_file():
                    broken.append({'note': str(p.relative_to(root)), 'link': link})
    summary = {'cloud_files': len(current), 'local_files': len(local),
               'bytes': sum(p.stat().st_size for p in local), 'missing': len(missing),
               'unconverted': len(unconverted), 'empty': len(empty),
               'checked_links': checked, 'broken_links': len(broken),
               'remote_images': remote_images}
    return {'summary': summary, 'active_paths': {k: str(v.relative_to(root)) for k, v in current.items()},
            'missing': missing, 'unconverted': unconverted, 'empty': empty, 'broken_links': broken}


def archive(root, before, previous, current, destination, apply=False):
    root, before = Path(root).resolve(), Path(before).resolve()
    destination = Path(destination).resolve()
    require(not destination.is_relative_to(root), 'Archive must be outside the export')
    manifest = read_json(before / 'manifest.json')
    active = active_paths(root, current)
    require(all(p.is_file() for p in active.values()), 'Current export is incomplete')
    stale = {within(root, str(exported_path(before / 'files', row).relative_to(before / 'files')))
             for row in previous['files']} - set(active.values())
    stale = {p for p in stale if p.is_file()}
    parents = {p.parent for p in stale}
    movable_stale = {p for p in stale
                     if sha(p) == manifest.get(str(p.relative_to(root)), {}).get('sha256')}
    texts = [(p.parent, unquote(p.read_text(errors='replace')))
             for p in files(root) if p.suffix == '.md' and p not in movable_stale]
    candidates = set(stale)
    for relative in manifest:
        path = within(root, relative)
        if path in active.values() or not path.is_file():
            continue
        owner = next((p.parent for p in path.parents if p.name in ('images', 'attachments')), None)
        if owner in parents and not any(os.path.relpath(path, parent).replace(os.sep, '/') in text
                                        for parent, text in texts):
            candidates.add(path)
    paths, retained = [], []
    for p in sorted(candidates):
        relative = str(p.relative_to(root))
        if sha(p) == manifest.get(relative, {}).get('sha256'):
            paths.append(relative)
        else:
            retained.append(relative)
    if apply:
        # Check the entire batch before moving any file.
        for relative in paths:
            require(not within(destination, relative).exists(), 'Archive target already exists')
            require(sha(within(root, relative)) == manifest[relative]['sha256'], 'File changed after plan')
        for relative in paths:
            source, target = within(root, relative), within(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        cloud_folders = {within(root, f['path']) for f in current['folders']}
        for p in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if p.is_dir() and p not in cloud_folders:
                try:
                    p.rmdir()
                except OSError:
                    pass
    return {'summary': {'archive_files': len(paths), 'retained_modified': len(retained), 'applied': apply},
            'archive_paths': paths, 'retained_modified_paths': retained,
            'active_paths': {k: str(v.relative_to(root)) for k, v in active.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    snap = commands.add_parser('snapshot')
    snap.add_argument('--root', required=True)
    snap.add_argument('--output', required=True)
    inv = commands.add_parser('inventory')
    inv.add_argument('--project', required=True)
    inv.add_argument('--output', required=True)
    check = commands.add_parser('audit')
    check.add_argument('--root', required=True)
    check.add_argument('--inventory', required=True)
    check.add_argument('--report', required=True)
    arc = commands.add_parser('archive')
    for name in ('root', 'before', 'previous', 'current', 'destination', 'report'):
        arc.add_argument('--' + name, required=True)
    arc.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == 'snapshot':
        result = snapshot(args.root, args.output)
    elif args.command == 'inventory':
        result = inventory(args.project, str(Path(args.output).resolve()))
    elif args.command == 'audit':
        result = audit(args.root, read_json(args.inventory))
        write_json(args.report, result)
    else:
        result = archive(args.root, args.before, read_json(args.previous), read_json(args.current),
                         args.destination, args.apply)
        write_json(args.report, result)
    print(json.dumps(result.get('summary', result), ensure_ascii=False))
    if args.command == 'audit' and any(result['summary'][key] for key in ('missing', 'unconverted', 'broken_links', 'remote_images')):
        return 2
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        # Network exceptions may embed authenticated URLs; do not print their values.
        print('Operation failed: ' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
