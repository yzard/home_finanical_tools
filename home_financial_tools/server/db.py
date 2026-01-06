import os
import sqlite3
from typing import Any, Dict, List, Optional


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        # Ensure parent directory exists before initializing database
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Users table for authentication
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY
                  , password_hash BLOB NOT NULL
                  , created_at TEXT NOT NULL DEFAULT (datetime('now'))
                  , updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            # Corporation table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS corporation (
                    id INTEGER PRIMARY KEY
                  , company_name TEXT
                  , recipient TEXT
                  , street TEXT
                  , city TEXT
                  , state TEXT
                  , zip_code TEXT
                  , phone_number TEXT
                )
            """
            )
            # Bill To table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bill_to (
                    id INTEGER PRIMARY KEY
                  , recipient TEXT
                  , company_name TEXT
                  , street TEXT
                  , city TEXT
                  , state TEXT
                  , zip_code TEXT
                )
            """
            )
            # Ship To table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ship_to (
                    id INTEGER PRIMARY KEY
                  , recipient TEXT
                  , company_name TEXT
                  , street TEXT
                  , city TEXT
                  , state TEXT
                  , zip_code TEXT
                )
            """
            )
            # Time Entries table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS time_entries (
                    date DATE PRIMARY KEY
                  , hours REAL
                  , hourly_rate REAL
                  , hours_inputted INTEGER DEFAULT 0
                  , rate_inputted INTEGER DEFAULT 0
                )
            """
            )
            # Settings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY
                  , value TEXT
                )
            """
            )
            # Sessions table for persistent authentication
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY
                  , username TEXT NOT NULL
                  , created_at TEXT NOT NULL
                  , expires_at TEXT NOT NULL
                )
            """
            )
            # Email settings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS email_settings (
                    id INTEGER PRIMARY KEY
                  , gmail_account TEXT
                  , from_email TEXT
                  , to_email TEXT
                  , cc_email TEXT
                  , gmail_app_password TEXT
                )
            """
            )
            # Migration: add gmail_account column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE email_settings ADD COLUMN gmail_account TEXT")
            except sqlite3.OperationalError:
                pass
            # Migration: add email_subject column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE email_settings ADD COLUMN email_subject TEXT")
            except sqlite3.OperationalError:
                pass
            # Migration: add columns if they don't exist
            try:
                cursor.execute("ALTER TABLE time_entries ADD COLUMN hours_inputted INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE time_entries ADD COLUMN rate_inputted INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def get_corporation(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT id
                     , company_name
                     , recipient
                     , street
                     , city
                     , state
                     , zip_code
                     , phone_number
                  FROM corporation
                 WHERE id = 1
            """
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "company_name": row[1],
                    "recipient": row[2],
                    "street": row[3],
                    "city": row[4],
                    "state": row[5],
                    "zip_code": row[6],
                    "phone_number": row[7],
                }
            return None

    def save_corporation(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO corporation (
                    id
                  , company_name
                  , recipient
                  , street
                  , city
                  , state
                  , zip_code
                  , phone_number
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql,
                (
                    data["company_name"],
                    data["recipient"],
                    data["street"],
                    data["city"],
                    data["state"],
                    data["zip_code"],
                    data.get("phone_number"),
                ),
            )
            conn.commit()

    def get_bill_to(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT id
                     , recipient
                     , company_name
                     , street
                     , city
                     , state
                     , zip_code
                  FROM bill_to
                 WHERE id = 1
            """
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "recipient": row[1],
                    "company_name": row[2],
                    "street": row[3],
                    "city": row[4],
                    "state": row[5],
                    "zip_code": row[6],
                }
            return None

    def save_bill_to(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO bill_to (
                    id
                  , recipient
                  , company_name
                  , street
                  , city
                  , state
                  , zip_code
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql,
                (
                    data["recipient"],
                    data["company_name"],
                    data["street"],
                    data["city"],
                    data["state"],
                    data["zip_code"],
                ),
            )
            conn.commit()

    def get_ship_to(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT id
                     , recipient
                     , company_name
                     , street
                     , city
                     , state
                     , zip_code
                  FROM ship_to
                 WHERE id = 1
            """
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "recipient": row[1],
                    "company_name": row[2],
                    "street": row[3],
                    "city": row[4],
                    "state": row[5],
                    "zip_code": row[6],
                }
            return None

    def save_ship_to(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO ship_to (
                    id
                  , recipient
                  , company_name
                  , street
                  , city
                  , state
                  , zip_code
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql,
                (
                    data["recipient"],
                    data["company_name"],
                    data["street"],
                    data["city"],
                    data["state"],
                    data["zip_code"],
                ),
            )
            conn.commit()

    def get_time_entries(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT date
                     , hours
                     , hourly_rate
                     , hours_inputted
                     , rate_inputted
                   FROM time_entries
                  WHERE date BETWEEN ? AND ?
            """
            cursor.execute(sql, (start_date, end_date))
            rows = cursor.fetchall()
            return [
                {
                    "date": row[0],
                    "hours": row[1],
                    "hourly_rate": row[2],
                    "hours_inputted": bool(row[3]),
                    "rate_inputted": bool(row[4]),
                }
                for row in rows
            ]

    def save_time_entry(
        self, date: str, hours: float, hourly_rate: float, hours_inputted: bool = False, rate_inputted: bool = False
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO time_entries (
                    date
                  , hours
                  , hourly_rate
                  , hours_inputted
                  , rate_inputted
                ) VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(sql, (date, hours, hourly_rate, int(hours_inputted), int(rate_inputted)))
            conn.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT value
                  FROM settings
                 WHERE key = ?
            """
            cursor.execute(sql, (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def save_setting(self, key: str, value: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO settings (
                    key
                  , value
                ) VALUES (?, ?)
            """
            cursor.execute(sql, (key, value))
            conn.commit()

    def save_session(self, token: str, username: str, expires_at: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO sessions (
                    token
                  , username
                  , created_at
                  , expires_at
                ) VALUES (?, ?, datetime('now'), ?)
            """
            cursor.execute(sql, (token, username, expires_at))
            conn.commit()

    def get_session(self, token: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT username
                  FROM sessions
                 WHERE token = ?
                   AND expires_at > datetime('now')
            """
            cursor.execute(sql, (token,))
            row = cursor.fetchone()
            return row[0] if row else None

    def delete_session(self, token: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                DELETE FROM sessions
                 WHERE token = ?
            """
            cursor.execute(sql, (token,))
            conn.commit()

    def cleanup_expired_sessions(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                DELETE FROM sessions
                 WHERE expires_at <= datetime('now')
            """
            cursor.execute(sql)
            conn.commit()

    def get_email_settings(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT id
                     , gmail_account
                     , from_email
                     , to_email
                     , cc_email
                     , email_subject
                     , gmail_app_password
                  FROM email_settings
                 WHERE id = 1
            """
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "gmail_account": row[1],
                    "from_email": row[2],
                    "to_email": row[3],
                    "cc_email": row[4],
                    "email_subject": row[5],
                    "gmail_app_password": row[6],
                }
            return None

    def save_email_settings(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO email_settings (
                    id
                  , gmail_account
                  , from_email
                  , to_email
                  , cc_email
                  , email_subject
                  , gmail_app_password
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql,
                (
                    data.get("gmail_account"),
                    data.get("from_email"),
                    data.get("to_email"),
                    data.get("cc_email"),
                    data.get("email_subject"),
                    data.get("gmail_app_password"),
                ),
            )
            conn.commit()

    def get_user(self, username: str) -> Optional[bytes]:
        """
        Get hashed password for a user.

        Args:
            username: Username to look up

        Returns:
            Password hash as bytes, or None if user not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT password_hash
                  FROM users
                 WHERE username = ?
            """
            cursor.execute(sql, (username,))
            row = cursor.fetchone()
            return row[0] if row else None

    def save_user(self, username: str, password_hash: bytes) -> None:
        """
        Save or update a user's hashed password.

        Args:
            username: Username
            password_hash: Bcrypt password hash as bytes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO users (
                    username
                  , password_hash
                  , updated_at
                ) VALUES (?, ?, datetime('now'))
            """
            cursor.execute(sql, (username, password_hash))
            conn.commit()

    def get_all_users(self) -> Dict[str, bytes]:
        """
        Get all users and their password hashes.

        Returns:
            Dictionary mapping username to password hash
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT username
                     , password_hash
                  FROM users
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}
