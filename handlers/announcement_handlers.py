import os
import asyncio
from io import BytesIO
from PIL import Image
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.helpers import escape_markdown

from database import db
import logging

from config import ADMIN_IDS
from .menu_handlers import handle_back, start
from .utils import category_map

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния для объявлений
STATE_WAITING_FOR_ACTION, STATE_WAITING_FOR_TITLE, STATE_WAITING_FOR_TEXT, STATE_WAITING_FOR_IMAGES, STATE_CONFIRM_ADD = range(0, 5)
# Состояния для удаления
STATE_DELETE_CONFIRMATION = 5
# Состояния для редактирования
STATE_EDIT_ANNOUNCEMENT, STATE_EDIT_TITLE, STATE_EDIT_TEXT, STATE_EDIT_IMAGES = range(6, 10)

async def handle_announcement_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Received callback query: {query.data}")
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return ConversationHandler.END
    if query.data == "delete_announcement":
        return await handle_delete_announcement(update, context)
    elif query.data == "edit_announcement":
        return await handle_edit_announcement(update, context)
    elif query.data == "add_announcement":
        logger.info("Handling add announcement")
        return await start_announcement(update, context)
    logger.warning(f"Unhandled callback data: {query.data}")
    return ConversationHandler.END

async def start_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Starting announcement addition process for user {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return ConversationHandler.END
    context.user_data['announcement_data'] = {'image_paths': []}
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        message = await query.message.edit_text("Введите заголовок объявления:", reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        logger.info(f"Transition to STATE_WAITING_FOR_TITLE. Message ID: {message.message_id}")
        return STATE_WAITING_FOR_TITLE
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await query.message.edit_text("Произошла ошибка. Попробуйте снова.")
        return ConversationHandler.END

async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received title: {update.message.text}, Chat ID: {update.effective_chat.id}")
    user_text = update.message.text
    context.user_data['announcement_data']['title'] = user_text
    # Сохранение текущего message_id перед очисткой
    current_message_id = update.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        message = await update.message.reply_text("Введите текст объявления:", reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        logger.info(f"Transition to STATE_WAITING_FOR_TEXT. Message ID: {message.message_id}")
        return STATE_WAITING_FOR_TEXT
    except Exception as e:
        logger.error(f"Error sending text: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
        return ConversationHandler.END

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received text: {update.message.text}, Chat ID: {update.effective_chat.id}")
    user_text = update.message.text
    context.user_data['announcement_data']['text'] = user_text
    # Сохранение текущего message_id перед очисткой
    current_message_id = update.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Добавить изображения (опционально)", callback_data="add_images")],
        [InlineKeyboardButton("Завершить без изображений", callback_data="done_no_images")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        message = await update.message.reply_text("Хотите добавить изображения? Выберите действие:", reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        logger.info(f"Transition to STATE_WAITING_FOR_IMAGES. Message ID: {message.message_id}")
        return STATE_WAITING_FOR_IMAGES
    except Exception as e:
        logger.error(f"Error sending image choice: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
        return ConversationHandler.END

async def handle_add_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Activating image addition. Query: {query}")
    await query.answer()
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Завершить с изображениями", callback_data="done_with_images")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        message = await query.message.edit_text("Отправьте изображения. Нажмите 'Завершить с изображениями', когда закончите.", reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        if 'image_paths' not in context.user_data['announcement_data']:
            context.user_data['announcement_data']['image_paths'] = []
        logger.info(f"Transition to STATE_CONFIRM_ADD. Message ID: {message.message_id}")
        return STATE_CONFIRM_ADD
    except Exception as e:
        logger.error(f"Error editing message for images: {e}")
        await query.message.edit_text("Произошла ошибка. Попробуйте снова.")
        return ConversationHandler.END

async def handle_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received photo, Chat ID: {update.effective_chat.id}")
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_data = await file.download_as_bytearray()
        logger.info(f"Image data size: {len(img_data)} bytes")
        try:
            img = Image.open(BytesIO(img_data))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"image_{timestamp}_{hash(update.message.message_id)}.png"
            file_path = os.path.join("images", file_name)
            os.makedirs("images", exist_ok=True)
            with open(file_path, "wb") as f:
                img.save(f, format="PNG")
            logger.info(f"Image saved at: {file_path}")
            if 'image_paths' not in context.user_data['announcement_data']:
                context.user_data['announcement_data']['image_paths'] = []
            context.user_data['announcement_data']['image_paths'].append(file_path)
            image_count = len(context.user_data['announcement_data']['image_paths'])
            # Сохранение текущего message_id перед очисткой
            current_message_id = update.message.message_id
            context.user_data['current_message_id'] = current_message_id
            # Удаление предыдущих сообщений, кроме текущего
            if 'message_ids' in context.user_data and context.user_data['message_ids']:
                for msg_id in context.user_data['message_ids']:
                    if msg_id != current_message_id:
                        try:
                            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                            logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
                context.user_data['message_ids'] = [current_message_id]
            keyboard = [
                [InlineKeyboardButton("Завершить с изображениями", callback_data="done_with_images")],
                [InlineKeyboardButton("Назад", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            await update.message.reply_text("Ошибка при обработке изображения. Попробуйте снова.")
            return ConversationHandler.END
    return STATE_CONFIRM_ADD

async def handle_done_no_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Completing without images. Query: {query}")
    await query.answer()
    category = context.user_data.get('current_category')
    announcement_data = context.user_data['announcement_data']
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    try:
        announcement_id = db.save_announcement(announcement_data['title'], announcement_data['text'], None, category)
        await query.message.edit_text(f"Объявление '{announcement_data['title']}' сохранено с ID {announcement_id}.")
    except Exception as e:
        logger.error(f"Error saving announcement: {e}")
        await query.message.edit_text("Ошибка при сохранении объявления. Попробуйте снова.")
        return ConversationHandler.END
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                logger.info(f"Deleted message with ID: {msg_id}")
            except Exception as e:
                logger.warning(f"Failed to delete message {msg_id}: {str(e)}")
    del context.user_data['announcement_data']
    del context.user_data['message_ids']
    await handle_back(update, context)
    return ConversationHandler.END

async def handle_done_with_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    image_count = len(context.user_data['announcement_data'].get('image_paths', []))
    logger.info(f"Completing with images. Query: {query}, Image count: {image_count}")
    await query.answer()
    category = context.user_data.get('current_category')
    announcement_data = context.user_data['announcement_data']
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    try:
        images_str = ",".join(announcement_data.get('image_paths', [])) if announcement_data.get('image_paths') else None
        logger.info(f"Image paths list: {images_str}")
        announcement_id = db.save_announcement(announcement_data['title'], announcement_data['text'], images_str, category)
        text = f"**{announcement_data['title']}**\n\n{announcement_data['text']}"
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['message_ids'] = []
        if image_count == 0:
            message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='Markdown', reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            logger.info(f"Sent text only, message ID: {message.message_id}")
        elif image_count == 1:
            with open(announcement_data['image_paths'][0], 'rb') as photo:
                message = await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=text, parse_mode='Markdown', reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            logger.info(f"Sent single photo, message ID: {message.message_id}")
        else:
            media = []
            for i, image_path in enumerate(announcement_data['image_paths']):
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as photo_file:
                        media.append(InputMediaPhoto(photo_file))
                    logger.info(f"Added image {i+1} to media group: {image_path}, size: {os.path.getsize(image_path)} bytes")
                else:
                    logger.warning(f"Image not found: {image_path}")
            if media:
                logger.info(f"Attempting to send media group with {len(media)} images")
                message = await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)
                if message and len(message) > 0:
                    context.user_data['message_ids'] = [msg.message_id for msg in message]
                    logger.info(f"Media group sent successfully, all message IDs: {context.user_data['message_ids']}")
                    await asyncio.sleep(2)  # Увеличенная задержка для обработки медиа-группы
                    final_message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='Markdown', reply_markup=reply_markup)
                    context.user_data['message_ids'].append(final_message.message_id)
                    logger.info(f"Sent text message, ID: {final_message.message_id}")
                else:
                    logger.error("Media group failed unexpectedly, falling back to individual photos")
                    for i, image_path in enumerate(announcement_data['image_paths']):
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as photo:
                                photo_msg = await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo)
                                context.user_data['message_ids'].append(photo_msg.message_id)
                                logger.info(f"Fallback: Sent photo {i+1}, message ID: {photo_msg.message_id}")
                    final_message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='Markdown', reply_markup=reply_markup)
                    context.user_data['message_ids'].append(final_message.message_id)
                    logger.info(f"Fallback: Sent text message, ID: {final_message.message_id}")
            else:
                message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='Markdown', reply_markup=reply_markup)
                context.user_data['message_ids'] = [message.message_id]
                logger.info(f"No valid images, sent text only, message ID: {message.message_id}")
        await query.message.edit_text(f"Объявление '{announcement_data['title']}' с {image_count} изображениями сохранено с ID {announcement_id}.")
        await asyncio.sleep(2)  # Задержка перед удалением
        if 'message_ids' in context.user_data and context.user_data['message_ids']:
            for msg_id in context.user_data['message_ids']:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Deleted message with ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete message {msg_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error saving announcement with images: {str(e)}")
        await query.message.edit_text(f"Ошибка при сохранении объявления: {str(e)}. Попробуйте снова.")
        return ConversationHandler.END
    del context.user_data['announcement_data']
    del context.user_data['message_ids']
    await start(update, context)
    return ConversationHandler.END

# Функции для удаления
async def handle_delete_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Activating deletion. Query: {query}, User: {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return ConversationHandler.END
    category = context.user_data.get('current_category')
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    if category:
        announcements = db.get_announcements(category)
        if announcements:
            keyboard = []
            for ann_id, title, _, _, _, _ in announcements:
                keyboard.append([InlineKeyboardButton(f"Удалить {title}", callback_data=f"delete_ann_confirm_{ann_id}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"Выберите объявление для удаления в категории '{category_map.get(category)}':",
                                                    reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return STATE_DELETE_CONFIRMATION
        else:
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"В категории '{category_map.get(category)}' нет объявлений для удаления.", reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return ConversationHandler.END
    return ConversationHandler.END

async def handle_delete_ann_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Confirming deletion. Query: {query.data}, User: {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return ConversationHandler.END
    ann_id = int(query.data.replace("delete_ann_confirm_", ""))
    category = context.user_data.get('current_category')
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    if category:
        try:
            announcement = db.get_announcement(ann_id)
            if announcement:
                _, _, images_str, _ = announcement
                image_paths = images_str.split(",") if images_str else []
                for image_path in image_paths:
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                            logger.info(f"Deleted image file: {image_path}")
                        except Exception as e:
                            logger.error(f"Error deleting file {image_path}: {str(e)}")
                    else:
                        logger.warning(f"Image file not found: {image_path}")
            if db.delete_announcement(ann_id):
                message = await query.message.edit_text(f"Объявление с ID {ann_id} удалено из категории '{category_map.get(category)}'.")
                context.user_data['message_ids'] = [message.message_id]
                logger.info(f"Announcement with ID {ann_id} successfully deleted")
            else:
                message = await query.message.edit_text(f"Объявление с ID {ann_id} не найдено.")
                context.user_data['message_ids'] = [message.message_id]
            await start(update, context)
        except Exception as e:
            logging.error(f"Error deleting announcement with ID {ann_id}: {e}")
            await query.message.edit_text(f"Ошибка при удалении объявления с ID {ann_id}: {str(e)}")
    return ConversationHandler.END

async def handle_edit_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Activating edit. Query: {query}, User: {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return ConversationHandler.END
    category = context.user_data.get('current_category')
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    if category:
        announcements = db.get_announcements(category)
        if announcements:
            keyboard = []
            for ann_id, title, _, _, _, _ in announcements:
                keyboard.append([InlineKeyboardButton(f"Редактировать {title}", callback_data=f"edit_ann_select_{ann_id}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"Выберите объявление для редактирования в категории '{category_map.get(category)}':",
                                                    reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return STATE_EDIT_ANNOUNCEMENT
        else:
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await query.message.edit_text(f"В категории '{category_map.get(category)}' нет объявлений для редактирования.", reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            return ConversationHandler.END
    return ConversationHandler.END

async def handle_edit_ann_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Selecting announcement for edit. Query: {query.data}, User: {user_id}")
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.message.edit_text("У вас нет прав для выполнения этой операции.")
        return ConversationHandler.END
    ann_id = int(query.data.replace("edit_ann_select_", ""))
    context.user_data['editing_ann_id'] = ann_id
    announcement = db.get_announcement(ann_id)
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    if announcement:
        title, text, images_str, _ = announcement
        context.user_data['announcement_data'] = {
            'title': title,
            'text': text,
            'image_paths': images_str.split(',') if images_str else []
        }
        keyboard = [
            [InlineKeyboardButton("Редактировать заголовок", callback_data="edit_title")],
            [InlineKeyboardButton("Редактировать текст", callback_data="edit_text")],
            [InlineKeyboardButton("Редактировать изображения", callback_data="edit_images")],
            [InlineKeyboardButton("Сохранить изменения", callback_data="save_edit")],
            [InlineKeyboardButton("Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await query.message.edit_text(f"Редактирование объявления '{title}'\nВыберите действие:", reply_markup=reply_markup)
        context.user_data['message_ids'] = [message.message_id]
        return STATE_EDIT_ANNOUNCEMENT
    else:
        await query.message.edit_text("Объявление не найдено.")
        return ConversationHandler.END

async def handle_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Editing title. Query: {query}")
    await query.answer()
    current_title = context.user_data['announcement_data'].get('title', '')
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.edit_text(f"Текущий заголовок:\n\n{current_title}\n\nВведите новый заголовок или отредактируйте текущий:",
                                            reply_markup=reply_markup)
    context.user_data['message_ids'] = [message.message_id]
    return STATE_EDIT_TITLE

async def handle_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Editing text. Query: {query}")
    await query.answer()
    current_text = context.user_data['announcement_data'].get('text', '')
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.edit_text(f"Текущий текст:\n\n{current_text}\n\nВведите новый текст или отредактируйте текущий:",
                                            reply_markup=reply_markup)
    context.user_data['message_ids'] = [message.message_id]
    return STATE_EDIT_TEXT

async def handle_edit_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Editing images. Query: {query}")
    await query.answer()
    if 'announcement_data' not in context.user_data or 'image_paths' not in context.user_data['announcement_data']:
        await query.message.edit_text("Данные изображений не найдены.")
        return ConversationHandler.END
    current_images = context.user_data['announcement_data']['image_paths']
    message_text = "Текущие изображения:\n"
    if current_images:
        for i, image_path in enumerate(current_images, 1):
            if os.path.exists(image_path):
                message_text += f"{i}. {os.path.basename(image_path)}\n"
            else:
                message_text += f"{i}. (Файл не найден: {os.path.basename(image_path)})\n"
    else:
        message_text += "Нет изображений.\n"
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = []
    if current_images:
        for i, _ in enumerate(current_images):
            keyboard.append([InlineKeyboardButton(f"Удалить изображение {i+1}", callback_data=f"remove_image_{i}")])
    keyboard.extend([
        [InlineKeyboardButton("Добавить новое изображение", callback_data="start_add_new_image")],
        [InlineKeyboardButton("Завершить редактирование изображений", callback_data="save_edit_images")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.edit_text(message_text + "\nВыберите действие с изображениями. Отправьте новые изображения или удалите существующие:", reply_markup=reply_markup)
    context.user_data['message_ids'] = [message.message_id]
    return STATE_EDIT_IMAGES

async def handle_remove_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Removing image. Query: {query.data}")
    await query.answer()
    if 'announcement_data' not in context.user_data or 'image_paths' not in context.user_data['announcement_data']:
        await query.message.edit_text("Данные изображений не найдены.")
        return ConversationHandler.END
    index = int(query.data.replace("remove_image_", ""))
    current_images = context.user_data['announcement_data']['image_paths']
    if 0 <= index < len(current_images):
        removed_image = current_images.pop(index)
        if os.path.exists(removed_image):
            try:
                os.remove(removed_image)
                logger.info(f"Deleted image file: {removed_image}")
            except Exception as e:
                logger.error(f"Error deleting file {removed_image}: {str(e)}")
        else:
            logger.warning(f"Image file not found: {removed_image}")
    await handle_edit_images(update, context)
    return STATE_EDIT_IMAGES

async def start_add_new_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Starting new image addition. Query: {query}")
    await query.answer()
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Завершить добавление изображений", callback_data="save_edit_images")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.edit_text("Отправьте новое изображение. Нажмите 'Завершить добавление изображений', когда закончите.", reply_markup=reply_markup)
    context.user_data['message_ids'] = [message.message_id]
    return STATE_EDIT_IMAGES

async def handle_add_new_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Adding new image. Chat ID: {update.effective_chat.id}")
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_data = await file.download_as_bytearray()
        logger.info(f"Image data size: {len(img_data)} bytes")
        try:
            img = Image.open(BytesIO(img_data))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"image_{timestamp}_{hash(update.message.message_id)}.png"
            file_path = os.path.join("images", file_name)
            os.makedirs("images", exist_ok=True)
            with open(file_path, "wb") as f:
                img.save(f, format="PNG")
            logger.info(f"Image saved at: {file_path}")
            if 'image_paths' not in context.user_data['announcement_data']:
                context.user_data['announcement_data']['image_paths'] = []
            context.user_data['announcement_data']['image_paths'].append(file_path)
            image_count = len(context.user_data['announcement_data']['image_paths'])
            # Сохранение текущего message_id перед очисткой
            current_message_id = update.message.message_id
            context.user_data['current_message_id'] = current_message_id
            # Удаление предыдущих сообщений, кроме текущего
            if 'message_ids' in context.user_data and context.user_data['message_ids']:
                for msg_id in context.user_data['message_ids']:
                    if msg_id != current_message_id:
                        try:
                            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                            logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
                context.user_data['message_ids'] = [current_message_id]
            keyboard = [
                [InlineKeyboardButton("Завершить добавление изображений", callback_data="save_edit_images")],
                [InlineKeyboardButton("Назад", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            await update.message.reply_text("Ошибка при обработке изображения. Попробуйте снова.")
    return STATE_EDIT_IMAGES

async def handle_save_edit_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Saving image edits. Query: {query}")
    await query.answer()
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Редактировать заголовок", callback_data="edit_title")],
        [InlineKeyboardButton("Редактировать текст", callback_data="edit_text")],
        [InlineKeyboardButton("Редактировать изображения", callback_data="edit_images")],
        [InlineKeyboardButton("Сохранить изменения", callback_data="save_edit")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await query.message.edit_text(f"Редактирование объявления\nВыберите действие:", reply_markup=reply_markup)
    context.user_data['message_ids'] = [message.message_id]
    return STATE_EDIT_ANNOUNCEMENT

async def handle_save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Saving edits. Query: {query}")
    await query.answer()
    ann_id = context.user_data.get('editing_ann_id')
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    if ann_id and 'announcement_data' in context.user_data:
        announcement_data = context.user_data['announcement_data']
        images_str = ",".join(announcement_data.get('image_paths', [])) if announcement_data.get('image_paths') else None
        if db.update_announcement(ann_id, announcement_data['title'], announcement_data['text'], images_str):
            image_count = len(announcement_data.get('image_paths', []))
            # Экранируем текст для безопасной отправки в MarkdownV2
            safe_title = escape_markdown(announcement_data['title'], version=2)
            safe_text = escape_markdown(announcement_data['text'], version=2) if announcement_data['text'] else ""
            text = f"**{safe_title}**\n\n{safe_text}"
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                if image_count == 0:
                    message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                    context.user_data['message_ids'] = [message.message_id]
                    logger.info(f"Sent edited announcement without images, message ID: {message.message_id}")
                elif image_count == 1:
                    image_path = announcement_data['image_paths'][0]
                    if os.path.exists(image_path):
                        with open(image_path, 'rb') as photo:
                            message = await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                        context.user_data['message_ids'] = [message.message_id]
                        logger.info(f"Sent edited announcement with photo, message ID: {message.message_id}")
                    else:
                        logger.error(f"Image not found: {image_path}")
                        message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                        context.user_data['message_ids'] = [message.message_id]
                        logger.info(f"Fallback to text only, message ID: {message.message_id}")
                else:
                    media = []
                    for image_path in announcement_data['image_paths']:
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as photo_file:
                                media.append(InputMediaPhoto(photo_file))
                            logger.info(f"Added image to media group: {image_path}")
                        else:
                            logger.warning(f"Image not found: {image_path}")
                    if media:
                        logger.info(f"Sending media group with {len(media)} images")
                        message = await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)
                        if message and len(message) > 0:
                            context.user_data['message_ids'] = [msg.message_id for msg in message]
                            logger.info(f"Saved media group message IDs: {context.user_data['message_ids']}")
                            final_message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                            context.user_data['message_ids'].append(final_message.message_id)
                            logger.info(f"Sent text message, ID: {final_message.message_id}")
                        else:
                            logger.error("Failed to send media group, falling back to text only")
                            message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                            context.user_data['message_ids'] = [message.message_id]
                    else:
                        message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                        context.user_data['message_ids'] = [message.message_id]
                        logger.info(f"No valid images, sent text only, message ID: {message.message_id}")
                await query.message.edit_text(f"Объявление с ID {ann_id} успешно обновлено.")
            except Exception as e:
                logger.error(f"Error saving edited announcement: {e}")
                await query.message.edit_text(f"Ошибка при обновлении объявления с ID {ann_id}: {str(e)}")
        else:
            message = await query.message.edit_text(f"Ошибка при обновлении объявления с ID {ann_id}.")
            context.user_data['message_ids'] = [message.message_id]
    else:
        message = await query.message.edit_text("Данные для редактирования не найдены.")
        context.user_data['message_ids'] = [message.message_id]
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                logger.info(f"Deleted message with ID: {msg_id}")
            except Exception as e:
                logger.warning(f"Failed to delete message {msg_id}: {str(e)}")
    del context.user_data['announcement_data']
    del context.user_data['editing_ann_id']
    await handle_back(update, context)
    return ConversationHandler.END

async def handle_cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Canceling edit. Query: {query}")
    await query.answer()
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Deleted message with ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete message {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    # Очищаем данные
    message = await query.message.edit_text("Редактирование отменено.")
    context.user_data['message_ids'] = [message.message_id]
    if 'announcement_data' in context.user_data:
        del context.user_data['announcement_data']
    if 'editing_ann_id' in context.user_data:
        del context.user_data['editing_ann_id']
    await handle_back(update, context)
    return ConversationHandler.END

async def handle_view_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Handling announcement view: {query.data}")
    await query.answer()
    # Сохранение текущего message_id перед очисткой
    current_message_id = query.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущего сообщения с запросом (список объявлений)
    try:
        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=current_message_id)
        logger.info(f"Deleted original message with ID: {current_message_id}")
    except Exception as e:
        logger.warning(f"Failed to delete original message {current_message_id}: {str(e)}")
    # Удаление других предыдущих сообщений, если есть
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
                    logger.info(f"Deleted previous message with ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete message {msg_id}: {str(e)}")
        context.user_data['message_ids'] = []
    ann_id = int(query.data.replace("view_announcement_", ""))
    logger.info(f"Extracted announcement ID: {ann_id}")
    announcement = db.get_announcement(ann_id)
    if announcement is None:
        logger.warning(f"No announcement found for ID: {ann_id}")
        await query.message.reply_text("Объявление не найдено.")
        return
    logger.info(f"Announcement retrieved: {announcement}")
    title, text, images_str, category = announcement
    image_paths = [path.strip() for path in (images_str.split(",") if images_str else [])]
    image_count = len(image_paths)
    logger.info(f"Image count: {image_count}, Paths: {image_paths}")

    # Экранируем текст для безопасной отправки в MarkdownV2
    safe_title = escape_markdown(title, version=2)
    safe_text = escape_markdown(text, version=2) if text else ""
    text = f"**{safe_title}**\n\n{safe_text}"
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if image_count == 0:
            message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
            context.user_data['message_ids'] = [message.message_id]
            logger.info(f"Sent text only, message ID: {message.message_id}")
        elif image_count == 1:
            image_path = image_paths[0]
            if os.path.exists(image_path):
                with open(image_path, 'rb') as photo:
                    message = await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                context.user_data['message_ids'] = [message.message_id]
                logger.info(f"Sent single photo, message ID: {message.message_id}")
            else:
                logger.error(f"Image not found: {image_path}")
                message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                context.user_data['message_ids'] = [message.message_id]
                logger.info(f"Fallback to text only, message ID: {message.message_id}")
        else:
            media = []
            for i, image_path in enumerate(image_paths):
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as photo_file:
                        media.append(InputMediaPhoto(photo_file))
                    logger.info(f"Added image {i+1} to media group: {image_path}, size: {os.path.getsize(image_path)} bytes")
                else:
                    logger.warning(f"Image not found: {image_path}")
            if media:
                logger.info(f"Attempting to send media group with {len(media)} images")
                message = await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)
                if message and len(message) > 0:
                    context.user_data['message_ids'] = [msg.message_id for msg in message]
                    logger.info(f"Media group sent successfully, all message IDs: {context.user_data['message_ids']}")
                    await asyncio.sleep(2)  # Увеличенная задержка для обработки медиа-группы
                    final_message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                    context.user_data['message_ids'].append(final_message.message_id)
                    logger.info(f"Sent text message, ID: {final_message.message_id}")
                else:
                    logger.error("Media group failed unexpectedly, falling back to individual photos")
                    for i, image_path in enumerate(image_paths):
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as photo:
                                photo_msg = await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo)
                                context.user_data['message_ids'].append(photo_msg.message_id)
                                logger.info(f"Fallback: Sent photo {i+1}, message ID: {photo_msg.message_id}")
                    final_message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                    context.user_data['message_ids'].append(final_message.message_id)
                    logger.info(f"Fallback: Sent text message, ID: {final_message.message_id}")
            else:
                message = await context.bot.send_message(chat_id=query.message.chat_id, text=text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                context.user_data['message_ids'] = [message.message_id]
                logger.info(f"No valid images, sent text only, message ID: {message.message_id}")
    except Exception as e:
        logger.error(f"Error viewing announcement: {e}")
        await query.message.reply_text("Ошибка при отображении объявления.")
    return

async def handle_title_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    context.user_data['announcement_data']['title'] = user_text
    logger.info(f"New title: {user_text}")
    # Сохранение текущего message_id перед очисткой
    current_message_id = update.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Редактировать заголовок", callback_data="edit_title")],
        [InlineKeyboardButton("Редактировать текст", callback_data="edit_text")],
        [InlineKeyboardButton("Редактировать изображения", callback_data="edit_images")],
        [InlineKeyboardButton("Сохранить изменения", callback_data="save_edit")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Заголовок обновлен. Выберите следующее действие:", reply_markup=reply_markup)
    return STATE_EDIT_ANNOUNCEMENT

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    context.user_data['announcement_data']['text'] = user_text
    logger.info(f"New text: {user_text[:50]}...")
    # Сохранение текущего message_id перед очисткой
    current_message_id = update.message.message_id
    context.user_data['current_message_id'] = current_message_id
    # Удаление предыдущих сообщений, кроме текущего
    if 'message_ids' in context.user_data and context.user_data['message_ids']:
        for msg_id in context.user_data['message_ids']:
            if msg_id != current_message_id:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                    logger.info(f"Удалено старое сообщение с ID: {msg_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {msg_id}: {str(e)}")
        context.user_data['message_ids'] = [current_message_id]
    keyboard = [
        [InlineKeyboardButton("Редактировать заголовок", callback_data="edit_title")],
        [InlineKeyboardButton("Редактировать текст", callback_data="edit_text")],
        [InlineKeyboardButton("Редактировать изображения", callback_data="edit_images")],
        [InlineKeyboardButton("Сохранить изменения", callback_data="save_edit")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Текст обновлен. Выберите следующее действие:", reply_markup=reply_markup)
    return STATE_EDIT_ANNOUNCEMENT

def announcement_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_announcement_action, pattern="^delete_announcement$|^edit_announcement$|^add_announcement$")],
        states={
            STATE_WAITING_FOR_ACTION: [],
            STATE_WAITING_FOR_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_WAITING_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_WAITING_FOR_IMAGES: [
                CallbackQueryHandler(handle_add_images, pattern="^add_images$"),
                CallbackQueryHandler(handle_done_no_images, pattern="^done_no_images$"),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_CONFIRM_ADD: [
                MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_images),
                CallbackQueryHandler(handle_done_with_images, pattern="^done_with_images$"),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_DELETE_CONFIRMATION: [
                CallbackQueryHandler(handle_delete_ann_confirm, pattern="^delete_ann_confirm_"),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_EDIT_ANNOUNCEMENT: [
                CallbackQueryHandler(handle_edit_title, pattern="^edit_title$"),
                CallbackQueryHandler(handle_edit_text, pattern="^edit_text$"),
                CallbackQueryHandler(handle_edit_images, pattern="^edit_images$"),
                CallbackQueryHandler(handle_save_edit, pattern="^save_edit$"),
                CallbackQueryHandler(handle_edit_ann_select, pattern="^edit_ann_select_"),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_EDIT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_input),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_EDIT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$")
            ],
            STATE_EDIT_IMAGES: [
                CallbackQueryHandler(handle_remove_image, pattern="^remove_image_"),
                CallbackQueryHandler(start_add_new_image, pattern="^start_add_new_image$"),
                CallbackQueryHandler(handle_save_edit_images, pattern="^save_edit_images$"),
                CallbackQueryHandler(handle_cancel_edit, pattern="^back$"),
                MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_add_new_image)
            ]
        },
        fallbacks=[CallbackQueryHandler(handle_back, pattern="^back_to_main$")],
        allow_reentry=True
    )