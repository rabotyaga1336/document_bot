import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def start(update, context):
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
    message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                             text="Добро пожаловать в профсоюзного бота! Выберите категорию:",
                                             reply_markup=reply_markup)
    context.user_data['message_ids'] = [message.message_id]
    logging.info(f"Отправлено новое меню с message_id: {message.message_id}")

async def handle_back(update, context):
    query = update.callback_query
    logging.info("Возврат в главное меню. Текущее query.message: %s", query.message if query else "None")
    await query.answer()
    chat_id = query.message.chat_id if query.message else update.effective_chat.id

    # Очистка и удаление предыдущих сообщений
    if 'message_ids' in context.user_data:
        for msg_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                logging.info(f"Удалено старое сообщение с ID: {msg_id}")
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        del context.user_data['message_ids']
    if 'current_category' in context.user_data:
        del context.user_data['current_category']

    # Вызов start для нового меню
    await start(update, context)