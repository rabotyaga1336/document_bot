import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, \
    filters
from database import db
import logging
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Состояния для ConversationHandler
STATE_WAITING_FOR_DOCUMENTS, STATE_DELETE_DOC, STATE_DONE = range(3)

# Словарь для соответствия коротких идентификаторов и полных названий
category_map = {
    "doc1": "Базовые документы",
    "doc2": "Структура ППО",
    "doc3": "Правовая защита",
    "doc4": "Охрана труда",
    "doc5": "Оздоровление",
    "doc6": "Туристско-экскурсионная деятельность",
    "doc7": "Информационная работа",
    "doc8": "Объявления",
    "doc9": "Образцы документов",
    "doc10": "Полезные ссылки"
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Запуск команды /start")
    keyboard = [
        [InlineKeyboardButton("Базовые документы", callback_data="doc1"),
         InlineKeyboardButton("Структура ППО", callback_data="doc2")],
        [InlineKeyboardButton("Правовая защита", callback_data="doc3"),
         InlineKeyboardButton("Охрана труда", callback_data="doc4")],
        [InlineKeyboardButton("Оздоровление", callback_data="doc5"),
         InlineKeyboardButton("Туристско-экскурсионная деятельность", callback_data="doc6")],
        [InlineKeyboardButton("Информационная работа", callback_data="doc7"),
         InlineKeyboardButton("Объявления", callback_data="doc8")],
        [InlineKeyboardButton("Образцы документов", callback_data="doc9"),
         InlineKeyboardButton("Полезные ссылки", callback_data="doc10")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        message = await update.message.reply_text("Добро пожаловать в профсоюзного бота! Выберите категорию:",
                                                  reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
    else:
        message = await context.bot.send_message(chat_id=update.callback_query.message.chat_id,
                                                 text="Добро пожаловать в профсоюзного бота! Выберите категорию:",
                                                 reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
    logging.info(f"Инициализированы message_ids: {context.user_data.get('message_ids')}")


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"Обработка меню для категории: {query.data}")
    await query.answer()
    category = category_map.get(query.data)
    if category:
        context.user_data['current_category'] = category
        documents = db.get_documents(category)
        if documents:
            keyboard = [
                [InlineKeyboardButton("Просмотреть документы", callback_data="view_docs")],
                [InlineKeyboardButton("Добавить документы", callback_data="add_docs")],
                [InlineKeyboardButton("Главное меню", callback_data="back")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("Добавить документы", callback_data="add_docs")],
                [InlineKeyboardButton("Главное меню", callback_data="back")]
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await query.message.reply_text(f"Категория: {category}", reply_markup=reply_markup)
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []
        context.user_data['message_ids'].append(message.message_id)
        logging.info(f"Текущее состояние message_ids после handle_menu: {context.user_data.get('message_ids')}")
        return STATE_WAITING_FOR_DOCUMENTS
    await query.message.delete()
    return ConversationHandler.END


async def handle_view_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"Просмотр документов для категории: {context.user_data.get('current_category')}")
    await query.answer()
    category = context.user_data.get('current_category')
    if category:
        documents = db.get_documents(category)
        if documents:
            if 'message_ids' not in context.user_data:
                context.user_data['message_ids'] = []
            for doc_id, file_id, file_name in documents:
                # Проверяем, является ли file_id URL
                if is_url(file_id):
                    message = await query.message.reply_text(f"<a href='{file_id}'>{file_name}</a>", parse_mode='HTML')
                else:
                    doc_message = await context.bot.send_document(chat_id=query.message.chat_id, document=file_id,
                                                                  filename=file_name)
                    context.user_data['message_ids'].append(doc_message.message_id)
                    keyboard = [
                        [InlineKeyboardButton(f"Удалить {file_name}", callback_data=f"delete_{doc_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    text_message = await query.message.reply_text(f"Документ: {file_name}", reply_markup=reply_markup)
                    context.user_data['message_ids'].append(text_message.message_id)
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            back_message = await query.message.reply_text("Выберите действие или вернитесь назад.",
                                                          reply_markup=reply_markup)
            context.user_data['message_ids'].append(back_message.message_id)
            return STATE_DELETE_DOC
        else:
            message = await query.message.reply_text(f"В категории '{category}' нет документов.")
            if 'message_ids' not in context.user_data:
                context.user_data['message_ids'] = []
            context.user_data['message_ids'].append(message.message_id)
    await query.message.delete()
    return STATE_WAITING_FOR_DOCUMENTS


async def handle_delete_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"Удаление документа с ID: {query.data}")
    await query.answer()
    doc_id = int(query.data.replace("delete_", ""))
    category = context.user_data.get('current_category')
    if category:
        try:
            db.delete_document(doc_id, category)
            message = await query.message.edit_text(f"Документ с ID {doc_id} удален из категории '{category}'.")
            if 'message_ids' not in context.user_data:
                context.user_data['message_ids'] = []
            context.user_data['message_ids'].append(message.message_id)
            logging.info(f"Документ с ID {doc_id} успешно удален")
        except Exception as e:
            logging.error(f"Ошибка при удалении документа с ID {doc_id}: {e}")
            await query.message.edit_text(f"Ошибка при удалении документа с ID {doc_id}: {str(e)}")
    await query.message.delete()
    return STATE_WAITING_FOR_DOCUMENTS


async def handle_add_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"Добавление документов для категории: {context.user_data.get('current_category')}")
    await query.answer()
    category = context.user_data.get('current_category')
    if category:
        keyboard = [
            [InlineKeyboardButton("Завершить загрузку", callback_data="done")],
            [InlineKeyboardButton("Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await query.message.edit_text(
            f"Отправьте документы или ссылки для категории '{category}'. Нажмите 'Завершить загрузку', когда закончите.",
            reply_markup=reply_markup)
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []
        context.user_data['message_ids'].append(message.message_id)
    return STATE_WAITING_FOR_DOCUMENTS


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Получен документ для категории: {context.user_data.get('current_category')}")
    if update.message and (update.message.document or update.message.text):
        category = context.user_data.get('current_category') or update.message.caption or "Без категории"
        if 'media_group_docs' not in context.user_data:
            context.user_data['media_group_docs'] = []

        if update.message.text and is_url(update.message.text):
            # Если это URL, сохраняем его как ссылку
            context.user_data['media_group_docs'].append({
                'file_id': update.message.text,  # Сохраняем URL как file_id
                'file_name': update.message.text.split('/')[-1] or 'Ссылка'
            })
            message = await update.message.reply_text(
                f"Ссылка '{update.message.text}' добавлена. Продолжайте загрузку или завершите.", parse_mode='HTML')
        elif update.message.document:
            # Если это файл, обрабатываем как обычно
            file = await update.message.document.get_file()
            context.user_data['media_group_docs'].append({
                'file_id': update.message.document.file_id,
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
    logging.info(f"Завершение загрузки для категории: {context.user_data.get('current_category')}")
    await query.answer()
    if 'media_group_docs' in context.user_data:
        category = context.user_data.get('current_category') or "Без категории"
        for doc in context.user_data['media_group_docs']:
            db.save_document(category, doc['file_id'], doc['file_name'])
            if is_url(doc['file_id']):
                message = await query.message.reply_text(f"<a href='{doc['file_id']}'>{doc['file_name']}</a>",
                                                         parse_mode='HTML')
            else:
                message = await query.message.reply_text(
                    f"Документ '{doc['file_name']}' сохранен в категории '{category}'.")
            if 'message_ids' not in context.user_data:
                context.user_data['message_ids'] = []
            context.user_data['message_ids'].append(message.message_id)
        # Очищаем данные
        del context.user_data['media_group_docs']
        del context.user_data['current_category']
    await query.message.delete()
    return ConversationHandler.END


async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info("Возврат в главное меню")
    await query.answer()
    chat_id = query.message.chat_id
    if 'message_ids' in context.user_data:
        for message_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                time.sleep(0.1)  # Небольшая задержка, чтобы избежать превышения лимита Telegram
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение {message_id}: {e}")
        del context.user_data['message_ids']
    # Проверяем, существует ли query.message перед удалением
    if query.message and not query.message.chat_id == 0:  # chat_id == 0 для inline-запросов
        try:
            await query.message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить query.message: {e}")
    await start(update, context)  # Вызываем start для отображения главного меню
    if 'media_group_docs' in context.user_data:
        del context.user_data['media_group_docs']
    if 'current_category' in context.user_data:
        del context.user_data['current_category']
    return ConversationHandler.END


# Функция для проверки, является ли строка URL
def is_url(text):
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    return bool(url_pattern.match(text))


def document_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu, pattern="^doc[1-9]|doc10$")],
        states={
            STATE_WAITING_FOR_DOCUMENTS: [
                CallbackQueryHandler(handle_add_docs, pattern="^add_docs$"),
                CallbackQueryHandler(handle_view_docs, pattern="^view_docs$"),
                CallbackQueryHandler(handle_done, pattern="^done$"),
                CallbackQueryHandler(handle_back, pattern="^back$"),
                MessageHandler(filters.Document.ALL | filters.TEXT, handle_document)  # Добавляем фильтр для текста
            ],
            STATE_DELETE_DOC: [
                CallbackQueryHandler(handle_delete_doc, pattern="^delete_"),
                CallbackQueryHandler(handle_back, pattern="^back_to_menu$")
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )


# Регистрация обработчиков
def register_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(document_conversation_handler())