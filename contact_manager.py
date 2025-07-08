import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ContactManager:
    def __init__(self, file_path: str = None):
        # Определяем абсолютный путь к файлу
        if not file_path:
            base_dir = Path(__file__).resolve().parent
            self.file_path = base_dir / "data" / "contacts.json"
        else:
            self.file_path = Path(file_path)

        logger.info(f"Файл контактов: {self.file_path.absolute()}")

        # Гарантируем существование папки и файла
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f)
            logger.info("Создан новый файл контактов")

    def save_contact(
        self, user_id: int, name: str, phone: str, context: str = ""
    ) -> bool:
        try:
            # Загружаем существующие контакты
            contacts = self.load_contacts()
            logger.info(f"Загружено контактов: {len(contacts)}")

            # Создаем новый контакт
            new_contact = {
                "user_id": user_id,
                "name": name,
                "phone": phone,
                "context": context,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Добавляем новый контакт
            contacts.append(new_contact)
            logger.info(f"Добавлен контакт: {name} ({phone})")

            # Сохраняем обратно в файл
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=2, ensure_ascii=False)

            logger.info(f"Сохранено контактов: {len(contacts)}")
            return True
        except Exception as e:
            logger.exception(f"Ошибка сохранения контакта: {str(e)}")
            return False

    def load_contacts(self) -> list:
        try:
            if not self.file_path.exists():
                return []

            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON. Возвращаю пустой список.")
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки контактов: {str(e)}")
            return []


# Инициализируем менеджер контактов
contact_manager = ContactManager()
