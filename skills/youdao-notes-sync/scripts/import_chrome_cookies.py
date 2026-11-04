#!/usr/bin/env python3
"""Import only the three authorized Youdao session cookies from Linux Chrome."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

REQUIRED = ('YNOTE_CSTK', 'YNOTE_LOGIN', 'YNOTE_SESS')
HOST = '.note.youdao.com'


def decrypt(encrypted, password, host, version):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
    if encrypted[:3] not in (b'v10', b'v11'):
        raise ValueError('Unsupported encryption format')
    key = hashlib.pbkdf2_hmac('sha1', password, b'saltysalt', 1, dklen=16)
    decoder = Cipher(algorithms.AES(key), modes.CBC(b' ' * 16)).decryptor()
    padded = decoder.update(encrypted[3:]) + decoder.finalize()
    unpadder = PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    if version >= 24:
        if plain[:32] != hashlib.sha256(host.encode()).digest():
            raise ValueError('Cookie domain verification failed')
        plain = plain[32:]
    return plain.decode('utf-8')


def import_cookies(database, output):
    database, output = Path(database).resolve(), Path(output)
    if output.is_symlink():
        raise ValueError('Invalid destination')
    output = output.resolve()
    if database == output:
        raise ValueError('Invalid destination')
    con = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    try:
        version = int(con.execute("SELECT value FROM meta WHERE key='version'").fetchone()[0])
        if not 1 <= version <= 24:
            raise ValueError('Unverified Chrome database version')
        rows = con.execute("SELECT name,value,encrypted_value,expires_utc FROM cookies "
                           "WHERE host_key=? AND path='/' AND name IN (?,?,?)",
                           (HOST, *REQUIRED)).fetchall()
    finally:
        con.close()
    if len(rows) != 3 or {r[0] for r in rows} != set(REQUIRED):
        raise ValueError('Expected exactly one matching cookie of each required name')
    now = int(time.time() * 1_000_000) + 11_644_473_600_000_000
    if any(expiry and expiry <= now for _, _, _, expiry in rows):
        raise ValueError('Stored Youdao cookies have expired')
    session, bus = None, None
    password = None
    try:
        if any(encrypted[:3] == b'v11' for _, _, encrypted, _ in rows):
            import dbus
            bus = dbus.SessionBus()
            service = dbus.Interface(bus.get_object('org.freedesktop.secrets', '/org/freedesktop/secrets'),
                                     'org.freedesktop.Secret.Service')
            unlocked, _ = service.SearchItems({'application': 'chrome'})
            if len(unlocked) != 1:
                raise ValueError('Need one unlocked Chrome storage key')
            _, session = service.OpenSession('plain', dbus.String('', variant_level=1))
            item = dbus.Interface(bus.get_object('org.freedesktop.secrets', unlocked[0]),
                                  'org.freedesktop.Secret.Item')
            password = bytes(item.GetSecret(session)[2])
        decoded = {}
        for name, value, encrypted, _ in rows:
            if encrypted:
                secret = b'peanuts' if encrypted[:3] == b'v10' else password
                if secret is None:
                    raise ValueError('Unsupported encryption key')
                value = decrypt(encrypted, secret, HOST, version)
            if not value or value in ('**', '***'):
                raise ValueError('Missing cookie value')
            decoded[name] = [name, value, HOST, '/']
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.youdao-cookies-', dir=output.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump({'cookies': [decoded[name] for name in REQUIRED]}, handle, indent=4)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    finally:
        if session is not None:
            import dbus
            dbus.Interface(bus.get_object('org.freedesktop.secrets', session),
                           'org.freedesktop.Secret.Session').Close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        import_cookies(args.database, args.output)
        print('Wrote three Youdao cookies with mode 0600; values were not displayed.')
    except Exception as exc:
        print('Cookie import stopped: ' + type(exc).__name__ + '. Check authorization, schema and keyring.', file=sys.stderr)
        raise SystemExit(2)
