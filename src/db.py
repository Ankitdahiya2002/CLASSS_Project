import os
import sys
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import hashlib
import io

DB_FILE = "omnisicient.db"


# ---------------- Database Connection ----------------
def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- Table Creation ----------------
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        name TEXT,
        profession TEXT,
        verified INTEGER DEFAULT 0,
        verification_token TEXT,
        verification_token_expiry TEXT,
        reset_token TEXT,
        reset_token_expiry TEXT,
        blocked INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user'
    );
    """)

    # Chats table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        user_input TEXT,
        ai_response TEXT,
        thread_id TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_email) REFERENCES users(email)
    );
    """)

    # Uploaded files table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        file_name TEXT,
        file_type TEXT,
        extracted_text TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_email) REFERENCES users(email)
    );
    """)

    # Email logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT,
        subject TEXT,
        status TEXT,
        error TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


# ---------------- Safe Initialization ----------------
def safe_initialize():
    try:
        create_tables()
    except sqlite3.DatabaseError as e:
        try:
            backup_path = DB_FILE + ".corrupt.bak"
            os.rename(DB_FILE, backup_path)
        except Exception:
            pass
        try:
            os.remove(DB_FILE)
            create_tables()
        except Exception:
            sys.exit(1)


# ---------------- User Functions ----------------
def create_user(email, password_hash, name="", profession="", verification_token=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return False

    expiry = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO users (email, password, name, profession, verified, verification_token, verification_token_expiry)
        VALUES (?, ?, ?, ?, 0, ?, ?)
    """, (email, password_hash, name, profession, verification_token, expiry))

    conn.commit()
    conn.close()
    return True


def get_user(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def is_user_verified(email):
    user = get_user(email)
    return user and user.get("verified") == 1


def update_reset_token(email, token, expiry):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET reset_token = ?, reset_token_expiry = ?
        WHERE email = ?
    """, (token, expiry.strftime("%Y-%m-%d %H:%M:%S"), email))
    conn.commit()
    conn.close()


def reset_user_password_by_token(token, new_hashed_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, reset_token_expiry FROM users WHERE reset_token = ?", (token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    email = row["email"]
    expiry = datetime.strptime(row["reset_token_expiry"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        conn.close()
        return False

    cursor.execute("""
        UPDATE users
        SET password = ?, reset_token = NULL, reset_token_expiry = NULL
        WHERE email = ?
    """, (new_hashed_password, email))
    conn.commit()
    conn.close()
    return True


def verify_user_credentials(email, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed))
    user = cursor.fetchone()
    conn.close()
    return user is not None


def verify_user_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, verified, verification_token_expiry FROM users WHERE verification_token = ?", (token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    expiry = datetime.strptime(row["verification_token_expiry"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        conn.close()
        return False

    if row["verified"]:
        conn.close()
        return True

    cursor.execute("""
        UPDATE users
        SET verified = 1, verification_token = NULL, verification_token_expiry = NULL
        WHERE email = ?
    """, (row["email"],))
    conn.commit()
    conn.close()
    return True


# ---------------- Chat Functions ----------------
def save_chat(user_email, user_input, ai_response, thread_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chats (user_email, user_input, ai_response, thread_id)
        VALUES (?, ?, ?, ?)
    """, (user_email, user_input, ai_response, thread_id))
    conn.commit()
    conn.close()


def get_user_chats(user_email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE user_email = ? ORDER BY timestamp ASC", (user_email,))
    chats = cursor.fetchall()
    conn.close()
    return [dict(chat) for chat in chats]


def delete_user_chats(user_email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chats WHERE user_email = ?", (user_email,))
    conn.commit()
    conn.close()


def export_chats_to_csv():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return ""
    df = pd.DataFrame([dict(row) for row in rows])
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()


# ---------------- File Functions ----------------
def save_uploaded_file(user_email, file_name, file_type, extracted_text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO uploaded_files (user_email, file_name, file_type, extracted_text)
        VALUES (?, ?, ?, ?)
    """, (user_email, file_name, file_type, extracted_text))
    conn.commit()
    conn.close()


def get_uploaded_files(user_email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM uploaded_files WHERE user_email = ? ORDER BY timestamp DESC", (user_email,))
    files = cursor.fetchall()
    conn.close()
    return [dict(f) for f in files]


# ---------------- Email Logs ----------------
def log_email_status(recipient, subject, status, error=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_logs (recipient, subject, status, error)
        VALUES (?, ?, ?, ?)
    """, (recipient, subject, status, error))
    conn.commit()
    conn.close()


def get_email_logs(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- Admin/User Helpers ----------------
def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY email")
    rows = cursor.fetchall()
    conn.close()
    return [dict(u) for u in rows]


def block_user(email, block=True):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET blocked = ? WHERE email = ?", (1 if block else 0, email))
    conn.commit()
    conn.close()


def count_registered_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ---------------- Run safe initialization ----------------
if __name__ == "__main__":
    safe_initialize()
