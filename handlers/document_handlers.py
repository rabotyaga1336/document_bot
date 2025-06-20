import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from database import db
import logging

from .utils import is_url, category_map
from config import ADMIN_IDS
from .menu_handlers import handle_back

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния для документов
STATE_WAITING_FOR_DOCUMENTS, STATE_DELETE_DOC, STATE_DELETE_SELECTION = range(0, 3)

async def handle_menu_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Обработка меню документов для категории: {query.data} пользователем {user_id}")
    await query.answer()
    logging.info(f"Пользователь {user_id} открыл категорию {query.data}")
    chat_id = query.message.chat_id

    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id

    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logging.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]

    category_key = query.data
    if category_key:
        context.user_data['current_category'] = category_key  # Установка категории
        documents = db.get_documents(category_key)
        links = db.get_links(category_key)
        announcements = db.get_announcements(category_key)  # Получаем объявления
        logging.info(f"Получено документов: {len(documents)}, ссылок: {len(links)}, объявлений: {len(announcements)} для категории {category_key}")
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []

        # Отображение данных
        if not documents and not links and not announcements:
            message = await query.message.reply_text(f"Ссылки в категории: {category_map.get(category_key)}\n\nЗдесь пока ничего нет.")
            context.user_data['message_ids'].append(message.message_id)
        else:
            if documents:
                for doc_id, file_name, file_path in documents:  # Используем file_name и file_path
                    if is_url(file_path):  # Проверяем, является ли file_path URL
                        message = await query.message.reply_text(f"<a href='{file_path}'>{file_name}</a>",
                                                                 parse_mode='HTML', disable_web_page_preview=True)
                    else:
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as document:
                                message = await context.bot.send_document(chat_id=chat_id, document=document, filename=file_name)
                            logging.info(f"Отправлен документ: {file_name} из {file_path}")
                        else:
                            message = await query.message.reply_text(f"Файл {file_name} не найден.")
                    context.user_data['message_ids'].append(message.message_id)
                    await asyncio.sleep(0.1)
            if links:
                keyboard = []
                for link_id, url, description in links:
                    logging.info(f"Отображение ссылки: {url}, описание: {description}")
                    button_text = description if description else url[:20] + "..." if len(url) > 20 else url
                    clean_url = url.split('\n')[0] if '\n' in url else url
                    keyboard.append([InlineKeyboardButton(button_text, url=clean_url)])
                if keyboard:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message = await query.message.reply_text(f"Ссылки в категории: {category_map.get(category_key)}", reply_markup=reply_markup)
                    context.user_data['message_ids'].append(message.message_id)

            if announcements:
                keyboard = []
                for ann_id, title, text, images, category, created_at in announcements:
                    keyboard.append([InlineKeyboardButton(title, callback_data=f"view_announcement_{ann_id}")])
                if keyboard:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message = await query.message.reply_text(f"Объявления в категории: {category_map.get(category_key)}", reply_markup=reply_markup)
                    context.user_data['message_ids'].append(message.message_id)

        keyboard = []
        if user_id in ADMIN_IDS:
            keyboard.extend([
                [InlineKeyboardButton("Добавить документы", callback_data="add_docs")],
                [InlineKeyboardButton("Добавить ссылки", callback_data="add_link")],
                [InlineKeyboardButton("Добавить объявление", callback_data="add_announcement")],
                [InlineKeyboardButton("Удалить документ", callback_data="delete_select")],
                [InlineKeyboardButton("Удалить объявление", callback_data="delete_announcement")],
                [InlineKeyboardButton("Редактировать объявление", callback_data="edit_announcement")]
            ])
            if links:  # Показываем кнопку удаления ссылок только если есть ссылки
                keyboard.append([InlineKeyboardButton("Удалить ссылку", callback_data="delete_link_select")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
        context.user_data['message_ids'].append(message.message_id)
        return STATE_WAITING_FOR_DOCUMENTS
    logging.warning("Завершение ConversationHandler без удаления query.message")
    return ConversationHandler.END

async def handle_delete_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Удаление документа с ID: {query.data} пользователем {user_id}")
    await query.answer()
    chat_id = query.message.chat_id

    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id

    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logging.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]

    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    doc_id = int(query.data.replace("delete_", ""))
    category = context.user_data.get('current_category')
    if category:
        try:
            # Получаем информацию о документе перед удалением
            documents = db.get_documents(category)
            for id_, file_name, file_path in documents:
                if id_ == doc_id:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logging.info(f"Удалён файл: {file_path}")
                    break
            # Удаляем запись из базы данных
            if db.delete_document(doc_id):
                message = await query.message.edit_text(f"Документ с ID {doc_id} удален из категории '{category_map.get(category)}'.")
                context.user_data['message_ids'] = [message.message_id]
                logging.info(f"Документ с ID {doc_id} успешно удален")
            else:
                message = await query.message.edit_text(f"Документ с ID {doc_id} не найден в базе данных.")
                context.user_data['message_ids'] = [message.message_id]
            # Удаляем все сообщения перед возвратом
            if 'message_ids' in context.user_data and context.user_data['message_ids']:
                for msg_id in context.user_data['message_ids']:
                    try:
                        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                        logging.info(f"Deleted message with ID: {msg_id}")
                    except Exception as e:
                        logging.warning(f"Failed to delete message {msg_id}: {str(e)}")
            await handle_back(update, context)
        except Exception as e:
            logging.error(f"Ошибка при удалении документа с ID {doc_id}: {e}")
            await query.message.edit_text(f"Ошибка при удалении документа с ID {doc_id}: {str(e)}")
    return ConversationHandler.END

async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Выбор документа для удаления в категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
    chat_id = query.message.chat_id

    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id

    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logging.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]

    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    category = context.user_data.get('current_category')
    if category:
        documents = db.get_documents(category)
        if documents:
            keyboard = []
            for doc_id, file_name, file_path in documents:  # Используем file_name и file_path
                button_text = f"Удалить {file_name}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{doc_id}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"Выберите документ для удаления в категории '{category_map.get(category)}':",
                                                    reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return STATE_DELETE_DOC
        else:
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"В категории '{category_map.get(category)}' нет документов для удаления.", reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return STATE_WAITING_FOR_DOCUMENTS
    return STATE_WAITING_FOR_DOCUMENTS

async def handle_add_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Добавление документов для категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
    chat_id = query.message.chat_id

    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id

    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logging.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]

    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    category = context.user_data.get('current_category')
    if category:
        keyboard = [
            [InlineKeyboardButton("Завершить загрузку", callback_data="done")],
            [InlineKeyboardButton("Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await query.message.edit_text(
            f"Отправьте документы для категории '{category_map.get(category)}'. Нажмите 'Завершить загрузку', когда закончите.",
            reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        context.user_data['media_group_docs'] = []
    return STATE_WAITING_FOR_DOCUMENTS

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    chat_id = update.message.chat_id
    logging.info(f"Received document, Chat ID: {chat_id}, File name: {document.file_name}")

    # Определяем категорию из context.user_data
    category = context.user_data.get('current_category', 'default')
    base_dir = "documents"
    folder_name = category_map.get(category, category)  # Используем название раздела из category_map
    folder_path = os.path.join(base_dir, folder_name)  # Папка соответствует названию раздела

    # Создаём папку, если её нет
    os.makedirs(folder_path, exist_ok=True)

    # Используем оригинальное имя файла
    file_name = document.file_name
    file_path = os.path.join(folder_path, file_name)

    # Проверяем, не существует ли файл с таким именем, и добавляем суффикс, если да
    base_name = os.path.splitext(file_name)[0]
    extension = os.path.splitext(file_name)[1]
    counter = 1
    while os.path.exists(file_path):
        file_name = f"{base_name}_{counter}{extension}"
        file_path = os.path.join(folder_path, file_name)
        counter += 1

    # Скачиваем файл
    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(file_path)
    logging.info(f"Document saved at: {file_path}, Size: {os.path.getsize(file_path)} bytes")

    # Сохраняем путь в базу данных
    db.save_document(category, file_name, file_path)

    await update.message.reply_text(f"Документ '{file_name}' сохранён в категории '{category_map.get(category)}' по пути {file_path}.")
    return

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Завершение загрузки для категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
    chat_id = query.message.chat_id

    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id

    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logging.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]

    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    if 'media_group_docs' in context.user_data:
        category = context.user_data.get('current_category') or "Без категории"
        folder_name = category_map.get(category, category)
        folder_path = os.path.join("documents", folder_name)
        os.makedirs(folder_path, exist_ok=True)
        for doc in context.user_data['media_group_docs']:
            file_name = doc['file_name']
            file_path = os.path.join(folder_path, file_name)
            base_name = os.path.splitext(file_name)[0]
            extension = os.path.splitext(file_name)[1]
            counter = 1
            while os.path.exists(file_path):
                file_name = f"{base_name}_{counter}{extension}"
                file_path = os.path.join(folder_path, file_name)
                counter += 1
            with open(file_path, 'wb') as f:
                f.write(doc['content'])
            db.save_document(category, file_name, file_path)
            message = await query.message.reply_text(
                f"Документ '{file_name}' сохранен в категории '{category_map.get(category)}'.")
            context.user_data['message_ids'].append(message.message_id)
        del context.user_data['media_group_docs']
    # Удаляем все сообщения перед возвратом
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                logging.info(f"Deleted message with ID: {msg_id}")
            except Exception as e:
                logging.warning(f"Failed to delete message {msg_id}: {str(e)}")
    await handle_back(update, context)
    return ConversationHandler.END

def document_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu_documents, pattern="^doc[1-9]|doc10$")],
        states={
            STATE_WAITING_FOR_DOCUMENTS: [
                CallbackQueryHandler(handle_add_docs, pattern="^add_docs$"),
                CallbackQueryHandler(handle_done, pattern="^done$"),
                CallbackQueryHandler(handle_back, pattern=r"^back$"),
                CallbackQueryHandler(handle_delete_selection, pattern="^delete_select$"),
                MessageHandler(filters.Document.ALL, handle_document)
            ],
            STATE_DELETE_DOC: [
                CallbackQueryHandler(handle_delete_doc, pattern="^delete_"),
                CallbackQueryHandler(handle_back, pattern=r"^back$")
            ],
            STATE_DELETE_SELECTION: [
                CallbackQueryHandler(handle_delete_doc, pattern="^delete_"),
                CallbackQueryHandler(handle_back, pattern=r"^back$")
            ]
        },
        fallbacks=[CallbackQueryHandler(handle_back, pattern="^back_to_main$")],
        allow_reentry=True
    )