import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from database import db
import logging
from .utils import is_url, category_map
from config import ADMIN_IDS
from .menu_handlers import handle_back, start

# Состояния для документов
STATE_WAITING_FOR_DOCUMENTS, STATE_DELETE_DOC, STATE_DELETE_SELECTION = range(0, 3)

async def handle_menu_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Обработка меню документов для категории: {query.data} пользователем {user_id}")
    await query.answer()
    chat_id = query.message.chat_id

    # Удаление предыдущего сообщения
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                logging.info(f"Удалено старое сообщение с ID: {msg_id}")
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = []  # Очистка после удаления

    category_key = query.data
    if category_key:
        context.user_data['current_category'] = category_key  # Установка категории
        documents = db.get_documents(category_key)
        links = db.get_links(category_key)
        logging.info(f"Получено документов: {len(documents)}, ссылок: {len(links)} для категории {category_key}")
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []

        # Отображение данных
        if not documents and not links:
            message = await query.message.reply_text(f"Категория: {category_map.get(category_key)}\n\nЗдесь пока ничего нет.")
            context.user_data['message_ids'].append(message.message_id)
        else:
            if documents:
                for doc_id, file_id, file_name in documents:
                    if is_url(file_id):
                        message = await query.message.reply_text(f"<a href='{file_id}'>{file_name}</a>",
                                                                 parse_mode='HTML', disable_web_page_preview=True)
                    else:
                        message = await context.bot.send_document(chat_id=chat_id, document=file_id,
                                                                  filename=file_name)
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
                    message = await query.message.reply_text(f"Категория: {category_map.get(category_key)}", reply_markup=reply_markup)
                    context.user_data['message_ids'].append(message.message_id)

        keyboard = []
        if user_id in ADMIN_IDS:
            keyboard.extend([
                [InlineKeyboardButton("Добавить документы", callback_data="add_docs")],
                [InlineKeyboardButton("Добавить ссылки", callback_data="add_link")],
                [InlineKeyboardButton("Удалить документ", callback_data="delete_select")]
            ])
            if links:  # Показываем кнопку удаления ссылок только если есть ссылки
                keyboard.append([InlineKeyboardButton("Удалить ссылку", callback_data="delete_link_select")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
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
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    doc_id = int(query.data.replace("delete_", ""))
    category = context.user_data.get('current_category')
    if category:
        try:
            db.delete_document(doc_id, category)
            message = await query.message.edit_text(f"Документ с ID {doc_id} удален из категории '{category_map.get(category)}'.")
            context.user_data['message_ids'].append(message.message_id)
            logging.info(f"Документ с ID {doc_id} успешно удален")
            # Очистка данных и возврат в главное меню
            await handle_back(update, context)
            await start(update, context)  # Вызов start для отображения главного меню
        except Exception as e:
            logging.error(f"Ошибка при удалении документа с ID {doc_id}: {e}")
            await query.message.edit_text(f"Ошибка при удалении документа с ID {doc_id}: {str(e)}")
    return ConversationHandler.END

async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Выбор документа для удаления в категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    category = context.user_data.get('current_category')
    if category:
        documents = db.get_documents(category)
        if documents:
            keyboard = []
            for doc_id, file_id, file_name in documents:
                button_text = f"Удалить {file_name}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{doc_id}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"Выберите документ для удаления в категории '{category_map.get(category)}':",
                                                    reply_markup=reply_markup)
            context.user_data['message_ids'].append(message.message_id)
            return STATE_DELETE_DOC
        else:
            message = await query.message.edit_text(f"В категории '{category_map.get(category)}' нет документов для удаления.")
            context.user_data['message_ids'].append(message.message_id)
    return STATE_WAITING_FOR_DOCUMENTS

async def handle_add_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Добавление документов для категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
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
        context.user_data['message_ids'].append(message.message_id)
        context.user_data['media_group_docs'] = []
    return STATE_WAITING_FOR_DOCUMENTS

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Получен документ для категории: {context.user_data.get('current_category')}")
    if update.message and update.message.document:
        category = context.user_data.get('current_category') or "Без категории"
        if 'media_group_docs' not in context.user_data:
            context.user_data['media_group_docs'] = []
        file = await update.message.document.get_file()
        context.user_data['media_group_docs'].append({
            'doc_id': None,
            'content': update.message.document.file_id,
            'file_name': update.message.document.file_name
        })
        message = await update.message.reply_text(
            f"Документ '{update.message.document.file_name}' добавлен. Продолжайте загрузку или завершите.")
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []
        context.user_data['message_ids'].append(message.message_id)
    return STATE_WAITING_FOR_DOCUMENTS

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Завершение загрузки для категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return STATE_WAITING_FOR_DOCUMENTS
    if 'media_group_docs' in context.user_data:
        category = context.user_data.get('current_category') or "Без категории"
        for doc in context.user_data['media_group_docs']:
            doc_id = db.save_document(category, doc['content'], doc['file_name'])
            message = await query.message.reply_text(
                f"Документ '{doc['file_name']}' сохранен в категории '{category_map.get(category)}'.")
            context.user_data['message_ids'].append(message.message_id)
        del context.user_data['media_group_docs']
    # Очистка данных и возврат в главное меню
    await handle_back(update, context)
    await start(update, context)  # Вызов start для отображения главного меню
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
        fallbacks=[],
        allow_reentry=True
    )