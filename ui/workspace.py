"""Safe, local SQLite workspace selection and backup for ClassFlow."""
import os
import sqlite3
from pathlib import Path
from PyQt5.QtCore import QSettings
import db

SETTINGS_ORG="ClassFlow"
SETTINGS_APP="ClassFlow"
WORKSPACE_KEY="active_workspace"

def active_workspace_path():
    """An explicit environment override always wins over the saved selection."""
    override=os.environ.get("CLASSFLOW_DB")
    if override:
        return Path(override).expanduser().resolve()
    selected=QSettings(SETTINGS_ORG,SETTINGS_APP).value(WORKSPACE_KEY,"")
    if selected:
        result=Path(str(selected)).expanduser().resolve()
        if not result.is_file():
            raise FileNotFoundError(
                f"The selected ClassFlow dataset was moved or deleted:\n{result}\n"
                "Restore the file, or clear the saved 'active_workspace' preference."
            )
        return result
    return db.default_path()

def current_database_path():
    row=db.conn.execute("PRAGMA database_list").fetchone()
    return Path(row[2]).resolve() if row and row[2] else None

def save_copy(destination):
    """Use SQLite backup API for consistent copies even while DB is open."""
    target=Path(destination).expanduser().resolve()
    active=current_database_path()
    if active and target==active:
        raise ValueError("Choose a different filename to keep the current database safe.")
    if target.exists():
        raise FileExistsError("That file already exists. Choose a new backup filename.")
    if not target.parent.is_dir():
        raise FileNotFoundError("The destination folder does not exist.")
    connection=sqlite3.connect(str(target))
    try:
        db.conn.backup(connection)
        connection.commit()
    except Exception:
        connection.close()
        try: target.unlink(missing_ok=True)
        except OSError: pass
        raise
    finally:
        try: connection.close()
        except Exception: pass
    return target

def create_blank_workspace(destination, username):
    """New academic records, with current admin credentials retained.

    Accounts are copied only for the signed-in administrator. All academic
    tables, schedules and blocked-time records start empty.
    """
    target=Path(destination).expanduser().resolve()
    if target.exists():
        raise FileExistsError("A dataset already exists at this path. Choose a new filename.")
    if not target.parent.is_dir():
        raise FileNotFoundError("Choose an existing destination folder.")
    account=db.conn.execute(
        "SELECT username,salt,digest FROM users WHERE username=?",(username,)
    ).fetchone()
    if account is None:
        raise ValueError("Your signed-in account could not be found. Sign in again.")
    fresh=sqlite3.connect(str(target))
    try:
        fresh.executescript(db.SCHEMA)
        fresh.execute(
            "CREATE TABLE IF NOT EXISTS users("
            "username TEXT PRIMARY KEY,salt TEXT NOT NULL,digest TEXT NOT NULL)"
        )
        fresh.execute(
            "INSERT INTO users(username,salt,digest) VALUES(?,?,?)",tuple(account)
        )
        fresh.commit()
    except Exception:
        fresh.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        try: fresh.close()
        except Exception: pass
    select_workspace(target)
    return target

def validate_workspace(source):
    """Reject unrelated or corrupt SQLite files before selecting them."""
    path=Path(source).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("Selected dataset does not exist.")
    with path.open("rb") as handle:
        if handle.read(16)!=b"SQLite format 3\x00":
            raise ValueError("This is not a SQLite database file.")
    try:
        connection=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
        try:
            ok=connection.execute("PRAGMA integrity_check").fetchone()[0]
            if ok!="ok":
                raise ValueError("The selected database did not pass its integrity check.")
            tables={row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            required={"users","programs","subjects","sections","faculty",
                      "classrooms","terms","schedules"}
            if not required.issubset(tables):
                raise ValueError("This is not a compatible ClassFlow dataset.")
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError("This database cannot be opened safely as a ClassFlow dataset.") from exc
    return path

def select_workspace(path):
    QSettings(SETTINGS_ORG,SETTINGS_APP).setValue(
        WORKSPACE_KEY,str(Path(path).expanduser().resolve())
    )
