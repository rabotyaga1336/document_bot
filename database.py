import os
import sqlite3
import base64
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
                               file_name TEXT,  -- Добавляем колонку file_name
                               file_path TEXT)''')
        # Удаляем file_id, так как он больше не нужен
        try:
            self.cursor.execute("ALTER TABLE documents DROP COLUMN file_id")
        except sqlite3.OperationalError:
            # Игнорируем ошибку, если столбец уже удалён
            pass

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
                               images TEXT,
                               category TEXT,
                               created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        self.conn.commit()

    def save_document(self, category, file_name, file_path):
        # Убеждаемся, что file_path валиден
        if not os.path.exists(file_path):
            raise ValueError(f"File path {file_path} does not exist")

        # Заменяем / на _ для корректности пути в базе данных
        safe_category = category.replace("/", "_")

        # Сохраняем в базу данных
        self.cursor.execute(
            "INSERT INTO documents (category, file_name, file_path) VALUES (?, ?, ?)",
            (safe_category, file_name, file_path)
        )
        self.conn.commit()

        # Получаем ID последней вставленной записи
        self.cursor.execute("SELECT last_insert_rowid()")
        return self.cursor.fetchone()[0]

    def get_documents(self, category, limit=None):
        try:
            query = "SELECT id, file_name, file_path FROM documents WHERE category = ?"
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
            logging.info(f"Получено ссылок для категории {category}: {result}")
            return result
        except sqlite3.Error as e:
            logging.error(f"Ошибка при получении ссылок: {e}")
            raise

    def delete_link(self, link_id, category):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM links WHERE id = ? AND category = ?", (link_id, category))
        self.conn.commit()
        return cursor.rowcount > 0

    def save_announcement(self, title, text, images_str, category):
        logger.info(
            f"Сохранение объявления: title={title}, text_length={len(text) if text else 0}, images_length={len(images_str) if images_str else 0}, category={category}")
        try:
            self.cursor.execute('''
                INSERT INTO announcements (title, text, images, category, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (title, text, images_str, category))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Ошибка при сохранении в базу данных: {str(e)}")
            raise

    def get_announcement(self, ann_id):
        try:
            self.cursor.execute('SELECT title, text, images, category FROM announcements WHERE id = ?', (ann_id,))
            result = self.cursor.fetchone()
            return result if result else None
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении объявления: {str(e)}")
            raise

    def get_announcements(self, category):
        try:
            self.cursor.execute(
                'SELECT id, title, text, images, category, created_at FROM announcements WHERE category = ?',
                (category,))
            results = self.cursor.fetchall()
            return results if results else []
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении объявлений: {str(e)}")
            raise

    def delete_announcement(self, ann_id):
        try:
            # Сначала получаем пути к изображениям
            self.cursor.execute('SELECT images FROM announcements WHERE id = ?', (ann_id,))
            result = self.cursor.fetchone()
            if result and result[0]:
                images_str = result[0]
                if images_str:
                    image_paths = images_str.split(',')
                    for path in image_paths:
                        if os.path.exists(path):
                            os.remove(path)
                            logger.info(f"Удалён файл изображения: {path}")
            # Удаляем запись из базы
            self.cursor.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            self.conn.commit()
            logger.info(f"Объявление с ID {ann_id} удалено")
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при удалении объявления: {str(e)}")
            raise

    def update_announcement(self, ann_id, title, text, images_str):
        try:
            self.cursor.execute('''
                UPDATE announcements
                SET title = ?, text = ?, images = ?
                WHERE id = ?
            ''', (title, text, images_str, ann_id))
            self.conn.commit()
            logger.info(f"Объявление с ID {ann_id} обновлено")
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении объявления: {str(e)}")
            raise

    def __del__(self):
        self.conn.close()


db = Database()