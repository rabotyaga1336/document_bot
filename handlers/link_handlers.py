import telegram.error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from database import db
import logging

from .menu_handlers import handle_back, start
from .utils import is_url, category_map
from config import ADMIN_IDS

# Состояния для ссылок
STATE_ADDING_LINKS = 0
STATE_DELETE_LINK_SELECTION = 1  # Состояние для выбора ссылки на удаление

async def handle_add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Активация добавления ссылки для категории: {context.user_data.get('current_category')} пользователем {user_id}")
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
        return
    category = context.user_data.get('current_category')
    if not category:
        logging.error("Категория не определена для добавления ссылки")
        await query.message.edit_text("Ошибка: выберите категорию перед добавлением ссылки.")
        keyboard = [[InlineKeyboardButton("Вернуться в меню", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await query.message.reply_text("Выберите категорию:", reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton("Завершить добавление", callback_data="done_link")],
        [InlineKeyboardButton("Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        message = await query.message.edit_text(
            f"Отправьте ссылку как простой текст (например, https://example.com) и на следующей строке укажите Описание "
            f"для категории '{category_map.get(category)}'. Нажмите 'Завершить добавление', когда закончите. "
            f"Описание станет названием кнопки.",
            reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
    except telegram.error.BadRequest:
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"Отправьте ссылку как простой текст (например, https://example.com) и, опционально, описание как caption "
                 f"для категории '{category_map.get(category)}'. Нажмите 'Завершить добавление', когда закончите. "
                 f"Описание станет названием кнопки.",
            reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
    context.user_data['link_data'] = []
    logging.info(f"Переход в состояние STATE_ADDING_LINKS для чата {chat_id}")
    return STATE_ADDING_LINKS

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Получено сообщение для обработки ссылки: text={update.message.text if update.message else 'None'}, "
                 f"caption={update.message.caption if update.message else 'None'}, "
                 f"document={update.message.document if update.message else 'None'}")
    if update.message:
        category = context.user_data.get('current_category')
        if 'link_data' not in context.user_data:
            context.user_data['link_data'] = []
        text = update.message.text.strip() if update.message.text else ""
        caption = update.message.caption if update.message.caption else ""
        # Игнорируем документы
        if update.message.document:
            message = await update.message.reply_text("Пожалуйста, отправляйте только текст или ссылку с caption, а не документы.")
        # Если текст — ссылка, используем его как URL, caption как описание
        elif is_url(text):
            url = text.split('\n')[0] if '\n' in text else text
            description = caption if caption else text[len(url):].strip() if '\n' in text else ""
            context.user_data['link_data'].append((url, description))
            logging.info(f"Добавлена ссылка в link_data: {url}, описание: {description}")
            message = await update.message.reply_text(
                f"Ссылка '{url}' добавлена. Продолжайте добавление или нажмите 'Завершить добавление'. "
                f"Описание: {description if description else 'Не указано'}",
                parse_mode='HTML', disable_web_page_preview=True)
        # Если caption — ссылка, используем его как URL, текст как описание
        elif caption and is_url(caption):
            context.user_data['link_data'].append((caption, text))
            logging.info(f"Добавлена ссылка в link_data: {caption}, описание: {text}")
            message = await update.message.reply_text(
                f"Ссылка '{caption}' добавлена. Продолжайте добавление или нажмите 'Завершить добавление'. "
                f"Описание: {text if text else 'Не указано'}",
                parse_mode='HTML', disable_web_page_preview=True)
        else:
            message = await update.message.reply_text("Пожалуйста, отправьте корректную ссылку как текст или caption.")
        if 'message_ids' not in context.user_data:
            context.user_data['message_ids'] = []
        context.user_data['message_ids'].append(message.message_id)
        # Очистка чата, сохраняя только последнее сообщение
        current_message_id = message.message_id
        if 'message_ids' in context.user_data and len(context.user_data['message_ids']) > 1:
            for msg_id in context.user_data['message_ids'][:-1]:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                    logging.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
            context.user_data['message_ids'] = [current_message_id]
    return STATE_ADDING_LINKS

async def handle_done_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Завершение добавления ссылок для категории: {context.user_data.get('current_category')} пользователем {user_id}")
    await query.answer()
    chat_id = query.message.chat_id

    # Удаление предыдущих сообщений
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                logging.info(f"Удалено старое сообщение с ID: {msg_id}")
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = []

    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return
    if 'link_data' in context.user_data:
        category = context.user_data.get('current_category') or "Без категории"
        logging.info(f"Данные для сохранения: {context.user_data['link_data']}")
        for url, description in context.user_data['link_data']:
            link_id = db.save_link(category, url, description)
            logging.info(f"Сохранена ссылка с ID {link_id}: {url}, категория: {category}")
    if 'link_data' in context.user_data:
        del context.user_data['link_data']
    # Возврат в главное меню
    await handle_back(update, context)
    return ConversationHandler.END

async def handle_delete_link_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Выбор ссылки для удаления в категории: {context.user_data.get('current_category')} пользователем {user_id}")
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
        return
    category = context.user_data.get('current_category')
    if category:
        links = db.get_links(category)
        if links:
            keyboard = []
            for link_id, url, description in links:
                button_text = description if description else url[:20] + "..." if len(url) > 20 else url
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_link_{link_id}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"Выберите ссылку для удаления в категории '{category_map.get(category)}':",
                                                    reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return STATE_DELETE_LINK_SELECTION
        else:
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"В категории '{category_map.get(category)}' нет ссылок для удаления.", reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return ConversationHandler.END
    return

async def handle_delete_link_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logging.info(f"Удаление ссылки с ID: {query.data} пользователем {user_id}")
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
        return
    link_id = int(query.data.replace("delete_link_", ""))
    category = context.user_data.get('current_category')
    if category:
        try:
            db.delete_link(link_id, category)
            message = await query.message.edit_text(f"Ссылка с ID {link_id} удалена из категории '{category_map.get(category)}'.")
            context.user_data['message_ids'] = [message.message_id]
            logging.info(f"Ссылка с ID {link_id} успешно удалена")
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
            logging.error(f"Ошибка при удалении ссылки с ID {link_id}: {e}")
            await query.message.edit_text(f"Ошибка при удалении ссылки с ID {link_id}: {str(e)}")
    return ConversationHandler.END

def link_conversation_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_add_link, pattern="^add_link$"),
            CallbackQueryHandler(handle_delete_link_selection, pattern="^delete_link_select$")
        ],
        states={
            STATE_ADDING_LINKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link),
                CallbackQueryHandler(handle_done_link, pattern="^done_link$")
            ],
            STATE_DELETE_LINK_SELECTION: [
                CallbackQueryHandler(handle_delete_link_confirmed, pattern="^delete_link_")
            ]
        },
        fallbacks=[CallbackQueryHandler(handle_back, pattern="^back_to_main$")],
        allow_reentry=True
    )