import sqlite3

class Database:
    def __init__(self, db_name="documents.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS documents
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               category TEXT,
                               file_id TEXT,
                               file_name TEXT)''')
        self.conn.commit()

    def save_document(self, category, file_id, file_name):
        self.cursor.execute("INSERT INTO documents (category, file_id, file_name) VALUES (?, ?, ?)",
                           (category, file_id, file_name))
        self.conn.commit()

    def get_documents(self, category):
        self.cursor.execute("SELECT id, file_id, file_name FROM documents WHERE category = ?", (category,))
        return self.cursor.fetchall()

    def delete_document(self, doc_id, category):
        self.cursor.execute("DELETE FROM documents WHERE id = ? AND category = ?", (doc_id, category))
        self.conn.commit()

    def __del__(self):
        self.conn.close()

db = Database()