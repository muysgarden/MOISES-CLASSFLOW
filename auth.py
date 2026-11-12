"""Local accounts: salted PBKDF2 hashes, never plaintext passwords."""
import hashlib
import hmac
import secrets
import sqlite3
import db


def init():
    db.conn.execute('CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT NOT NULL, digest TEXT NOT NULL)')
    db.conn.commit()


def has_users():
    return db.row('SELECT 1 FROM users LIMIT 1') is not None


def create(username, password):
    username = username.strip()
    if not username or len(password) < 8:
        raise ValueError('Enter a username and a password of at least 8 characters.')
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    with db.conn:
        db.conn.execute('INSERT INTO users VALUES(?,?,?)', (username, salt, digest))


def verify(username, password):
    row = db.row('SELECT * FROM users WHERE username=?', (username.strip(),))
    if row is None:
        # Keep failed-user and failed-password work comparable.
        hashlib.pbkdf2_hmac('sha256', password.encode(), bytes(16), 600000)
        return False
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(row['salt']), 600000).hex()
    return hmac.compare_digest(digest, row['digest'])


def change_username(username, new_username, current_password):
    """Rename the authenticated local account without changing its password."""
    new_username = new_username.strip()
    if not new_username:
        raise ValueError('Enter a new username.')
    if not verify(username, current_password):
        raise ValueError('Current password is incorrect.')
    if new_username == username:
        return new_username
    try:
        with db.conn:
            db.conn.execute(
                'UPDATE users SET username=? WHERE username=?',
                (new_username, username.strip()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError('That username is already in use.') from exc
    return new_username


def change_password(username, current_password, new_password):
    """Replace password hash and salt after verifying the existing password."""
    if len(new_password) < 8:
        raise ValueError('New password must contain at least 8 characters.')
    if not verify(username, current_password):
        raise ValueError('Current password is incorrect.')
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256', new_password.encode(), bytes.fromhex(salt), 600000
    ).hex()
    with db.conn:
        db.conn.execute(
            'UPDATE users SET salt=?, digest=? WHERE username=?',
            (salt, digest, username.strip()),
        )
