# FoxGameLab

FoxGameLab — VK-бот для учителей английского языка. Он генерирует учебные игры по возрасту, уровню, теме, навыку и длительности, создаёт printable PDF-наборы, хранит коллекцию игр и повторно использует готовые материалы.

Бот получает события сообщества через VK Community Long Poll и использует YandexGPT для генерации игрового содержания.

## Требования

- Python 3.10 или новее (проект протестирован на Python 3.12);
- сообщество VK с включёнными сообщениями и Community Long Poll;
- VK community token с правами `messages`, `manage`, `photos` и `docs`;
- API key и folder ID для YandexGPT.

## Установка

```bash
python -m venv .venv
```

Активируйте виртуальное окружение и установите зависимости:

```bash
pip install -r requirements.txt
```

## Настройка environment variables

Скопируйте `.env.example` в `.env` и заполните значения:

```env
VK_TOKEN=your_vk_community_token
YANDEX_API_KEY=your_yandex_cloud_api_key
YANDEX_FOLDER_ID=your_yandex_cloud_folder_id
```

- `VK_TOKEN` — токен сообщества VK. Право `docs` необходимо для отправки PDF-файлов.
- `YANDEX_API_KEY` — API key сервисного аккаунта Yandex Cloud.
- `YANDEX_FOLDER_ID` — ID каталога Yandex Cloud с доступом к YandexGPT.

Файл `.env` содержит секреты и исключён из Git. Не добавляйте реальные credentials в `.env.example` или исходный код.

## Запуск

```bash
python bot.py
```

При запуске бот подключается к Community Long Poll и ожидает входящие сообщения. Runtime-файлы `saved_games.json`, `carousel_media.json`, логи и созданные PDF исключены из Git.

## Тесты

```bash
python -m unittest
```
