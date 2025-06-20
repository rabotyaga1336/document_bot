import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from handlers.announcement_handlers import announcement_conversation_handler, handle_view_announcement
from handlers.document_handlers import document_conversation_handler
from handlers.link_handlers import link_conversation_handler
from handlers.menu_handlers import start
from config import TOKEN


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CallbackQueryHandler(handle_view_announcement, pattern="^view_announcement_"))  # Выше всех
    application.add_handler(CommandHandler("start", start))
    application.add_handler(document_conversation_handler())
    application.add_handler(link_conversation_handler())
    application.add_handler(announcement_conversation_handler())
    try:
        logging.info("Запуск бота...")
        application.run_polling()
    except Exception as e:
        logging.error(f"Фатальная ошибка в основном цикле: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()