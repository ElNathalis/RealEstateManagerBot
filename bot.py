# Основные импорты
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler,
)
import os
import logging
import json
from dotenv import load_dotenv
from collections import defaultdict
from pathlib import Path
import sys
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram import BotCommand, BotCommandScopeDefault, MenuButtonCommands
import random

# Кастомные модули
from llm_integration import generate_yandexgpt_response
from utils import *
from contact_manager import contact_manager

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создаем обработчик для консоли
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(console_formatter)

# Создаем обработчик для файла
file_handler = logging.FileHandler("bot.log", mode="w")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)

# Добавляем обработчики к логгеру
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Проверка наличия токена
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("Переменная окружения TELEGRAM_TOKEN не установлена!")
    exit(1)

# Глобальная база данных
database = None
all_objects_summary = None

SYSTEM_PROMPT = """
Ты - эксперт по недвижимости с доступом к базе данных. Твои правила:
0. Будь дружелюбным и разговорчивым. Старайся отвечать развернута, хотя бы 2 предложениями (за исключением ответа "У меня нет данных по этому вопросу")
1. Отвечай ТОЛЬКО на основе предоставленного КОНТЕКСТА и ВСЕЙ БАЗЫ ОБЪЕКТОВ
2. Если информации нет - говори "У меня нет данных по этому вопросу"
3. Для сравнения объектов используй данные из контекста
4. Для общих вопросов используй всю базу объектов
5. Сбор контактов:
   - Предлагай только после того, как помог клиенту. Не здоровайся, когда собираешь контакт, если это не первое сообщение в чате!
   - Используй естественные фразы: 
        "Если хотите, могу прислать подборку вариантов - оставьте телефон для связи"
        "Если возникнут вопросы - оставьте контакты, я свяжусь с вами"
        "Могу записать вас на просмотр - как вас зовут и на какой номер перезвонить?"
        "Если хотите, могу прислать подробную презентацию - оставьте телефон?"
   - Если имя уже известно, уточни имя и запрашивай только телефон
    - После запроса контактов УСТАНАВЛИВАЙ ФЛАГ collecting_contacts
   - Если имя неизвестно, вежливо попроси имя и телефон
   - Никогда не настаивай
   - не пиши пользователю о том, что был установлен флаг collecting_contacts
    - ПРЕДЛАГАЙ ТОЛЬКО ОДИН РАЗ за сессию
   - ЕСЛИ КОНТАКТ УЖЕ СОХРАНЕН (contact_saved=True) - НЕ ПРЕДЛАГАЙ СНОВА
   - После сохранения контакта ПЕРЕСТАНЬ УПОМИНАТЬ ЭТУ ТЕМУ
   - Переключайся на другие темы: подбор объектов, сравнение, общая информация
6. Будь дружелюбным, полезным и разговорчивым
7. Поддерживай диалог, задавай уточняющие вопросы
8. Форматирование ответов:
   - НЕ ИСПОЛЬЗУЙ markdown (**жирный**, __курсив__)
   - Пиши простым, понятным языком
   - Разбивай длинные ответы на абзацы, при этом не пиши слова "заключение", "введение" и т.д.
9. Обращайся к клиенту по имени, если оно известно: {user_name}
10. НИКОГДА не придумывай реплики за пользователя. Отвечай только от своего лица.
11. НЕ ПРЕДПОЛАГАЙ ответы пользователя. Задавай вопросы и жди реального ответа.
"""


def load_database():
    """Загрузка базы данных из JSON-файла"""
    global database
    try:
        # Определяем путь к файлу базы данных
        current_dir = Path(__file__).resolve().parent
        db_path = current_dir / "data" / "database.json"

        logger.info(f"Попытка загрузки базы данных из: {db_path}")

        if not db_path.exists():
            logger.error(f"Файл базы данных не найден: {db_path}")
            return None

        with open(db_path, "r", encoding="utf-8") as f:
            database = json.load(f)
            logger.info(f"База данных загружена. Объектов: {len(database)}")
            return database

    except json.JSONDecodeError as e:
        logger.exception("Ошибка декодирования JSON в базе данных")
        return None
    except Exception as e:
        logger.exception(f"Критическая ошибка загрузки базы данных: {e}")
        return None


# Загрузка базы данных при старте
load_database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.message.from_user
    logger.info(f"Пользователь {user.id} запустил бота")

    # Путь к изображению
    current_dir = Path(__file__).parent
    image_path = current_dir / "images" / "logo.jpg"

    # Формируем текст сообщения
    welcome_text = (
        "🏠 Добро пожаловать в бот компании СтройИнвест!\n"
        "Я помогу вам подобрать идеальное жилье и ответить на все вопросы.\n\n"
        "Нажмите кнопку ниже, чтобы начать:"
    )

    # Проверяем существование изображения
    if image_path.exists():
        with open(image_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=ReplyKeyboardMarkup(
                    [["Начать общение"]], resize_keyboard=True, one_time_keyboard=True
                ),
            )
    else:
        logger.warning(f"Файл логотипа не найден: {image_path}")
        await update.message.reply_text(
            welcome_text,
            reply_markup=ReplyKeyboardMarkup(
                [["Начать общение"]], resize_keyboard=True, one_time_keyboard=True
            ),
        )

    # Сбрасываем состояние пользователя
    context.user_data.clear()


async def handle_first_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработка первого сообщения после старта"""
    await update.message.reply_text(
        "👋 Приятно познакомиться! Как я могу к вам обращаться?",
        reply_markup=ReplyKeyboardRemove(),
    )
    # Устанавливаем состояние ожидания имени
    context.user_data["expecting_name"] = True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.message.from_user.id
        user_text = update.message.text
        logger.info(f"Получено сообщение от {user_id}: {user_text}")

        # Проверка на команды, которые должны сбрасывать состояние
        reset_commands = ["/start", "/menu", "главное меню", "начать сначала"]
        if user_text.lower() in reset_commands:
            context.user_data.pop("collecting_contacts", None)
            await show_main_menu(update, context)
            return

        # Обработка ожидания имени
        if context.user_data.get("expecting_name"):
            # Извлекаем имя из сообщения
            extracted_name = extract_name(user_text)

            if len(extracted_name.split()) > 2:
                # Сохраняем извлеченное имя, но просим уточнить
                context.user_data["temp_name"] = extracted_name
                await update.message.reply_text(
                    f"Понял вас как '{extracted_name}'. Это ваше полное имя? "
                    "Можно просто имя, чтобы мне было удобнее обращаться 😊"
                )
                context.user_data["confirming_name"] = True
                return

            if context.user_data.get("confirming_name"):
                if user_text.lower() in ["да", "yes", "верно"]:
                    name = context.user_data["temp_name"]
                else:
                    name = extract_name(user_text)

                context.user_data["user_name"] = name
                context.user_data["confirming_name"] = False
                context.user_data["expecting_name"] = False
                logger.info(f"Пользователь {user_id} представился как: {name}")

                await update.message.reply_text(
                    f"Приятно познакомиться, {name}! 😊\n"
                    "Чем могу помочь? Можете спросить о наших жилых комплексах, "
                    "условиях покупки или попросить подобрать вариант."
                )
                # Показываем главное меню после знакомства
                await show_main_menu(update, context)
                return
            else:
                # Сохраняем имя пользователя
                context.user_data["user_name"] = extracted_name
                context.user_data["expecting_name"] = False
                logger.info(
                    f"Пользователь {user_id} представился как: {extracted_name}"
                )

                await update.message.reply_text(
                    f"Приятно познакомиться, {extracted_name}! 😊\n"
                    "Чем могу помочь? Можете спросить о наших жилых комплексах, "
                    "условиях покупки или попросить подобрать вариант."
                )
                # Показываем главное меню после знакомства
                await show_main_menu(update, context)
                return

        # Обработка ожидания сравнения объектов
        if context.user_data.get("awaiting_comparison"):
            try:
                # Разделяем введенные названия по запятой
                complexes = [
                    name.strip() for name in user_text.split(",") if name.strip()
                ]

                if not complexes:
                    await update.message.reply_text(
                        "Вы не указали названия ЖК. Пожалуйста, попробуйте снова."
                    )
                    return

                # Получаем результат сравнения
                comparison_result = compare_complexes(complexes, database)

                # Отправляем результат
                await update.message.reply_text(comparison_result)

                # Предлагаем дополнительные действия
                await update.message.reply_text(
                    "Хотите узнать подробнее о каком-то из ЖК? Или может быть записаться на просмотр?",
                    reply_markup=ReplyKeyboardMarkup(
                        [
                            ["Подробнее о ЖК", "Записаться на просмотр"],
                            ["Главное меню"],
                        ],
                        resize_keyboard=True,
                    ),
                )

            except Exception as e:
                logger.exception(f"Ошибка при сравнении ЖК: {e}")
                await update.message.reply_text(
                    "Произошла непредвиденная ошибка при сравнении объектов. "
                    "Попробуйте позже или свяжитесь с нашим менеджером."
                )
            finally:
                context.user_data["awaiting_comparison"] = False
            return

        # Обработка сбора контактов
        if context.user_data.get("collecting_contacts"):
            # Извлекаем имя и телефон из сообщения
            contact_info = extract_contact_info(user_text)

            if contact_info:
                name, phone = contact_info
                logger.info(f"Извлечен контакт: {name}, {phone}")

                # Формируем контекст диалога
                dialog_context = " | ".join(
                    [msg["text"] for msg in context.user_data.get("history", [])[-3:]]
                )
                logger.info(f"Контекст диалога: {dialog_context}")

                # Сохраняем контакт
                if contact_manager.save_contact(
                    user_id=user_id, name=name, phone=phone, context=dialog_context
                ):
                    logger.info("Контакт успешно сохранен в системе")

                    # ОЧИЩАЕМ СОСТОЯНИЕ СБОРА КОНТАКТОВ
                    context.user_data["collecting_contacts"] = False

                    # Устанавливаем флаг, что контакт уже сохранен
                    context.user_data["contact_saved"] = True
                    context.user_data["collecting_contacts"] = False

                    # Очищаем историю от предыдущих запросов контактов
                    clean_history = [
                        msg
                        for msg in context.user_data["history"]
                        if "контакты" not in msg["text"].lower()
                        and "телефон" not in msg["text"].lower()
                        and "перезвонить" not in msg["text"].lower()
                    ]
                    context.user_data["history"] = clean_history[
                        -10:
                    ]  # Сохраняем последние 10 сообщений

                    await update.message.reply_text(
                        f"Спасибо, {name}! Мы свяжемся с вами в ближайшее время. 😊"
                    )

                    # Показываем главное меню
                    await show_main_menu(update, context)
                else:
                    logger.error("Не удалось сохранить контакт!")
                    await update.message.reply_text(
                        "Произошла ошибка при сохранении ваших данных. "
                        "Пожалуйста, попробуйте еще раз."
                    )
                    # Оставляем флаг для повторного ввода контактов
            else:
                await update.message.reply_text(
                    "Не удалось распознать контактные данные. "
                    "Пожалуйста, введите имя и телефон в формате: "
                    '"Иван Иванов +79161234567"'
                )
            return  # ВАЖНО: завершаем обработку после этого блока

        # Обработка команд главного меню
        if user_text == "Показать все ЖК":
            all_objects = list(database.keys())
            response = "🏠 Доступные жилые комплексы:\n" + "\n".join(
                [f"• {name}" for name in all_objects]
            )
            await update.message.reply_text(response)
            return

        elif user_text == "Сравнить ЖК":
            await update.message.reply_text(
                "Пожалуйста, введите названия ЖК для сравнения через запятую\n"
                "Например: ЖК Солнечный, ЖК Луговой"
            )
            context.user_data["awaiting_comparison"] = True
            return

        elif user_text == "Оставить контакты":
            await update.message.reply_text(
                "Пожалуйста, введите ваше имя и номер телефона в формате: "
                "Иван Иванов +79161234567"
            )
            context.user_data["collecting_contacts"] = True
            return

        elif user_text == "Помощь":
            await help_command(update, context)
            return

        # Инициализация данных пользователя
        if "history" not in context.user_data:
            context.user_data["history"] = []
            context.user_data["object_context"] = ""
            logger.info(f"Инициализирована история для пользователя {user_id}")

        # Всегда обновляем персонализированный промпт
        user_name = context.user_data.get("user_name", "клиент")
        personalized_prompt = SYSTEM_PROMPT.format(user_name=user_name)

        # Универсальный поиск объектов в базе данных
        object_data = find_object_in_db(user_text, database)
        if object_data:
            context.user_data["object_context"] = format_context(object_data, database)
            logger.info(f"Обновлен контекст объекта")

        # Формируем сообщения для GPT
        messages = [{"role": "system", "text": personalized_prompt}]

        # 0. Флаг сохраненного контакта
        if context.user_data.get("contact_saved"):
            messages.append(
                {
                    "role": "system",
                    "text": "ВАЖНО: Контактные данные клиента уже сохранены! Не предлагать снова.",
                }
            )

        # 1. Основные системные инструкции
        messages.append({"role": "system", "text": SYSTEM_PROMPT})

        # 2. Контекст объекта (если есть)
        if context.user_data["object_context"]:
            messages.append(
                {
                    "role": "system",
                    "text": f"ТЕКУЩИЙ КОНТЕКСТ ОБЪЕКТА:\n{context.user_data['object_context']}",
                }
            )

        # 3. Добавляем краткую сводку по всем объектам
        global all_objects_summary
        if not all_objects_summary:
            all_objects_summary = generate_all_objects_summary(database)
        messages.append(
            {
                "role": "system",
                "text": f"ВСЯ БАЗА ОБЪЕКТОВ (кратко):\n{all_objects_summary}",
            }
        )

        # 4. Добавляем историю диалога
        for msg in context.user_data["history"]:
            # Фильтруем только сообщения пользователя
            if msg["role"] == "user":
                messages.append({"role": "user", "text": msg["text"]})
            # Для ассистента добавляем с пометкой
            elif msg["role"] == "assistant":
                messages.append(
                    {"role": "assistant", "text": f"[Ассистент]: {msg['text']}"}
                )

        # 5. Добавляем текущий запрос пользователя
        messages.append({"role": "user", "text": user_text})

        # 6. Важные указания для модели
        messages.append(
            {
                "role": "system",
                "text": "ВАЖНО: Отвечай только на последний запрос пользователя. Не пытайся предугадывать его ответы.",
            }
        )
        messages.append(
            {
                "role": "system",
                "text": "ЗАКЛЮЧЕНИЕ: Твой ответ должен заканчиваться на этом. Не добавляй ничего после.",
            }
        )

        # Логирование для отладки
        logger.info(f"Сформировано {len(messages)} сообщений для GPT")
        logger.debug(f"Первые 3 сообщения:")
        for i, msg in enumerate(messages[:3]):
            logger.debug(f"  {i}. {msg['role']}: {msg['text'][:100]}...")

        # Получаем ответ от YandexGPT
        logger.info("Вызов generate_yandexgpt_response")
        response_text = generate_yandexgpt_response(messages)
        logger.info(f"Ответ от YandexGPT: {response_text}")

        # Проверяем, содержит ли ответ запрос контактов
        if any(
            phrase in response_text.lower()
            for phrase in [
                "оставьте контакты",
                "оставьте телефон",
                "как вас зовут",
                "номер перезвонить",
            ]
        ):
            context.user_data["collecting_contacts"] = True
            logger.info("Установлен флаг collecting_contacts")

        # Добавляем ответ бота в историю
        context.user_data["history"].append(
            {"role": "assistant", "text": response_text}
        )

        # Добавляем запрос пользователя в историю
        context.user_data["history"].append({"role": "user", "text": user_text})

        # Ограничиваем размер истории (последние 10 сообщений)
        MAX_HISTORY_LENGTH = 10
        context.user_data["history"] = context.user_data["history"][
            -MAX_HISTORY_LENGTH:
        ]
        logger.debug(
            f"История сокращена до {len(context.user_data['history'])} сообщений"
        )

        # Форматируем ответ для Telegram
        clean_response = clean_telegram_text(response_text)

        # Отправляем ответ пользователю
        await update.message.reply_text(clean_response)
        logger.info("Сообщение отправлено пользователю")

    except Exception as e:
        logger.exception("Критическая ошибка в обработчике сообщений")
        try:
            await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
        except Exception as send_error:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {send_error}")


def extract_contact_info(text: str) -> tuple:
    """Извлекает имя и телефон из текста с улучшенной логикой"""
    # Удаляем лишние символы
    clean_text = "".join(filter(lambda x: x not in '",;', text))

    # Пробуем разделить по последнему пробелу
    parts = clean_text.rsplit(maxsplit=1)

    if len(parts) < 2:
        return None

    name_part = parts[0].strip()
    phone_part = parts[1].strip()

    # Проверяем, содержит ли вторая часть цифры
    if any(char.isdigit() for char in phone_part):
        # Оставляем только цифры в номере
        phone_clean = "".join(filter(str.isdigit, phone_part))

        # Проверяем длину номера (минимум 6 цифр)
        if len(phone_clean) >= 6:
            # Форматируем номер, если начинается с 7 или 8
            if phone_clean.startswith("8") and len(phone_clean) == 11:
                phone_clean = "7" + phone_clean[1:]
            elif phone_clean.startswith("7") and len(phone_clean) == 11:
                pass  # Уже правильный формат
            elif len(phone_clean) == 10:
                phone_clean = "7" + phone_clean

            return name_part, phone_clean

    return None


def clean_telegram_text(text: str) -> str:
    # Удаляем фразы о сборе контактов, если контакт уже сохранен
    if "контакты" in text.lower() or "телефон" in text.lower():
        phrases_to_remove = [
            "оставьте контакты",
            "оставьте телефон",
            "как вас зовут",
            "номер перезвонить",
            "записать вас",
            "для связи",
        ]
        for phrase in phrases_to_remove:
            text = text.replace(phrase, "")

    """Очищает текст от markdown и улучшает форматирование для Telegram"""
    # Убираем markdown и экранирование
    text = text.replace("**", "").replace("__", "").replace("\\", "")
    # Удаляем метки ассистента/пользователя
    text = text.replace("[Ассистент]:", "").replace("Пользователь:", "")

    # Улучшаем форматирование списков
    text = text.replace("•", "•")
    text = text.replace("- ", "• ")

    # Оптимизируем переносы строк
    text = text.replace("\n\n", "\n")

    # Добавляем эмодзи в начало
    if not text.startswith(("👋", "🏠", "📞", "ℹ️", "🔍")):
        emojis = ["🏠", "🌟", "✨", "💡", "📌", "🔎"]
        text = random.choice(emojis) + " " + text

    return text


async def reset_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Полный сброс состояния бота"""
    context.user_data.clear()
    await update.message.reply_text(
        "Состояние сброшено. Начнем заново!", reply_markup=ReplyKeyboardRemove()
    )
    await start(update, context)


def extract_name(text: str) -> str:
    """Извлекает имя из текста сообщения"""
    # Приводим к нижнему регистру для поиска
    lower_text = text.lower()

    # Паттерны, которые могут содержать имя
    patterns = ["меня зовут", "зовут", "мое имя", "имя", "Я", "это"]

    # Ищем паттерны в тексте
    for pattern in patterns:
        if pattern in lower_text:
            # Извлекаем часть после паттерна
            start_index = lower_text.index(pattern) + len(pattern)
            name_part = text[start_index:].strip()

            # Удаляем возможные знаки препинания
            if name_part and name_part[0] in [",", ":", "-", "."]:
                name_part = name_part[1:].strip()

            # Возвращаем первое слово (или первые 2 слова для составных имен)
            parts = name_part.split()
            if len(parts) > 0:
                # Берем не более 2 слов (для имени+фамилии)
                return " ".join(parts[:2]).title()

    # Если не нашли паттерны - возвращаем весь текст (обрезанный)
    return text[:30].strip().title()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Я помогу вам выбрать идеальное жильё!\n\n"
        "Доступные команды:\n"
        "/start - перезапустить бота\n"
        "/help - эта справка\n\n"
        "Вы можете:\n"
        "- Спросить о конкретном ЖК\n"
        "- Попросить подобрать вариант\n"
        "- Сравнить несколько ЖК\n"
        "- Оставить контакты для связи"
    )
    await update.message.reply_text(help_text)


async def setup_commands(application: Application) -> None:
    """Устанавливает команды меню для бота"""
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Помощь и справка"),
        BotCommand("menu", "Показать главное меню"),
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню с кнопками"""
    menu_keyboard = [
        ["Показать все ЖК", "Сравнить ЖК"],
        ["Помощь", "Оставить контакты"],
    ]
    await update.message.reply_text(
        "🏠 Главное меню:",
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True),
    )


def main() -> None:
    """Запуск бота."""
    logger.info("Запуск бота...")

    # Создаем Application и передаем токен
    try:
        # Создаем Application с использованием Builder
        builder = Application.builder().token(TELEGRAM_TOKEN)

        # Добавляем post_init обработчик
        builder = builder.post_init(setup_commands)

        application = builder.build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("menu", show_main_menu))
        application.add_handler(CommandHandler("reset", reset_bot))
        application.add_handler(
            MessageHandler(filters.Regex(r"^Начать общение$"), handle_first_message)
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # Запускаем бота
        logger.info("Бот запущен...")
        application.run_polling()
    except Exception as e:
        logger.exception("Критическая ошибка при запуске бота")


if __name__ == "__main__":
    main()
