import sqlite3
import base64
import logging

class Database:
    def __init__(self, db_name="bot.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # Таблица для документов
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS documents
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               category TEXT,
                               file_id TEXT,
                               file_name TEXT)''')
        # Таблица для ссылок
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS links
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               category TEXT,
                               url TEXT,
                               description TEXT)''')
        # Таблица для объявлений
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS announcements
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               title TEXT NOT NULL,
                               text TEXT NOT NULL,
                               image TEXT)''')
        self.conn.commit()

    def save_document(self, category, file_id, file_name):
        self.cursor.execute("INSERT INTO documents (category, file_id, file_name) VALUES (?, ?, ?)",
                           (category, file_id, file_name))
        self.conn.commit()
        self.cursor.execute("SELECT last_insert_rowid()")
        return self.cursor.fetchone()[0]

    def get_documents(self, category, limit=None):
        try:
            query = "SELECT id, file_id, file_name FROM documents WHERE category = ?"
            params = [category]
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            self.cursor.execute(query, params)
            result = self.cursor.fetchall()
            logging.info(f"Получено документов для категории {category}: {result}")
            return result
        except sqlite3.Error as e:
            logging.error(f"Ошибка при получении документов: {e}")
            raise

    def delete_document(self, doc_id):
        try:
            self.cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Ошибка при удалении документа: {e}")
            raise

    def save_link(self, category, url, description):
        try:
            self.cursor.execute("INSERT INTO links (category, url, description) VALUES (?, ?, ?)",
                                (category, url, description))
            self.conn.commit()
            logging.info(f"Ссылка сохранена в базе: category={category}, url={url}, description={description}")
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Ошибка при сохранении ссылки: {e}")
            raise

    def get_links(self, category, limit=None):
        try:
            query = "SELECT id, url, description FROM links WHERE category = ?"
            params = [category]
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            self.cursor.execute(query, params)
            result = self.cursor.fetchall()
            logging.info(f"Получено ссылок для категории {category}: {result}")  # Добавим лог
            return result
        except sqlite3.Error as e:
            logging.error(f"Ошибка при получении ссылок: {e}")
            raise

    def delete_link(self, link_id, category):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM links WHERE id = ? AND category = ?", (link_id, category))
        self.conn.commit()
        return cursor.rowcount > 0

    def save_announcement(self, title, text, image=None):
        self.cursor.execute("INSERT INTO announcements (title, text, image) VALUES (?, ?, ?)",
                           (title, text, image))
        self.conn.commit()
        self.cursor.execute("SELECT last_insert_rowid()")
        return self.cursor.fetchone()[0]

    def get_announcements(self):
        self.cursor.execute("SELECT id, title FROM announcements")
        return self.cursor.fetchall()

    def get_announcement(self, announcement_id):
        self.cursor.execute("SELECT title, text, image FROM announcements WHERE id = ?", (announcement_id,))
        return self.cursor.fetchone()

    def delete_announcement(self, announcement_id):
        self.cursor.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
        self.conn.commit()

    def __del__(self):
        self.conn.close()

db = Database()