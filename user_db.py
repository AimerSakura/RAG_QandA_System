# user_db.py
import hashlib
import sqlite3
import os

DB_PATH = "users.db"

def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )''')
        conn.commit()
        conn.close()

def register_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    exists = c.fetchone()
    if exists:
        conn.close()
        return False, "用户名已存在，请更换用户名"
    pw_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    c.execute("INSERT INTO users (username, password_hash) VALUES (?,?)", (username, pw_hash))
    conn.commit()
    conn.close()
    return True, "注册成功"

def verify_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        stored_hash = row[0]
        pw_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return stored_hash == pw_hash
    return False
