import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import requests
import json
from datetime import time
import pytz

# Настройки
BOT_TOKEN = "8141615617:AAEBJ86u9rx0g1peCutLwWkL2gA1nw3QVL4"
ESP_IP = "http://192.168.1.100"  # Заменить на IP ESP
ESP_PORT = "80"  # Порт ESP
ESP_ENDPOINTS = {
    "moisture": "/moisture",
    "light": "/light",
    "pump": "/pump",
    "status": "/status",
    "schedule": "/schedule"
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PlantMonitorBot:
    def __init__(self):
        self.base_url = f"{ESP_IP}:{ESP_PORT}"
        self.authorized_users = set() 
        self.default_password = "plant123"

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отправляет приветственное сообщение при команде /start"""
        user = update.effective_user
        welcome_text = (
            f"Привет, {user.first_name}!\n\n"
            "Я бот для управления системой полива растений.\n"
            "Используйте /help чтобы увидеть список доступных команд.\n\n"
            "Для начала работы необходимо авторизоваться с помощью команды /auth."
        )
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отправляет сообщение с доступными командами"""
        help_text = (
            "Доступные команды:\n\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать это сообщение\n"
            "/auth - Авторизоваться в системе\n"
            "/status - Текущее состояние системы\n"
            "/moisture - Текущая влажность почвы\n"
            "/light - Текущий уровень освещенности\n"
            "/pump_on - Включить насос\n"
            "/pump_off - Выключить насос\n"
            "/pump_time - Включить насос на N секунд\n"
            "/set_schedule - Установить расписание полива\n"
            "/get_schedule - Показать текущее расписание\n"
            "/cancel_schedule - Отменить расписание полива\n"
        )
        await update.message.reply_text(help_text)

    async def auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик авторизации"""
        if update.effective_user.id in self.authorized_users:
            await update.message.reply_text("Вы уже авторизованы!")
            return
        
        if context.args and context.args[0] == self.default_password:
            self.authorized_users.add(update.effective_user.id)
            await update.message.reply_text("Авторизация успешна! Теперь вы можете управлять системой.")
        else:
            await update.message.reply_text(
                "Пожалуйста, введите пароль после команды /auth.\n"
                "Пример: /auth plant123"
            )

    def check_auth(self, user_id: int) -> bool:
        """Проверяет авторизацию пользователя"""
        return user_id in self.authorized_users

    async def send_esp_request(self, endpoint: str, params: dict = None) -> dict:
        """Отправляет запрос к ESP и возвращает ответ"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к ESP: {e}")
            return {"error": str(e)}

    async def get_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Получает и отображает статус системы"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["status"])
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        status_text = (
            "📊 Статус системы:\n\n"
            f"💧 Влажность почвы: {data.get('moisture', 'N/A')}%\n"
            f"☀️ Уровень освещенности: {data.get('light', 'N/A')} lux\n"
            f"🚿 Состояние насоса: {'ВКЛ' if data.get('pump_status', False) else 'ВЫКЛ'}\n"
            f"⏰ Расписание: {'Активно' if data.get('schedule_active', False) else 'Не активно'}\n"
            f"🕒 Время полива: {data.get('schedule_time', 'Не установлено')}\n"
            f"📅 Последний полив: {data.get('last_watered', 'Не доступно')}"
            )
        await update.message.reply_text(status_text)

    async def get_moisture(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Получает текущую влажность почвы"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["moisture"])
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        moisture = data.get("moisture", "N/A")
        await update.message.reply_text(f"💧 Текущая влажность почвы: {moisture}%")

    async def get_light(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Получает текущий уровень освещенности"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["light"])
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        light = data.get("light", "N/A")
        await update.message.reply_text(f"☀️ Текущий уровень освещенности: {light} lux")

    async def pump_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Включает насос"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["pump"], {"state": "on"})
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        await update.message.reply_text("🚿 Насос включен!")

    async def pump_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Выключает насос"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["pump"], {"state": "off"})
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        await update.message.reply_text("🚿 Насос выключен!")

    async def pump_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Включает насос на указанное время"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Пожалуйста, укажите время работы насоса в секундах.\nПример: /pump_time 10")
            return
        
        seconds = int(context.args[0])
        data = await self.send_esp_request(ESP_ENDPOINTS["pump"], {"state": "time", "time": seconds})
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        await update.message.reply_text(f"🚿 Насос включен на {seconds} секунд!")

    async def set_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Устанавливает расписание полива"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Пожалуйста, укажите время полива и интервал.\n"
                "Формат: /set_schedule HH:MM интервал_в_часах\n"
                "Пример: /set_schedule 08:00 24 (полив каждый день в 8 утра)"
            )
            return
        
        time_str = context.args[0]
        interval = context.args[1]
        
        try:
            # Проверка времени
            hours, minutes = map(int, time_str.split(':'))
            if not (0 <= hours < 24 and 0 <= minutes < 60):
                raise ValueError
        except ValueError:
            await update.message.reply_text("Неверный формат времени. Используйте HH:MM, например 08:00")
            return
        
        if not interval.isdigit():
            await update.message.reply_text("Интервал должен быть числом (часы)")
            return
        
        data = await self.send_esp_request(
            ESP_ENDPOINTS["schedule"],
            {"action": "set", "time": time_str, "interval": interval}
        )
        
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        await update.message.reply_text(
            f"⏰ Расписание установлено!\n"
            f"Время полива: {time_str}\n"
            f"Интервал: каждые {interval} часов"
        )

    async def get_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает текущее расписание полива"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["schedule"], {"action": "get"})
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        if data.get("active", False):
            schedule_text = (
                "⏰ Текущее расписание:\n\n"
                f"🕒 Время полива: {data.get('time', 'N/A')}\n"
                f"🔄 Интервал: каждые {data.get('interval', 'N/A')} часов\n"
                f"📅 Следующий полив: {data.get('next_watering', 'N/A')}"
            )
        else:
            schedule_text = "Расписание полива не установлено."
        
        await update.message.reply_text(schedule_text)

    async def cancel_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отменяет расписание полива"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        data = await self.send_esp_request(ESP_ENDPOINTS["schedule"], {"action": "cancel"})
        if "error" in data:
            await update.message.reply_text(f"Ошибка: {data['error']}")
            return
        
        await update.message.reply_text("⏰ Расписание полива отменено!")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "status":
            await self.get_system_status(update, context)
        elif query.data == "moisture":
            await self.get_moisture(update, context)
        elif query.data == "light":
            await self.get_light(update, context)
        elif query.data == "pump_on":
            await self.pump_on(update, context)
        elif query.data == "pump_off":
            await self.pump_off(update, context)

    async def show_control_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает панель управления с кнопками"""
        if not self.check_auth(update.effective_user.id):
            await update.message.reply_text("Ошибка: Вы не авторизованы!")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Статус", callback_data="status"),
                InlineKeyboardButton("💧 Влажность", callback_data="moisture"),
                InlineKeyboardButton("☀️ Освещенность", callback_data="light"),
            ],
            [
                InlineKeyboardButton("🚿 Вкл насос", callback_data="pump_on"),
                InlineKeyboardButton("🚿 Выкл насос", callback_data="pump_off"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Панель управления:", reply_markup=reply_markup)

def main() -> None:
    """Запуск бота."""
    bot = PlantMonitorBot()
    
    # Создаем Application и передаем ему токен бота
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("auth", bot.auth))
    application.add_handler(CommandHandler("status", bot.get_system_status))
    application.add_handler(CommandHandler("moisture", bot.get_moisture))
    application.add_handler(CommandHandler("light", bot.get_light))
    application.add_handler(CommandHandler("pump_on", bot.pump_on))
    application.add_handler(CommandHandler("pump_off", bot.pump_off))
    application.add_handler(CommandHandler("pump_time", bot.pump_time))
    application.add_handler(CommandHandler("set_schedule", bot.set_schedule))
    application.add_handler(CommandHandler("get_schedule", bot.get_schedule))
    application.add_handler(CommandHandler("cancel_schedule", bot.cancel_schedule))
    application.add_handler(CommandHandler("panel", bot.show_control_panel))
    
    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()