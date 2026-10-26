"""Local accounts: salted PBKDF2 hashes, never plaintext passwords."""
import hashlib
import hmac
import secrets
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
