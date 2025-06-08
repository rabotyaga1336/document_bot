import logging
from telegram import BotCommand
from telegram.ext import Application
from config import TOKEN
from handlers import register_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Инициализация бота
def main():
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
    register_handlers(application)

    # Устанавливаем только команду /start
    commands = [
        BotCommand(command="/start", description="Запустить бота")
    ]
    application.bot.set_my_commands(commands)

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()