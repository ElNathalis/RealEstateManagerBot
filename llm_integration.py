import requests
import os
import logging
import json
import time
from requests.exceptions import Timeout, ConnectionError

logger = logging.getLogger(__name__)


def generate_yandexgpt_response(messages: list) -> str:
    """
    Генерирует ответ на основе истории сообщений с использованием YandexGPT API.

    Параметры:
        messages (list): Список сообщений в формате [{"role": str, "text": str}]

    Возвращает:
        str: Сгенерированный ответ или сообщение об ошибке
    """
    try:
        start_time = time.time()
        logger.info("Начало генерации ответа YandexGPT")

        # Проверка учетных данных
        api_key = os.getenv("YANDEX_API_KEY")
        folder_id = os.getenv("YANDEX_FOLDER_ID")

        if not api_key:
            logger.error("Отсутствует переменная окружения YANDEX_API_KEY!")
            return "Извините, возникла техническая ошибка. Попробуйте позже."

        if not folder_id:
            logger.error("Отсутствует переменная окружения YANDEX_FOLDER_ID!")
            return "Извините, возникла техническая ошибка. Попробуйте позже."

        # URL для запроса к API
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {api_key}",
            "x-folder-id": folder_id,
            "Content-Type": "application/json",
        }

        # Формируем полезную нагрузку
        payload = {
            "modelUri": f"gpt://{folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,  # Оптимальное значение для баланса креативности и точности
                "maxTokens": 1500,  # Увеличим лимит для более полных ответов
            },
            "messages": messages,
        }

        # Логируем запрос для отладки
        logger.debug(
            f"Отправляемый запрос к YandexGPT:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
        )

        # Отправка запроса с таймаутом
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            logger.info(f"Статус ответа YandexGPT: {response.status_code}")
            logger.debug(f"Время ответа: {time.time() - start_time:.2f} сек")
        except Timeout:
            logger.error("Таймаут запроса к YandexGPT API")
            return (
                "Извините, сервис ответил слишком долго. Попробуйте повторить вопрос."
            )
        except ConnectionError:
            logger.error("Ошибка подключения к YandexGPT API")
            return "Извините, не удалось подключиться к сервису. Проверьте интернет-соединение."

        # Проверка статуса ответа
        if response.status_code != 200:
            error_msg = f"Ошибка API ({response.status_code}): {response.text}"
            logger.error(error_msg)

            # Попытка извлечь детали ошибки
            try:
                error_data = response.json()
                if "message" in error_data:
                    return f"Ошибка сервиса: {error_data['message']}"
            except:
                pass

            return "Извините, сервис временно недоступен. Попробуйте позже."

        # Обработка успешного ответа
        try:
            response_data = response.json()
            logger.debug(
                f"Полный ответ API: {json.dumps(response_data, indent=2, ensure_ascii=False)}"
            )

            # Проверяем наличие ожидаемой структуры ответа
            if "result" in response_data and "alternatives" in response_data["result"]:
                if response_data["result"]["alternatives"]:
                    return response_data["result"]["alternatives"][0]["message"]["text"]
                else:
                    logger.error("Пустой ответ от модели")
                    return "Извините, не удалось сгенерировать ответ."
            else:
                logger.error(
                    f"Неожиданный формат ответа: {json.dumps(response_data, indent=2)}"
                )
                return "Извините, возникла техническая ошибка."

        except (KeyError, IndexError, TypeError) as e:
            logger.exception(f"Ошибка разбора ответа API: {e}")
            return "Извините, возникла ошибка обработки ответа."

    except Exception as e:
        logger.exception(f"Неожиданная ошибка в YandexGPT API: {str(e)}")
        return "Извините, возникла непредвиденная ошибка."
