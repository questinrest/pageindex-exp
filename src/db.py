import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "docs.db")

try:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        file_name TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        tree_structure TEXT,
        created_at TEXT DEFAULT (DATETIME('now', 'localtime'))      
    )
''')
        print("Database and table ensured.")
except sqlite3.Error as e:
    print(f"An error occurred: {e}")