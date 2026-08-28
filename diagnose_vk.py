import json
import os
from typing import Any

import vk_api
from dotenv import load_dotenv
from vk_api.exceptions import ApiError


API_VERSION = "5.199"


def hide_secrets(value: Any) -> Any:
    """Скрывает токены, если VK вернёт их в диагностических данных."""
    if isinstance(value, dict):
        return {
            key: "<скрыто>" if "token" in key.lower() else hide_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [hide_secrets(item) for item in value]
    return value


def get_token_group(vk) -> dict:
    response = vk.groups.getById()
    groups = response.get("groups", []) if isinstance(response, dict) else response

    if not groups:
        raise RuntimeError("VK не вернул сообщество, связанное с этим токеном.")

    return groups[0]


def main() -> None:
    load_dotenv()
    token = os.getenv("VK_TOKEN")

    if not token:
        raise RuntimeError("VK_TOKEN не найден в файле .env.")

    vk_session = vk_api.VkApi(token=token, api_version=API_VERSION)
    vk = vk_session.get_api()

    print(f"Версия VK API: {API_VERSION}")
    print("1. Определяем сообщество по токену...")
    group = get_token_group(vk)
    group_id = group["id"]
    print(f"group_id: {group_id}")
    print(f"Название: {group.get('name', '<не указано>')}")

    print("\n2. Проверяем фактические права токена...")
    try:
        permissions = vk.groups.getTokenPermissions()
        print(json.dumps(hide_secrets(permissions), ensure_ascii=False, indent=2))
    except ApiError as error:
        print(f"Не удалось получить права токена: {error}")

    print("\n3. Вызываем groups.getLongPollServer...")
    try:
        server = vk.groups.getLongPollServer(group_id=group_id)
    except ApiError as error:
        print("Запрос отклонён VK.")
        print(f"Полный текст ошибки: {error}")
        print("Детали ответа VK:")
        print(
            json.dumps(
                hide_secrets(error.error),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print("Запрос выполнен успешно.")
    print(f"Long Poll server: {server.get('server', '<не указан>')}")
    print("Ключ и токен намеренно не выводятся.")


if __name__ == "__main__":
    main()
