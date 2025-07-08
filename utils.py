import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def format_context(object_data: dict, full_database: dict) -> str:
    try:
        """Форматирует контекст объекта с учетом типа запроса"""
        # Обработка автоматического поиска
        if object_data.get("special_type") == "auto_search":
            text = "===== НАЙДЕННЫЕ ОБЪЕКТЫ =====\n"
            for obj_name in object_data["objects"]:
                obj = full_database[obj_name]
                text += f"• {obj_name}:\n"
                text += f"  Описание: {obj['описание'][:100]}...\n"
                text += f"  Срок сдачи: {obj['срок_сдачи']}\n"
                if "особенности" in obj:
                    text += f"  Особенности: {', '.join(obj['особенности'][:3])}\n"
                text += "\n"
            return text

        # Запрос списка всех ЖК
        if object_data.get("special_type") == "all_objects":
            text = "===== ВСЕ ДОСТУПНЫЕ ЖК =====\n"
            for obj_name in object_data["objects"]:
                text += f"- {obj_name}\n"
            return text + "\n"

        # Запрос сравнения объектов
        if object_data.get("special_type") == "compare":
            text = "===== СРАВНЕНИЕ ОБЪЕКТОВ =====\n"
            for obj_name in object_data["objects"]:
                obj = full_database[obj_name]
                text += f"• {obj_name}:\n"
                text += f"  Описание: {obj['описание'][:100]}...\n"
                text += f"  Этажность: {obj['этажность']}\n"
                text += f"  Срок сдачи: {obj['срок_сдачи']}\n"
                if "ближайшие_объекты" in obj:
                    text += f"  Рядом: {', '.join([n['название'] for n in obj['ближайшие_объекты'][:2]])}\n"
                text += "\n"
            return text

        # Форматирование одного объекта
        text = f"===== {object_data['название']} =====\n"
        text += f"Описание: {object_data['описание']}\n"
        text += f"Этажность: {object_data['этажность']}\n"
        text += f"Срок сдачи: {object_data['срок_сдачи']}\n\n"
        text += "Ближайшие объекты:\n"
        for obj in object_data["ближайшие_объекты"]:
            text += f"- {obj['название']} ({obj['тип']}, {obj['расстояние']})\n"
        return text

    except Exception as e:
        logger.error(f"Ошибка форматирования контекста: {e}")
        return ""


def find_object_in_db(user_query: str, db: dict) -> dict:
    """Поиск объекта по ключевым словам"""
    try:
        if not db:
            logger.warning("База данных не загружена")
            return None

        normalized_query = user_query.lower()
        matches = []

        # 1. Запрос списка всех ЖК
        if any(
            phrase in normalized_query
            for phrase in [
                "какие жк доступны",
                "список жк",
                "перечисли жк",
                "ваши объекты",
            ]
        ):
            return {"special_type": "all_objects", "objects": list(db.keys())}

        # 2. Запрос сравнения объектов
        if "сравни" in normalized_query or "сравнение" in normalized_query:
            objects_to_compare = []
            for obj_name in db.keys():
                if obj_name.lower() in normalized_query:
                    objects_to_compare.append(obj_name)

            if len(objects_to_compare) >= 2:
                return {"special_type": "compare", "objects": objects_to_compare}

        # 1. Поиск по точному совпадению
        for obj_name, obj_data in db.items():
            if obj_name.lower() == normalized_query:
                return {"название": obj_name, **obj_data}

        # После точного совпадения добавим:
        for obj_name, obj_data in db.items():
            if normalized_query in obj_name.lower():
                return {"название": obj_name, **obj_data}

        # Добавим обработку сокращений:
        name_mapping = {"солнеч": "ЖК Солнечный", "луг": "ЖК Луговой"}

        for short, full in name_mapping.items():
            if short in normalized_query:
                return {"название": full, **db[full]}

        # 2. Поиск по частичному совпадению
        for obj_name, obj_data in db.items():
            if obj_name.lower() in normalized_query:
                return {"название": obj_name, **obj_data}

        # 3. Поиск по ключевым словам
        keywords = ["солнечный", "луговой", "стройинвест", "жк"]
        for keyword in keywords:
            if keyword in normalized_query:
                for obj_name, obj_data in db.items():
                    if keyword in obj_name.lower():
                        return {"название": obj_name, **obj_data}

            # 2. Поиск по описанию
            for obj_name, obj_data in db.items():
                if (
                    "описание" in obj_data
                    and obj_data["описание"].lower() in normalized_query
                ):
                    if obj_name not in matches:
                        matches.append(obj_name)

            # 3. Поиск по особенностям
            for obj_name, obj_data in db.items():
                if "особенности" in obj_data:
                    for feature in obj_data["особенности"]:
                        if feature.lower() in normalized_query:
                            if obj_name not in matches:
                                matches.append(obj_name)

            # 4. Поиск по ближайшим объектам
            for obj_name, obj_data in db.items():
                if "ближайшие_объекты" in obj_data:
                    for nearby in obj_data["ближайшие_объекты"]:
                        if nearby["название"].lower() in normalized_query:
                            if obj_name not in matches:
                                matches.append(obj_name)

            # Обработка результатов
            if matches:
                return {
                    "special_type": "auto_search",
                    "objects": list(set(matches)),  # Уникальные результаты
                }

        logger.info(f"Объект не найден для запроса: {user_query}")
        return None

    except Exception as e:
        logger.exception(f"Ошибка поиска объекта: {e}")
        return None


def generate_all_objects_summary(db: dict) -> str:
    """Генерирует краткую сводку по всем объектам"""
    summary = "===== КРАТКИЙ ОБЗОР ВСЕХ ОБЪЕКТОВ =====\n"
    for name, data in db.items():
        summary += f"• {name}:\n"
        summary += f"  - Описание: {data['описание'][:70]}...\n"
        summary += f"  - Срок сдачи: {data['срок_сдачи']}\n"
        if "особенности" in data:
            summary += f"  - Особенности: {', '.join(data['особенности'][:3])}\n"
        summary += "\n"
    return summary


def compare_complexes(complex_names: list, db: dict) -> str:
    """
    Сравнивает несколько жилых комплексов и возвращает форматированную строку сравнения

    Параметры:
        complex_names (list): Список названий ЖК для сравнения
        db (dict): База данных с информацией о ЖК

    Возвращает:
        str: Форматированное сравнение объектов
    """
    try:
        if not complex_names:
            return "Пожалуйста, укажите названия ЖК для сравнения."

        result = "🔍 Сравнение ЖК:\n\n"
        found_any = False

        for name in complex_names:
            name = name.strip()
            if name in db:
                found_any = True
                data = db[name]
                result += f"🏢 {name}:\n"
                result += f"  • Описание: {data['описание'][:100]}...\n"
                result += f"  • Этажность: {data['этажность']}\n"
                result += f"  • Срок сдачи: {data['срок_сдачи']}\n"

                if "ближайшие_объекты" in data and data["ближайшие_объекты"]:
                    nearby = ", ".join(
                        obj["название"] for obj in data["ближайшие_объекты"][:3]
                    )
                    result += f"  • Ближайшие объекты: {nearby}\n"

                result += "\n"
            else:
                result += f"⚠️ ЖК '{name}' не найден в базе данных\n\n"

        if not found_any:
            return "Ни один из указанных ЖК не найден. Пожалуйста, проверьте названия."

        return result

    except Exception as e:
        logger.error(f"Ошибка при сравнении ЖК: {e}")
        return "Произошла ошибка при сравнении объектов. Попробуйте позже."
