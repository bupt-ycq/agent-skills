#!/usr/bin/env python3
"""Offline regression tests; synthetic files only, no accounts or network."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from import_chrome_cookies import HOST, REQUIRED, decrypt, import_cookies
from prepare_git import prepare
from sync_state import SyncError, active_paths, archive, audit, inventory, sha, snapshot, within


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


def listing(*rows):
    return {'folders': [{'path': '', 'id': 'root'}],
            'files': [{'id': identifier, 'folder': str(Path(path).parent),
                       'name': Path(path).name} for identifier, path in rows]}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def commit(repo):
    git(repo, 'add', '--all')
    git(repo, '-c', 'user.name=Offline Test', '-c', 'user.email=test@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-m', 'fixture', '--allow-empty')


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='youdao-skill-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'export'
        self.root.mkdir()
        self.before = self.base / 'before'
        self.repo = self.base / 'repo'

    def init_repo(self):
        self.repo.mkdir()
        git(self.repo, 'init', '-q')

    def record(self):
        snapshot(self.root, self.before)


class StateTests(Sandbox):
    def test_snapshot_copies_bytes_and_detects_unsafe_destination(self):
        source = put(self.root, '中文/笔记.md', 'line\r\n')
        self.record()
        self.assertEqual(sha(source), sha(self.before / 'files/中文/笔记.md'))
        self.assertEqual((self.before / 'manifest.json').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(SyncError):
            snapshot(self.root, self.root / 'nested')

    def test_paths_reject_traversal_and_external_symlink(self):
        with self.assertRaises(SyncError):
            within(self.root, '../outside')
        (self.root / 'linked').symlink_to(self.base)
        with self.assertRaises(SyncError):
            within(self.root, 'linked/outside')
        with self.assertRaises(SyncError):
            self.record()

    def test_audit_balanced_parentheses_and_encoded_spaces(self):
        put(self.root, 'n.md', '![图](images/img%20(1).png)\n[附件](attachments/a.pdf)\n')
        put(self.root, 'images/img (1).png', b'image')
        attachment = put(self.root, 'attachments/a.pdf', b'pdf')
        inv = listing(('n', 'n.md'))
        report = audit(self.root, inv)
        self.assertEqual(report['summary']['checked_links'], 2)
        self.assertEqual(report['summary']['broken_links'], 0)
        attachment.unlink()
        self.assertEqual(audit(self.root, inv)['summary']['broken_links'], 1)

    def test_normalized_filename_collision_is_rejected(self):
        put(self.root, 'same.md', 'one')
        inv = listing(('a', 'same.note'), ('b', 'same.md'))
        with self.assertRaises(SyncError):
            active_paths(self.root, inv)

    def test_archive_preserves_active_references_and_modified_old_notes(self):
        put(self.root, 'old.md', '![old](images/unused.png)')
        put(self.root, 'edited.md', '![edit](images/edited.png)')
        put(self.root, 'live.md', '![live](images/shared.png)')
        for name in ('unused.png', 'edited.png', 'shared.png'):
            put(self.root, 'images/' + name, name)
        previous = listing(('old', 'old.md'), ('edit', 'edited.md'), ('live', 'live.md'))
        current = listing(('live', 'live.md'))
        self.record()
        put(self.root, 'edited.md', 'local edit\n![edit](images/edited.png)')
        destination = self.base / 'archive'
        plan = archive(self.root, self.before, previous, current, destination)
        self.assertEqual(set(plan['archive_paths']), {'old.md', 'images/unused.png'})
        self.assertEqual(plan['retained_modified_paths'], ['edited.md'])
        self.assertTrue((self.root / 'old.md').exists())
        self.assertFalse(destination.exists())
        result = archive(self.root, self.before, previous, current, destination, True)
        self.assertTrue(result['summary']['applied'])
        self.assertTrue((destination / 'old.md').is_file())
        for path in ('live.md', 'edited.md', 'images/shared.png', 'images/edited.png'):
            self.assertTrue((self.root / path).is_file())

    def test_archive_collision_aborts_whole_batch(self):
        put(self.root, 'a.md', 'a')
        put(self.root, 'b.md', 'b')
        self.record()
        destination = self.base / 'archive'
        put(destination, 'b.md', 'prior archive')
        with self.assertRaises(SyncError):
            archive(self.root, self.before, listing(('a', 'a.md'), ('b', 'b.md')),
                    listing(), destination, True)
        self.assertTrue((self.root / 'a.md').exists())
        self.assertTrue((self.root / 'b.md').exists())


class GitTests(Sandbox):
    def baseline_repo(self, cloud, remote=None):
        self.init_repo()
        for name, value in cloud.items():
            put(self.root, name, value)
            put(self.repo, name, (remote or {}).get(name, value))
        put(self.repo, '.gitignore', 'cookies.json\n')
        commit(self.repo)
        self.record()

    def test_preserves_remote_edit_and_remote_only_ignore_file(self):
        self.baseline_repo({'note.md': 'original\r\n'}, {'note.md': 'edited remotely\n'})
        put(self.root, 'new.md', 'new cloud note')
        report = prepare(self.root, self.before, self.repo,
                         listing(('n', 'note.md'), ('new', 'new.md')))
        self.assertEqual((self.repo / 'note.md').read_text(), 'edited remotely\n')
        self.assertEqual((self.repo / '.gitignore').read_text(), 'cookies.json\n')
        self.assertEqual(report['summary']['preserved_remote_edits'], 1)
        self.assertIn(b'new.md', git(self.repo, 'diff', '--cached', '--name-only'))

    def test_rename_carries_remote_changes_and_archives_old_path(self):
        self.baseline_repo({'old.md': 'original'}, {'old.md': 'remote correction'})
        (self.root / 'old.md').rename(self.root / 'new.md')
        previous, current = listing(('n', 'old.md')), listing(('n', 'new.md'))
        report = prepare(self.root, self.before, self.repo, current, previous,
                         {'archive_paths': ['old.md']})
        self.assertEqual((self.repo / 'new.md').read_text(), 'remote correction')
        self.assertFalse((self.repo / 'old.md').exists())
        self.assertEqual(report['summary']['removed_archived_paths'], 1)

    def test_nonoverlapping_text_edits_merge(self):
        base = 'one\n2\n3\n4\n5\n6\nseven\n'
        remote = base.replace('one', 'remote one')
        self.baseline_repo({'n.md': base}, {'n.md': remote})
        put(self.root, 'n.md', base.replace('seven', 'cloud seven'))
        prepare(self.root, self.before, self.repo, listing(('n', 'n.md')))
        result = (self.repo / 'n.md').read_text()
        self.assertIn('remote one', result)
        self.assertIn('cloud seven', result)

    def test_conflict_does_not_change_worktree(self):
        self.baseline_repo({'n.md': 'base\n'}, {'n.md': 'remote\n'})
        put(self.root, 'added.md', 'new')
        put(self.root, 'n.md', 'cloud\n')
        with self.assertRaises(SyncError):
            prepare(self.root, self.before, self.repo,
                    listing(('n', 'n.md'), ('a', 'added.md')))
        self.assertEqual(git(self.repo, 'status', '--porcelain'), b'')
        self.assertFalse((self.repo / 'added.md').exists())

    def test_remote_modified_obsolete_file_is_not_removed(self):
        self.baseline_repo({'old.md': 'base'}, {'old.md': 'remote'})
        (self.root / 'old.md').unlink()
        with self.assertRaises(SyncError):
            prepare(self.root, self.before, self.repo, listing(), archived={'archive_paths': ['old.md']})
        self.assertEqual(git(self.repo, 'status', '--porcelain'), b'')
        self.assertEqual((self.repo / 'old.md').read_text(), 'remote')

    def test_first_publish_with_empty_baseline(self):
        self.init_repo()
        commit(self.repo)
        self.record()
        put(self.root, 'new.md', 'first note')
        result = prepare(self.root, self.before, self.repo, listing(('n', 'new.md')))
        self.assertEqual(result['summary']['repository_files'], 1)
        self.assertEqual((self.repo / 'new.md').read_text(), 'first note')

    def test_remote_deletion_requires_review(self):
        self.baseline_repo({'n.md': 'old'})
        (self.repo / 'n.md').unlink()
        commit(self.repo)
        with self.assertRaises(SyncError):
            prepare(self.root, self.before, self.repo, listing(('n', 'n.md')))
        self.assertEqual(git(self.repo, 'status', '--porcelain'), b'')


def encrypted_fixture(text, prefix=b'v10', password=b'peanuts', host=HOST):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
    key = hashlib.pbkdf2_hmac('sha1', password, b'saltysalt', 1, dklen=16)
    plain = hashlib.sha256(host.encode()).digest() + text.encode()
    padder = PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    encoder = Cipher(algorithms.AES(key), modes.CBC(b' ' * 16)).encryptor()
    return prefix + encoder.update(padded) + encoder.finalize()


class CookieTests(Sandbox):
    def db(self, encrypted=False, wrong_domain=False):
        path = self.base / 'Cookies'
        with sqlite3.connect(path) as con:
            con.execute('CREATE TABLE meta (key TEXT, value TEXT)')
            con.execute("INSERT INTO meta VALUES ('version', '24')")
            con.execute('CREATE TABLE cookies (host_key TEXT, path TEXT, name TEXT, value TEXT, encrypted_value BLOB, expires_utc INTEGER)')
            for name in (*REQUIRED, 'UNRELATED'):
                value = 'offline-fixture-' + name
                cipher = encrypted_fixture(value, host='wrong.invalid' if wrong_domain else HOST) if encrypted else b''
                con.execute('INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?)',
                            (HOST, '/', name, '' if encrypted else value, cipher, 0))
        return path

    def test_import_plain_and_encrypted_only_three_in_correct_order(self):
        for use_encryption in (False, True):
            database = self.db(encrypted=use_encryption)
            output = self.base / 'output.json'
            import_cookies(database, output)
            rows = json.loads(output.read_text())['cookies']
            self.assertEqual(tuple(row[0] for row in rows), REQUIRED)
            self.assertEqual([row[1] for row in rows], ['offline-fixture-' + n for n in REQUIRED])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            database.unlink()

    def test_wrong_domain_does_not_overwrite_destination(self):
        database = self.db(encrypted=True, wrong_domain=True)
        output = put(self.base, 'output.json', 'original')
        with self.assertRaises(ValueError):
            import_cookies(database, output)
        self.assertEqual(output.read_text(), 'original')

    def test_v11_decrypt_with_synthetic_key(self):
        password = b'offline-only-test-key'
        encrypted = encrypted_fixture('fixture', prefix=b'v11', password=password)
        self.assertEqual(decrypt(encrypted, password, HOST, 24), 'fixture')

    def test_output_symlink_rejected(self):
        database = self.db()
        target = put(self.base, 'target.json', 'untouched')
        output = self.base / 'link.json'
        output.symlink_to(target)
        with self.assertRaises(ValueError):
            import_cookies(database, output)
        self.assertEqual(target.read_text(), 'untouched')

    def test_expired_session_is_not_written(self):
        database = self.db()
        with sqlite3.connect(database) as con:
            con.execute('UPDATE cookies SET expires_utc=1')
        output = self.base / 'output.json'
        with self.assertRaises(ValueError):
            import_cookies(database, output)
        self.assertFalse(output.exists())


class InventoryTests(Sandbox):
    def collect(self, configured='', truncated=False, unauthorized=False):
        project = self.base / 'project'
        project.mkdir()
        put(project, 'config.json', json.dumps({'ydnote_dir': configured}))
        output = self.base / 'current.json'
        calls = []
        response = types.SimpleNamespace(status_code=401 if unauthorized else 200)
        session = types.SimpleNamespace(request=lambda *a, **k: response,
                                        close=lambda: calls.append('closed'))
        entries = {'root': [{'fileEntry': {'id': 'd', 'name': 'folder', 'dir': True}}],
                   'd': [{'fileEntry': {'id': 'n', 'name': 'note.md', 'dir': False,
                                       'modifyTimeForSort': 10}}]}

        class FakeAPI:
            def __init__(self):
                self.session = session

            def login_by_cookies(self):
                return None

            def get_root_dir_info_id(self):
                self.session.request('POST', 'https://offline.invalid')
                return {'fileEntry': {'id': 'root'}}

            def get_dir_info_by_id(self, identifier):
                return {'entries': entries[identifier],
                        'count': 100 if truncated else len(entries[identifier])}

        module = types.ModuleType('core.api')
        module.YoudaoNoteApi = FakeAPI
        cwd = Path.cwd()
        original_path = list(sys.path)
        try:
            with patch.dict(sys.modules, {'core': types.ModuleType('core'), 'core.api': module}):
                result = inventory(project, output)
            return result, json.loads(output.read_text())
        finally:
            sys.path[:] = original_path
            self.assertEqual(Path.cwd(), cwd)
            self.assertIn('closed', calls)
            if unauthorized or truncated:
                self.assertFalse(output.exists())

    def test_recursive_inventory(self):
        summary, data = self.collect()
        self.assertEqual(summary['cloud_files'], 1)
        self.assertEqual(data['files'][0]['folder'], 'folder')

    def test_configured_subfolder_matches_export_layout(self):
        summary, data = self.collect(configured='folder')
        self.assertEqual(summary['cloud_folders'], 1)
        self.assertEqual(data['files'][0]['folder'], '')

    def test_truncated_inventory_is_not_saved(self):
        with self.assertRaises(SyncError):
            self.collect(truncated=True)

    def test_unauthorized_inventory_is_not_saved(self):
        with self.assertRaises(SyncError):
            self.collect(unauthorized=True)


if __name__ == '__main__':
    unittest.main()
