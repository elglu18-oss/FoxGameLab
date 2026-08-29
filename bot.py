import json
import os
import random
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
import vk_api
from dotenv import load_dotenv
from vk_api import VkUpload
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from pdf_pack import create_printable_pack


BASE_DIR = Path(__file__).resolve().parent
CAROUSEL_DIR = BASE_DIR / "assets" / "carousel"
MEDIA_CACHE_PATH = BASE_DIR / "carousel_media.json"
SAVED_GAMES_PATH = BASE_DIR / "saved_games.json"
YANDEX_COMPLETION_URL = "https://ai.api.cloud.yandex.net/foundationModels/v1/completion"
VK_API_VERSION = "5.199"

CAROUSEL_ASSETS = {
    "mission": "mission.png",
    "how_to_play": "how_to_play.png",
    "english_toolkit": "english_toolkit.png",
    "fox_twist": "fox_twist.png",
    "how_to_win": "how_to_win.png",
}

START_MESSAGES = {"привет", "начать"}
NEW_GAME_MESSAGES = {"новая игра", "🆕 новая игра"}
SAVE_GAME_MESSAGES = {"сохранить", "💾 сохранить", "сохранить игру", "💾 сохранить игру"}
COLLECTION_MESSAGES = {"моя коллекция", "📚 моя коллекция"}
MANAGE_COLLECTION_MESSAGES = {"управлять коллекцией", "🗑 управлять коллекцией"}
COLLECTION_SEARCH_MESSAGES = {"поиск", "🔎 поиск"}
COLLECTION_FILTER_MESSAGES = {"фильтры", "🎯 фильтры"}
COLLECTION_FAVORITES_MESSAGES = {"избранное", "⭐ избранное"}
COLLECTION_RECENT_MESSAGES = {"недавние", "🕘 недавние"}
RESET_FILTER_MESSAGES = {"сбросить фильтр", "❌ сбросить фильтр"}
ADD_FAVORITE_MESSAGES = {"в избранное", "⭐ в избранное"}
REMOVE_FAVORITE_MESSAGES = {"убрать из избранного", "☆ убрать из избранного"}
BACK_MESSAGES = {
    "назад",
    "↩ назад",
    "↩️ назад",
    "оставить как есть",
    "↩ оставить как есть",
}
USE_SAVED_MESSAGES = {
    "использовать",
    "▶ использовать",
    "▶️ использовать",
    "использовать эту игру",
    "▶ использовать эту игру",
}
DELETE_SAVED_MESSAGES = {"удалить", "🗑 удалить"}
CONFIRM_DELETE_MESSAGES = {"да, удалить", "✅ да, удалить"}
CANCEL_MESSAGES = {"отмена", "❌ отмена", "оставить", "↩ оставить"}
MATERIAL_MENU_MESSAGES = {
    "материалы",
    "📦 материалы",
    "материалы к игре",
    "🧰 материалы к игре",
}
MATERIAL_COMMANDS = {
    "карточки": "cards",
    "🃏 карточки": "cards",
    "game cards": "cards",
    "🎴 game cards": "cards",
    "worksheet": "worksheet",
    "📄 worksheet": "worksheet",
    "player worksheet": "worksheet",
    "📝 player worksheet": "worksheet",
    "мини-набор": "pack",
    "🎒 мини-набор": "pack",
    "teacher mini pack": "pack",
    "🦊 teacher mini pack": "pack",
}
OTHER_MATERIAL_MESSAGES = {"другой материал", "🧰 другой материал"}
BACK_TO_GAME_MESSAGES = {"к игре", "↩ к игре", "↩️ к игре"}
PRINTABLE_COMMANDS = {
    "printable pack",
    "🖨 printable pack",
    "весь комплект",
    "📚 весь комплект",
    "сделать ещё раз",
    "🖨 сделать ещё раз",
}
IGNORED_CAROUSEL_ACTIONS = {
    "подробнее",
    "фразы",
    "twist",
    "попробовать twist",
}
VARIATION_COMMANDS = {
    "ещё вариант": "another",
    "еще вариант": "another",
    "🎲 ещё вариант": "another",
    "🎲 еще вариант": "another",
    "сделать активнее": "active",
    "🔥 сделать активнее": "active",
    "без подготовки": "no_prep",
    "⚡ без подготовки": "no_prep",
    "усложнить": "harder",
    "🧠 усложнить": "harder",
    "удиви меня": "surprise",
    "🪄 удиви меня": "surprise",
    "✨ удиви меня": "surprise",
}

COMMAND_PROGRESS = {
    "base": "🧪 Собираю механику...",
    "another": "🎲 Ищу другую механику...",
    "no_prep": "⚡ Убираю всю подготовку...",
    "active": "🔥 Добавляю движение и азарт...",
    "harder": "🧠 Добавляю уровень сложности...",
    "surprise": "🪄 Сейчас будет что-то необычное...",
}

START_REPLY = """🦊 FOX GAME LAB

Начинаем охоту за классной идеей!

Сколько лет твоим игрокам?"""

NEW_GAME_REPLY = """🦊 NEW GAME

Новая охота за идеей!

Сколько лет твоим игрокам?"""

LEVEL_REPLY = """🎯 Отлично!

Какой уровень английского?"""

TOPIC_REPLY = """🌍 Какая тема урока?

Например:
Travel
Food
Animals
School
Past Simple"""

SKILL_REPLY = """⚡ Что будем прокачивать?"""

TIME_REPLY = """⏱ Сколько времени есть на игру?"""

AI_ERROR_REPLY = """🦊 Упс, лаборатория немного зависла.

Попробуй отправить сообщение ещё раз через минуту."""

AI_TIMEOUT_REPLY = """🦊 Что-то задержалось.
Попробуй ещё раз через несколько секунд."""

REBUILD_ERROR_REPLY = """🦊 Не получилось пересобрать игру.
Попробуй ещё раз."""

ALREADY_PROCESSING_REPLY = "🦊 Уже придумываю..."
MATERIAL_PROCESSING_REPLY = "🦊 Уже собираю материалы. Ещё пару секунд..."
MATERIAL_ERROR_REPLY = "🦊 Не получилось собрать материал. Попробуй ещё раз."
PDF_PROCESSING_REPLY = "🦊 Уже собираю PDF. Ещё немного..."
PDF_ERROR_REPLY = "🦊 Не получилось собрать printable pack.\nПопробуй ещё раз."
PDF_UPLOAD_ERROR_REPLY = (
    "🦊 PDF собран, но VK не смог прикрепить файл.\n"
    "Попробуй ещё раз через несколько секунд."
)
COLLECTION_ERROR_REPLY = "🦊 Не получилось открыть коллекцию. Попробуй ещё раз."

MATERIAL_PROGRESS = {
    "cards": "🃏 Собираю карточки...",
    "worksheet": "📄 Готовлю worksheet...",
    "pack": "🎒 Собираю мини-набор...",
}

MATERIAL_LOG_NAMES = {
    "cards": "CARDS",
    "worksheet": "WORKSHEET",
    "pack": "PACK",
}

PRINTABLE_PROGRESS = (
    "🖨 Собираю printable pack...\n\n"
    "🦊 Карточки, игровой лист и шпаргалка учителя — в один комплект."
)

AI_INSTRUCTIONS = """Ты — очень креативный методист английского языка для детей и подростков.

Создай настоящую игру, а не обычное упражнение. Английский должен быть нужен для победы, миссии или получения информации. Предпочитай detective, secret mission, spy, mafia, hidden role, forbidden word, auction, escape, challenge, collect clues, steal information, impostor, team competition, timer, movement, points, risk, secret cards и changing rules.

Не предлагай просто обсудить тему в парах, ответить на вопросы, составить предложения или заполнить пропуски. Игра должна соответствовать возрасту, уровню, теме, навыку и времени, требовать минимум подготовки, вовлекать класс одновременно и иметь неожиданный поворот.

Перед ответом внутренне проверь: есть ли реальная игровая цель и азарт, нужен ли английский для победы, есть ли неожиданный элемент и можно ли провести игру на реальном уроке. Если хотя бы один ответ отрицательный, придумай другую механику. Не показывай эту проверку.

Все значения JSON — название, миссия, правила, фразы, поворот и победа — пиши на естественном коротком английском языке.

Верни только один корректный JSON-объект без пояснений и без Markdown:
{
  "title": "short game title",
  "mission": "no more than two short sentences",
  "how_to_play": ["step 1", "step 2", "step 3", "step 4"],
  "english_toolkit": ["phrase 1", "phrase 2", "phrase 3", "phrase 4", "phrase 5"],
  "fox_twist": "one vivid unexpected twist",
  "how_to_win": "short and clear victory condition"
}

В mission должно быть не больше двух коротких предложений. В how_to_play должно быть 3–4 шага максимум по 14 слов. В english_toolkit должно быть 4–6 коротких английских фраз. Fox twist и how_to_win — по одному короткому предложению. Не повторяй одну мысль и не используй символы звёздочки, решётки и обратные кавычки внутри значений."""

MATERIAL_AI_INSTRUCTIONS = """Ты создаёшь готовые текстовые материалы для уже существующей игры на уроке английского.

Сначала проанализируй возраст, CEFR, тему, навык, длительность, механику, роли, условие победы и Fox Twist переданной игры. Определи основной тип механики: detective, auction, mission, escape, role game или другой подходящий тип. Форма материала обязана меняться вместе с механикой. Не меняй саму игру, не пересказывай HOW TO PLAY и не пиши методический конспект. Материал должен выглядеть как часть игры и за пять секунд объяснять, что с ним делать.

Три формата имеют разные функции:
CARDS — разные физические роли или игровые элементы, которые получают игроки;
WORKSHEET — визуальная игровая панель ученика во время игры;
MINI PACK — короткая панель управления и готовый сценарий учителя.
Не превращай их в три версии одного текста.

Используй только то, что полностью содержится в ответе или уже доступно в обычном классе. Запрещено ссылаться на несуществующие картинки, изображения, аудио, recording, video, attachment, worksheet, handout, cards или другие ресурсы, которых нет в самом ответе. Нельзя писать Look at the pictures или Listen to the recording. Не требуй предварительно созданных ботом файлов.

Основное содержание пиши на английском. Для A1 используй минимум текста, короткие фразы, выбор, отметки и простые предложения. Для A2 — короткие ответы, phrase support и простое объяснение. Для B1/B2 — больше стратегии, аргументации, выбора и объяснения решений.

Визуальный стиль обязателен: короткие игровые заголовки; пустая строка между блоками; ровно один уместный emoji в заголовке блока; максимум 2–3 короткие строки подряд; никаких длинных абзацев, абстрактных советов и служебных пояснений. Не используй repeat after the teacher, fill in the gaps, look at the pictures или listen to the recording.

Перед ответом внутренне проверь семь пунктов: материал реально usable завтра; подходит возрасту; соответствует CEFR; напрямую связан с текущей игрой; содержит игровое действие; не ссылается на отсутствующий ресурс; заметно отличается от двух других форматов. Если хотя бы один пункт не выполнен — полностью переделай ответ.

Верни только тело материала без общего заголовка, названия игры, Markdown, вступления и заключения. Не используй звёздочки, решётки или обратные кавычки. Общий объём — не более 3000 символов."""

WORKSHEET_AI_INSTRUCTIONS = """Ты создаёшь только плотный PLAYER WORKSHEET для уже готовой игры на уроке английского. Это полноценная языковая практика, связанная с игровой механикой, а не методический конспект и не декоративная панель.

Верни только тело worksheet без общего заголовка, названия игры, параметров, Markdown, вступления и заключения. Формат каждого основного блока строго такой:
TASK N — SHORT ACTION TITLE
1. one complete practice item
2. one complete practice item
3. one complete practice item

Для A1 обязательны ровно 8 TASK и 25–35 реальных языковых действий. Используй надёжную раскладку: TASK 1–6 содержат минимум по 4 отдельных действия, TASK 7–8 — минимум по 3; итого около 30. Каждый item или checkbox line — отдельная строка. Варианты внутри одного item не считай отдельными действиями. Для A2 нужны минимум 7 TASK и 25–40 действий; B1 — минимум 7 TASK и 20–35; B2 — минимум 7 TASK и 15–30.

Для A1 detective/Spy Hunt используй только детскую лексику. Не используй CIVILIAN, SUSPECT, EVIDENCE, INVESTIGATE или STRATEGY. Вместо них пиши STUDENT, PLAYER, SPY, SECRET, CLUE, ASK, ANSWER, LISTEN, WATCH, FIND, GUESS и CHANGE.

Смешай controlled practice, semi-controlled practice, speaking/game use и финальное применение. Последние 1–2 TASK напрямую используются в текущей игровой механике. Для grammar адаптивно включай question building, short answers, choosing the form, mistake correction, sentence completion, matching, speaking/reporting и final game result. Для vocabulary, reading, speaking и functional language подбирай другие уместные типы, не копируя grammar sequence механически.

После TASK блоков добавь ровно один финальный блок:
FOX CHALLENGE
одно короткое, чуть более сложное самостоятельное языковое действие.

Пиши все stimulus items, варианты и sentence starters полностью. Используй checkboxes ☐ и answer lines ______ там, где ученик реально отвечает. Не ссылайся на отсутствующие pictures, audio, recording, cards или handouts. Не используй звёздочки, решётки и обратные кавычки. Перед ответом буквально пересчитай TASK и отдельные practice items; если лимит не выполнен, пересобери материал."""

CARDS_AI_INSTRUCTIONS = """Ты создаёшь только готовый набор коротких printable GAME CARDS для уже существующей игры. Карточку должен самостоятельно понять ребёнок соответствующего возраста и CEFR за 3–5 секунд.

Верни только тело набора без общего заголовка, названия игры, Markdown, вступления и заключения. Первая строка строго SET: X CARDS, затем пустая строка. Каждая карточка — отдельный блок: короткий ROLE/TYPE + номер и 2–3 очень короткие строки с целью, действием, секретом или готовой репликой. Между всеми карточками обязательно оставляй пустую строку. Карточки должны иметь разные игровые функции.

Для detective-игры уровня A1 и возраста около 9 лет создай ровно 6 карточек: SPY 1, SPY 2, STUDENT 1, STUDENT 2, STUDENT 3, STUDENT 4. Не используй CIVILIAN, SUSPECT, IDENTITY DETAIL, EVIDENCE, INVESTIGATE, STRATEGY или TRUTHFULLY. Используй простые слова student, player, spy, secret, clue, ask, answer, listen, watch, find, guess, change. SPY 1: Keep your secret.; Change one answer after 2 minutes.; Say: "No, I am not a spy." SPY 2: Keep your secret.; Change one answer after 2 minutes.; Say: "Yes, I am a student." STUDENT 1: Ask 2 classmates.; Listen carefully.; Find the spies. STUDENT 2: Answer the questions.; Watch for changes.; Find the spies. STUDENT 3: Ask simple questions.; Listen carefully.; Make your guess. STUDENT 4: Ask and answer.; Watch the other players.; Find the spies.

Не добавляй teacher instructions, распределение ролей отдельной строкой, ссылки на внешние материалы или пересказ правил. Не используй звёздочки, решётки и обратные кавычки. Перед ответом проверь число карточек, детскую лексику и отсутствие CIVILIAN."""

TEACHER_PACK_AI_INSTRUCTIONS = """Ты создаёшь только практический TEACHER MINI PACK для уже существующей игры. Это компактный classroom dashboard: before, during, differentiation, after-game reflection и preparation checklist.

Верни только тело материала без общего заголовка, названия игры, Markdown, вступления и заключения. Используй ровно 9 отдельных блоков и именно эти заголовки:
START
SAY THIS
ENGLISH SUPPORT
TEACHER TIPS
FOX TWIST
IF TOO EASY
IF TOO HARD
AFTER THE GAME
QUICK CHECK — WHAT TO PREPARE

Между блоками обязательно оставляй пустую строку. Для A1 detective/Spy Hunt обязательно включи буквально: в SAY THIS строку Teacher Tip: Say these lines with energy to build excitement.; в IF TOO HARD строки Model the first round together., Write question prompts on the board., Let students practise in pairs first.; в AFTER THE GAME вопросы Who were the spies? и Which clues helped you?; в QUICK CHECK пункты Game cards, Player worksheet, Timer, Board markers.

START: 4 коротких действия и отдельная строка Teacher Note о скрытых карточках/ролях. SAY THIS: 4 готовые энергичные реплики и короткий teacher tip. ENGLISH SUPPORT: 6 полностью написанных фраз нужного CEFR. TEACHER TIPS: 8 конкретных действий, включая shy/weaker/stronger students, eye contact, full sentences, classroom monitoring, delayed correction и praise. FOX TWIST: момент, точное изменение и реплика учителя. IF TOO EASY: 4 мгновенные адаптации, включая extra full sentence и removal of one support prompt. IF TOO HARD: 5 действий, включая model, 3 question starters, pair practice, visible worksheet и ready-made question. AFTER THE GAME: 5 конкретных reflection/correction actions. QUICK CHECK: 5 вещей, включая optional reward или point tokens.

Пиши короткими строками, без длинных абзацев и общих методических рассуждений. Используй только доступные в обычном классе материалы. Не ссылайся на несуществующие pictures, audio или recording. Не используй звёздочки, решётки и обратные кавычки. Перед ответом проверь наличие всех 9 блоков, помощи слабым/сильным ученикам, classroom management, reflection и checklist."""

USER_STATES: dict[int, dict[str, Any]] = {}
USER_STATES_LOCK = threading.RLock()
SAVED_GAMES_LOCK = threading.RLock()


def get_group_id(vk) -> int:
    response = vk.groups.getById()
    groups = response.get("groups", []) if isinstance(response, dict) else response
    if not groups:
        raise RuntimeError("Не удалось определить ID сообщества по VK-токену.")
    return groups[0]["id"]


def new_user_state() -> dict[str, Any]:
    state = {
        "current_parameters": {
            "age": None,
            "level": None,
            "topic": None,
            "skill": None,
            "duration": None,
        },
        "current_game": None,
        "current_game_type": None,
        "current_materials": {
            "fingerprint": None,
            "cards": None,
            "worksheet": None,
            "pack": None,
            "pdf_path": None,
            "pdf_attachment": None,
        },
        "age": None,
        "level": None,
        "topic": None,
        "skill": None,
        "duration": None,
        "last_game": None,
        "last_game_type": None,
        "current_step": "age",
        "processing": False,
        "processing_kind": None,
        "collection_mode": None,
        "selected_saved_game_id": None,
        "collection_visible_ids": [],
        "collection_query": None,
        "collection_filter": None,
        "collection_filter_field": None,
        "delete_return_mode": None,
        "material_mode": None,
        "last_cards": None,
        "last_worksheet": None,
        "last_mini_pack": None,
        "material_cache_fingerprint": None,
    }
    return state


def normalize_user_state(state: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy flat state in-place while keeping old integrations compatible."""
    parameters = state.setdefault("current_parameters", {})
    for field in ("age", "level", "topic", "skill", "duration"):
        if field not in parameters or parameters[field] is None:
            parameters[field] = state.get(field)
        state[field] = parameters.get(field)

    if "current_game" not in state:
        state["current_game"] = deepcopy(state.get("last_game"))
    if state.get("current_game") is None and state.get("last_game") is not None:
        state["current_game"] = deepcopy(state["last_game"])
    state["last_game"] = state.get("current_game")

    if "current_game_type" not in state:
        state["current_game_type"] = state.get("last_game_type")
    if state.get("current_game_type") is None and state.get("last_game_type") is not None:
        state["current_game_type"] = state["last_game_type"]
    state["last_game_type"] = state.get("current_game_type")

    materials = state.setdefault("current_materials", {})
    legacy_materials = {
        "cards": "last_cards",
        "worksheet": "last_worksheet",
        "pack": "last_mini_pack",
    }
    for kind, legacy_field in legacy_materials.items():
        if kind not in materials or materials[kind] is None:
            materials[kind] = state.get(legacy_field)
        state[legacy_field] = materials.get(kind)
    if "fingerprint" not in materials or materials["fingerprint"] is None:
        materials["fingerprint"] = state.get("material_cache_fingerprint")
    state["material_cache_fingerprint"] = materials.get("fingerprint")
    materials.setdefault("pdf_path", None)
    materials.setdefault("pdf_attachment", None)
    return state


def set_current_parameter(state: dict[str, Any], field: str, value: Any) -> None:
    normalize_user_state(state)
    state["current_parameters"][field] = value
    state[field] = value


def set_current_game(state: dict[str, Any], game: dict[str, Any], game_type: str | None = None) -> None:
    normalize_user_state(state)
    state["current_game"] = game
    state["last_game"] = game
    resolved_type = game_type or detect_game_type(game)
    state["current_game_type"] = resolved_type
    state["last_game_type"] = resolved_type


def clear_current_materials(state: dict[str, Any]) -> None:
    state["current_materials"] = {
        "fingerprint": None,
        "cards": None,
        "worksheet": None,
        "pack": None,
        "pdf_path": None,
        "pdf_attachment": None,
    }
    state["last_cards"] = None
    state["last_worksheet"] = None
    state["last_mini_pack"] = None
    state["material_cache_fingerprint"] = None


def get_cached_material(state: dict[str, Any], kind: str) -> str | None:
    normalize_user_state(state)
    game = state.get("current_game")
    if not game:
        return None
    materials = state["current_materials"]
    if materials.get("fingerprint") != game_fingerprint(game):
        return None
    value = materials.get(kind)
    return value if isinstance(value, str) and value else None


def cache_material(state: dict[str, Any], kind: str, body: str) -> None:
    normalize_user_state(state)
    game = state.get("current_game")
    if not game:
        return
    state["current_materials"][kind] = body
    state["current_materials"]["fingerprint"] = game_fingerprint(game)
    legacy_fields = {"cards": "last_cards", "worksheet": "last_worksheet", "pack": "last_mini_pack"}
    state[legacy_fields[kind]] = body
    state["material_cache_fingerprint"] = state["current_materials"]["fingerprint"]


def start_new_game(user_id: int) -> None:
    with USER_STATES_LOCK:
        USER_STATES[user_id] = new_user_state()


def build_summary(state: dict[str, Any]) -> str:
    return f"""🧪 Собираю игру...

Возраст: {state['age']}
Уровень: {state['level']}
Тема: {state['topic']}
Фокус: {state['skill']}
Время: {state['duration']}

🦊 Добавляю игровую механику и Fox Twist..."""


def build_choice_keyboard(labels: list[str]) -> str:
    keyboard = VkKeyboard(one_time=True)
    for index, label in enumerate(labels):
        keyboard.add_button(label, color=VkKeyboardColor.PRIMARY)
        if index % 2 == 1 and index < len(labels) - 1:
            keyboard.add_line()
    return keyboard.get_keyboard()


def build_level_keyboard() -> str:
    return build_choice_keyboard(["A1", "A2", "B1", "B2"])


def build_skill_keyboard() -> str:
    return build_choice_keyboard(["Speaking", "Vocabulary", "Grammar", "Reading", "Listening"])


def build_duration_keyboard() -> str:
    return build_choice_keyboard(["5 минут", "10 минут", "15 минут", "20 минут"])


def empty_keyboard() -> str:
    return VkKeyboard.get_empty_keyboard()


def _atomic_write_saved_games(data: dict[str, list[dict[str, Any]]]) -> None:
    SAVED_GAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = SAVED_GAMES_PATH.with_name(f".{SAVED_GAMES_PATH.name}.{uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, SAVED_GAMES_PATH)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _backup_corrupt_saved_games() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = SAVED_GAMES_PATH.with_name(
        f"{SAVED_GAMES_PATH.stem}.corrupt-{timestamp}-{uuid4().hex[:8]}{SAVED_GAMES_PATH.suffix}"
    )
    shutil.copy2(SAVED_GAMES_PATH, backup_path)
    return backup_path


def _load_saved_games_unlocked() -> dict[str, list[dict[str, Any]]]:
    if not SAVED_GAMES_PATH.exists():
        _atomic_write_saved_games({})
        return {}
    try:
        raw = json.loads(SAVED_GAMES_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or any(
            not isinstance(user_id, str) or not isinstance(games, list)
            for user_id, games in raw.items()
        ):
            raise ValueError("invalid saved games structure")
        migrated = False
        for games in raw.values():
            for game in games:
                if not isinstance(game, dict):
                    raise ValueError("invalid saved game record")
                if "favorite" not in game:
                    game["favorite"] = False
                    migrated = True
                else:
                    normalized_favorite = bool(game["favorite"])
                    if game["favorite"] is not normalized_favorite:
                        game["favorite"] = normalized_favorite
                        migrated = True
                if "last_used" not in game:
                    game["last_used"] = None
                    migrated = True
        if migrated:
            _atomic_write_saved_games(raw)
        return raw
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        try:
            _backup_corrupt_saved_games()
            _atomic_write_saved_games({})
        except OSError as backup_error:
            print(f"[COLLECTION ERROR] stage=recovery error={short_error(backup_error)}")
            return {}
        print(f"[COLLECTION ERROR] stage=load error={short_error(error)} recovered=true")
        return {}


def load_saved_games() -> dict[str, list[dict[str, Any]]]:
    with SAVED_GAMES_LOCK:
        return deepcopy(_load_saved_games_unlocked())


def ensure_saved_games_file() -> None:
    load_saved_games()


def game_fingerprint(game: dict[str, Any]) -> str:
    fields = {
        "title": game.get("title", ""),
        "mission": game.get("mission", ""),
        "how_to_play": game.get("how_to_play", []),
        "fox_twist": game.get("fox_twist", ""),
        "how_to_win": game.get("how_to_win", ""),
    }

    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return " ".join(str(value).casefold().split())

    return json.dumps({key: normalize(value) for key, value in fields.items()}, sort_keys=True)


def save_user_game(user_id: int, state: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    normalize_user_state(state)
    game = state.get("current_game")
    if not game:
        return "missing", None
    with SAVED_GAMES_LOCK:
        data = _load_saved_games_unlocked()
        user_key = str(user_id)
        games = data.setdefault(user_key, [])
        fingerprint = game_fingerprint(game)
        duplicate = next((saved for saved in games if game_fingerprint(saved) == fingerprint), None)
        if duplicate is not None:
            current_materials = state.get("current_materials", {})
            if current_materials.get("fingerprint") == fingerprint:
                stored_materials = duplicate.setdefault("materials", {})
                for key in ("cards", "worksheet", "pack"):
                    if current_materials.get(key):
                        stored_materials[key] = deepcopy(current_materials[key])
                stored_materials["fingerprint"] = fingerprint
                _atomic_write_saved_games(data)
            return "duplicate", deepcopy(duplicate)
        if len(games) >= 20:
            return "limit", None
        record = {
            "id": f"game_{uuid4().hex}",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "title": game["title"],
            "age": state.get("age"),
            "level": state.get("level"),
            "topic": state.get("topic"),
            "skill": state.get("skill"),
            "duration": state.get("duration"),
            "mission": game["mission"],
            "how_to_play": list(game["how_to_play"]),
            "english_toolkit": list(game["english_toolkit"]),
            "fox_twist": game["fox_twist"],
            "how_to_win": game["how_to_win"],
            "game_type": state.get("current_game_type") or detect_game_type(game),
            "favorite": False,
            "last_used": None,
            "materials": {
                key: deepcopy(state["current_materials"].get(key))
                for key in ("fingerprint", "cards", "worksheet", "pack")
            },
        }
        games.append(record)
        _atomic_write_saved_games(data)
        return "saved", deepcopy(record)


def get_user_saved_games(user_id: int) -> list[dict[str, Any]]:
    data = load_saved_games()
    return deepcopy(data.get(str(user_id), []))


def search_user_saved_games(user_id: int, query: str) -> list[dict[str, Any]]:
    needle = " ".join(query.casefold().split())
    if not needle:
        return []
    matches = [
        game
        for game in reversed(get_user_saved_games(user_id))
        if needle in str(game.get("title") or "").casefold()
        or needle in str(game.get("topic") or "").casefold()
    ]
    return matches[:10]


def filter_user_saved_games(user_id: int, field: str, value: str) -> list[dict[str, Any]]:
    if field not in {"age", "level", "topic", "skill"}:
        return []
    expected = " ".join(value.casefold().split())
    matches = [
        game
        for game in reversed(get_user_saved_games(user_id))
        if " ".join(str(game.get(field) or "").casefold().split()) == expected
    ]
    return matches[:10]


def get_favorite_saved_games(user_id: int) -> list[dict[str, Any]]:
    return [game for game in reversed(get_user_saved_games(user_id)) if game.get("favorite", False)][:10]


def _last_used_sort_key(game: dict[str, Any]) -> datetime:
    value = game.get("last_used")
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def get_recent_saved_games(user_id: int) -> list[dict[str, Any]]:
    used = [game for game in get_user_saved_games(user_id) if game.get("last_used")]
    return sorted(used, key=_last_used_sort_key, reverse=True)[:10]


def set_saved_game_favorite(user_id: int, game_id: str | None, favorite: bool) -> dict[str, Any] | None:
    if not game_id:
        return None
    with SAVED_GAMES_LOCK:
        data = _load_saved_games_unlocked()
        game = next(
            (item for item in data.get(str(user_id), []) if item.get("id") == game_id),
            None,
        )
        if game is None:
            return None
        game["favorite"] = bool(favorite)
        _atomic_write_saved_games(data)
        return deepcopy(game)


def mark_saved_game_used(user_id: int, game_id: str | None) -> dict[str, Any] | None:
    if not game_id:
        return None
    with SAVED_GAMES_LOCK:
        data = _load_saved_games_unlocked()
        game = next(
            (item for item in data.get(str(user_id), []) if item.get("id") == game_id),
            None,
        )
        if game is None:
            return None
        game["last_used"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_saved_games(data)
        return deepcopy(game)


def get_saved_game(user_id: int, game_id: str | None) -> dict[str, Any] | None:
    if not game_id:
        return None
    return next(
        (game for game in get_user_saved_games(user_id) if game.get("id") == game_id),
        None,
    )


def delete_user_saved_game(user_id: int, game_id: str | None) -> bool:
    if not game_id:
        return False
    with SAVED_GAMES_LOCK:
        data = _load_saved_games_unlocked()
        user_key = str(user_id)
        games = data.get(user_key, [])
        remaining = [game for game in games if game.get("id") != game_id]
        if len(remaining) == len(games):
            return False
        if remaining:
            data[user_key] = remaining
        else:
            data.pop(user_key, None)
        _atomic_write_saved_games(data)
        return True


def build_main_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    rows = [
        [
            ("📦 Материалы", VkKeyboardColor.PRIMARY),
            ("💾 Сохранить", VkKeyboardColor.POSITIVE),
        ],
        [
            ("🎲 Ещё вариант", VkKeyboardColor.PRIMARY),
            ("🧠 Усложнить", VkKeyboardColor.NEGATIVE),
        ],
        [
            ("⚡ Без подготовки", VkKeyboardColor.SECONDARY),
            ("✨ Удиви меня", VkKeyboardColor.PRIMARY),
        ],
        [
            ("🆕 Новая игра", VkKeyboardColor.SECONDARY),
        ],
    ]
    for row_index, row in enumerate(rows):
        for label, color in row:
            keyboard.add_button(label, color=color)
        if row_index < len(rows) - 1:
            keyboard.add_line()
    return keyboard.get_keyboard()


def build_material_menu_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🎴 Game Cards", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📝 Player Worksheet", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🦊 Teacher Mini Pack", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("📚 Весь комплект", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("↩️ К игре", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_material_missing_game_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📚 Моя коллекция", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🆕 Новая игра", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_material_result_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🧰 Другой материал", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("📚 Моя коллекция", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("↩ К игре", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🆕 Новая игра", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_pdf_result_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🖨 Сделать ещё раз", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🧰 Другой материал", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("📚 Моя коллекция", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("↩ К игре", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🆕 Новая игра", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_collection_keyboard(
    games: list[dict[str, Any]] | int,
    management: bool = False,
    back_label: str = "↩️ Назад",
    show_tools: bool = True,
    filter_active: bool = False,
) -> str:
    keyboard = VkKeyboard(one_time=False)
    if isinstance(games, int):
        count = games
        titles = [str(index + 1) for index in range(count)]
    else:
        count = len(games)
        titles = []
        for index, game in enumerate(games, 1):
            title = " ".join(str(game.get("title") or "Без названия").split())
            if len(title) > 28:
                title = enforce_preview_limit(title, 27) or title[:27]
                title += "…"
            titles.append(f"{index}. {title}")
    numeric_limit = 9 if management else (5 if show_tools else 8)
    visible_buttons = min(count, numeric_limit)
    for index in range(visible_buttons):
        keyboard.add_button(titles[index], color=VkKeyboardColor.PRIMARY)
        if index < visible_buttons - 1:
            keyboard.add_line()
    if visible_buttons:
        keyboard.add_line()
    if management:
        keyboard.add_button(back_label, color=VkKeyboardColor.SECONDARY)
        return keyboard.get_keyboard()
    if show_tools:
        keyboard.add_button("🔎 Поиск", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button(
            "❌ Сбросить фильтр" if filter_active else "🎯 Фильтры",
            color=VkKeyboardColor.NEGATIVE if filter_active else VkKeyboardColor.PRIMARY,
        )
        keyboard.add_line()
        keyboard.add_button("⭐ Избранное", color=VkKeyboardColor.POSITIVE)
        keyboard.add_button("🕘 Недавние", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
    keyboard.add_button(back_label, color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_collection_limit_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🗑 Управлять коллекцией", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("↩ Оставить как есть", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_saved_game_keyboard(favorite: bool = False) -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("▶️ Использовать", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("📦 Материалы", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    favorite_label = "☆ Убрать из избранного" if favorite else "⭐ В избранное"
    keyboard.add_button(favorite_label, color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🗑 Удалить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("📚 К коллекции", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🆕 Новая игра", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_collection_back_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📚 К коллекции", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("↩️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_filter_fields_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("age", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("level", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("topic", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("skill", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("❌ Сбросить фильтр", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("↩️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_filter_values_keyboard(values: list[str]) -> str:
    keyboard = VkKeyboard(one_time=False)
    for index, value in enumerate(values[:8]):
        keyboard.add_button(value, color=VkKeyboardColor.PRIMARY)
        if index < min(len(values), 8) - 1:
            keyboard.add_line()
    if values:
        keyboard.add_line()
    keyboard.add_button("❌ Сбросить фильтр", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("↩️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_saved_confirmation_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📚 Моя коллекция", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📦 Материалы", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🆕 Новая игра", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def build_delete_confirmation_keyboard() -> str:
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✅ Да, удалить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("↩ Оставить", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def format_collection(
    games: list[dict[str, Any]],
    management: bool = False,
    heading: str | None = None,
) -> str:
    heading = heading or ("📚 УПРАВЛЕНИЕ КОЛЛЕКЦИЕЙ" if management else "📚 МОЯ КОЛЛЕКЦИЯ")
    lines = [heading, ""]
    if not management:
        lines.extend(["🦊 Здесь живут твои любимые игровые идеи.", ""])
    for index, game in enumerate(games, 1):
        favorite = " ⭐" if game.get("favorite", False) else ""
        lines.append(f"{index}. {game.get('title', 'Без названия')}{favorite}")
        if not management:
            lines.append(
                f"   {game.get('topic') or 'Без темы'} • {game.get('level') or '—'} • "
                f"{game.get('duration') or '—'}"
            )
            lines.append("")
    lines.append("Какую игру удалить?" if management else "Выбери номер игры:")
    return "\n".join(lines)


def collection_screen(
    user_id: int,
    state: dict[str, Any],
    management: bool = False,
    games: list[dict[str, Any]] | None = None,
    mode: str | None = None,
    heading: str | None = None,
) -> tuple[list[str], str]:
    games = list(reversed(get_user_saved_games(user_id)))[:10] if games is None else games[:10]
    state["material_mode"] = None
    state["collection_mode"] = mode or ("manage" if management else "list")
    state["selected_saved_game_id"] = None
    state["delete_return_mode"] = None
    state["collection_visible_ids"] = [game["id"] for game in games]
    print(f"[COLLECTION OPEN] user_id={user_id} count={len(games)} mode={state['collection_mode']}")
    if not games:
        if state["collection_mode"] == "list":
            empty_text = (
                "📚 Твоя коллекция пока пустая.\n\n"
                "🦊 Создай новую игру и сохрани ту, которую захочется повторить."
            )
        else:
            empty_text = f"{heading or '📚 МОЯ КОЛЛЕКЦИЯ'}\n\n🦊 Здесь пока нет подходящих игр."
        return [
            empty_text
        ], build_collection_keyboard(
            [], management, filter_active=state["collection_mode"] == "filter_results"
        )
    return [format_collection(games, management, heading)], build_collection_keyboard(
        games, management, filter_active=state["collection_mode"] == "filter_results"
    )


def saved_game_screen(user_id: int, state: dict[str, Any], game: dict[str, Any]) -> tuple[list[str], str]:
    activate_saved_game(state, game, keep_collection=True)
    state["collection_mode"] = "view"
    state["selected_saved_game_id"] = game["id"]
    state["delete_return_mode"] = None
    print(f"[SAVED GAME OPEN] user_id={user_id}")
    return [format_game_message(game, state, prefix="📚 SAVED GAME")], build_saved_game_keyboard(
        bool(game.get("favorite", False))
    )


def activate_saved_game(
    state: dict[str, Any],
    game: dict[str, Any],
    keep_collection: bool = False,
) -> None:
    normalize_user_state(state)
    for field in ("age", "level", "topic", "skill", "duration"):
        set_current_parameter(state, field, game.get(field))
    current_game = {
        key: deepcopy(game[key])
        for key in ("title", "mission", "how_to_play", "english_toolkit", "fox_twist", "how_to_win")
    }
    set_current_game(state, current_game, game.get("game_type"))
    saved_materials = game.get("materials") if isinstance(game.get("materials"), dict) else {}
    clear_current_materials(state)
    for kind in ("cards", "worksheet", "pack"):
        body = saved_materials.get(kind)
        if isinstance(body, str) and body:
            cache_material(state, kind, body)
    state["current_step"] = "ready"
    state["material_mode"] = None
    if not keep_collection:
        state["collection_mode"] = None
        state["selected_saved_game_id"] = None
        state["collection_visible_ids"] = []
        state["delete_return_mode"] = None


def selected_visible_game(user_id: int, state: dict[str, Any], text: str) -> dict[str, Any] | None:
    match = re.match(r"^(\d+)(?:\.|\s|$)", text.strip())
    if not match:
        return None
    index = int(match.group(1)) - 1
    visible_ids = state.get("collection_visible_ids", [])
    if index < 0 or index >= len(visible_ids):
        return None
    return get_saved_game(user_id, visible_ids[index])


def material_menu_screen(user_id: int, state: dict[str, Any]) -> tuple[list[str], str]:
    normalize_user_state(state)
    game = state.get("current_game")
    if not game:
        state["material_mode"] = None
        return ["🦊 Сначала создай или выбери игру."], build_material_missing_game_keyboard()
    state["collection_mode"] = None
    state["material_mode"] = "menu"
    print(f"[MATERIAL MENU] user_id={user_id}")
    return [
        f"📦 МАТЕРИАЛЫ\n\n🎲 {game['title']}\n\nЧто открыть?"
    ], build_material_menu_keyboard()


def back_to_game_screen(state: dict[str, Any]) -> tuple[list[str], str]:
    state["material_mode"] = None
    normalize_user_state(state)
    game = state.get("current_game")
    if not game:
        return ["🦊 Сначала создай или выбери игру."], build_material_missing_game_keyboard()
    return [format_game_message(game, state)], build_main_keyboard()


def handle_user_text(user_id: int, text: str) -> tuple[list[str], str | None, str | None]:
    text = text.strip()
    normalized = text.casefold()
    if normalized in START_MESSAGES:
        start_new_game(user_id)
        return [START_REPLY], None, empty_keyboard()
    if normalized in NEW_GAME_MESSAGES:
        start_new_game(user_id)
        return [NEW_GAME_REPLY], None, empty_keyboard()

    state = USER_STATES.get(user_id)
    state_was_missing = state is None
    if state_was_missing:
        state = new_user_state()
        USER_STATES[user_id] = state
    normalize_user_state(state)
    mode = state.get("collection_mode")

    if normalized in SAVE_GAME_MESSAGES:
        status, saved = save_user_game(user_id, state)
        print(f"[SAVE GAME] user_id={user_id} status={status}")
        if status == "missing":
            return ["🦊 Сначала создай игру — потом я смогу её сохранить."], None, None
        if status == "duplicate":
            return ["🦊 Эта игра уже в твоей коллекции."], None, build_saved_confirmation_keyboard()
        if status == "limit":
            state["collection_mode"] = "list"
            return [
                "📚 В коллекции уже 20 игр.\n\n🦊 Освободим место для новой?"
            ], None, build_collection_limit_keyboard()
        return [
            f"""💾 СОХРАНЕНО!

🎲 {saved['title']}
{saved.get('topic') or 'Без темы'} • {saved.get('level') or '—'} • {saved.get('duration') or '—'}

🦊 Игра уже в твоей коллекции."""
        ], None, build_saved_confirmation_keyboard()

    if normalized in COLLECTION_MESSAGES or normalized == "📚 к коллекции":
        state["collection_query"] = None
        state["collection_filter"] = None
        state["collection_filter_field"] = None
        replies, keyboard = collection_screen(user_id, state)
        return replies, None, keyboard

    if normalized in COLLECTION_SEARCH_MESSAGES:
        state["collection_mode"] = "search_query"
        state["collection_query"] = None
        return [
            "🔎 ПОИСК\n\nНапиши название игры или topic."
        ], None, build_collection_back_keyboard()

    if normalized in COLLECTION_FILTER_MESSAGES:
        state["collection_mode"] = "filter_field"
        state["collection_filter_field"] = None
        return [
            "🎯 ФИЛЬТРЫ\n\nВыбери один параметр: age, level, topic или skill."
        ], None, build_filter_fields_keyboard()

    if normalized in COLLECTION_FAVORITES_MESSAGES:
        replies, keyboard = collection_screen(
            user_id,
            state,
            games=get_favorite_saved_games(user_id),
            mode="favorites",
            heading="⭐ ИЗБРАННОЕ",
        )
        return replies, None, keyboard

    if normalized in COLLECTION_RECENT_MESSAGES:
        replies, keyboard = collection_screen(
            user_id,
            state,
            games=get_recent_saved_games(user_id),
            mode="recent",
            heading="🕘 НЕДАВНИЕ",
        )
        return replies, None, keyboard

    if normalized in RESET_FILTER_MESSAGES:
        state["collection_filter"] = None
        state["collection_filter_field"] = None
        replies, keyboard = collection_screen(user_id, state)
        return ["❌ Фильтр сброшен.", *replies], None, keyboard

    if mode == "search_query" and normalized not in BACK_MESSAGES:
        state["collection_query"] = text
        games = search_user_saved_games(user_id, text)
        replies, keyboard = collection_screen(
            user_id,
            state,
            games=games,
            mode="search_results",
            heading=f"🔎 РЕЗУЛЬТАТЫ: {text}",
        )
        return replies, None, keyboard

    if mode == "filter_field" and normalized in {"age", "level", "topic", "skill"}:
        state["collection_mode"] = "filter_value"
        state["collection_filter_field"] = normalized
        values_by_key: dict[str, str] = {}
        for game in get_user_saved_games(user_id):
            value = str(game.get(normalized) or "").strip()
            if value:
                values_by_key.setdefault(value.casefold(), value)
        values = sorted(values_by_key.values(), key=str.casefold)
        options = "\n".join(f"• {value}" for value in values) or "• Нет доступных значений"
        return [
            f"🎯 ФИЛЬТР: {normalized}\n\nВыбери или напиши значение:\n{options}"
        ], None, build_filter_values_keyboard(values)

    if mode == "filter_value" and normalized not in BACK_MESSAGES:
        field = state.get("collection_filter_field")
        if field not in {"age", "level", "topic", "skill"}:
            replies, keyboard = collection_screen(user_id, state)
            return ["🦊 Не удалось применить фильтр.", *replies], None, keyboard
        state["collection_filter"] = {"field": field, "value": text}
        games = filter_user_saved_games(user_id, field, text)
        replies, keyboard = collection_screen(
            user_id,
            state,
            games=games,
            mode="filter_results",
            heading=f"🎯 {field}: {text}",
        )
        return replies, None, keyboard

    if normalized in ADD_FAVORITE_MESSAGES | REMOVE_FAVORITE_MESSAGES and mode == "view":
        favorite = normalized in ADD_FAVORITE_MESSAGES
        game = set_saved_game_favorite(user_id, state.get("selected_saved_game_id"), favorite)
        if game is None:
            replies, keyboard = collection_screen(user_id, state)
            return ["🦊 Не удалось найти эту игру.", *replies], None, keyboard
        replies, keyboard = saved_game_screen(user_id, state, game)
        status = "⭐ Добавлено в избранное." if favorite else "☆ Убрано из избранного."
        return [status, *replies], None, keyboard

    if normalized in MANAGE_COLLECTION_MESSAGES:
        replies, keyboard = collection_screen(user_id, state, management=True)
        return replies, None, keyboard

    if normalized in MATERIAL_MENU_MESSAGES or normalized in OTHER_MATERIAL_MESSAGES:
        replies, keyboard = material_menu_screen(user_id, state)
        return replies, None, keyboard

    if normalized in PRINTABLE_COMMANDS:
        if not state.get("current_game"):
            return ["🦊 Сначала создай или выбери игру."], None, build_material_missing_game_keyboard()
        state["collection_mode"] = None
        cached_attachment = state["current_materials"].get("pdf_attachment")
        cached_path = state["current_materials"].get("pdf_path")
        if cached_attachment or (cached_path and Path(cached_path).is_file()):
            state["material_mode"] = "result"
            return [], "cached_pdf", empty_keyboard()
        state["material_mode"] = "generating"
        return [PRINTABLE_PROGRESS], "printable", empty_keyboard()

    material_kind = MATERIAL_COMMANDS.get(normalized)
    if material_kind:
        if not state.get("current_game"):
            return ["🦊 Сначала создай или выбери игру."], None, build_material_missing_game_keyboard()
        state["collection_mode"] = None
        cached_body = get_cached_material(state, material_kind)
        if cached_body:
            state["material_mode"] = "result"
            material_text = format_material_output(material_kind, state, cached_body)
            return [*split_vk_text(material_text), "🦊 Материал уже готов — открываю сохранённую версию."], None, build_material_result_keyboard()
        state["material_mode"] = "generating"
        return [MATERIAL_PROGRESS[material_kind]], f"material:{material_kind}", empty_keyboard()

    if state_was_missing:
        return [START_REPLY], None, empty_keyboard()

    mode = state.get("collection_mode")
    material_mode = state.get("material_mode")

    if normalized in BACK_TO_GAME_MESSAGES or (
        normalized in BACK_MESSAGES and material_mode in {"menu", "result", "generating"}
    ):
        replies, keyboard = back_to_game_screen(state)
        return replies, None, keyboard

    if normalized in BACK_MESSAGES:
        if mode == "view":
            replies, keyboard = collection_screen(user_id, state)
            return replies, None, keyboard
        if mode == "confirm_delete":
            game = get_saved_game(user_id, state.get("selected_saved_game_id"))
            if state.get("delete_return_mode") == "manage" or game is None:
                replies, keyboard = collection_screen(user_id, state, management=True)
            else:
                replies, keyboard = saved_game_screen(user_id, state, game)
            return replies, None, keyboard
        if mode == "manage":
            replies, keyboard = collection_screen(user_id, state)
            return replies, None, keyboard
        if mode in {
            "search_query",
            "search_results",
            "filter_field",
            "filter_value",
            "filter_results",
            "favorites",
            "recent",
        }:
            replies, keyboard = collection_screen(user_id, state)
            return replies, None, keyboard
        state["collection_mode"] = None
        state["selected_saved_game_id"] = None
        state["collection_visible_ids"] = []
        return ["↩ Возвращаюсь к игре."], None, build_main_keyboard()

    if normalized in USE_SAVED_MESSAGES and mode == "view":
        game = mark_saved_game_used(user_id, state.get("selected_saved_game_id"))
        if game is None:
            replies, keyboard = collection_screen(user_id, state)
            return ["🦊 Не удалось найти эту игру.", *replies], None, keyboard
        activate_saved_game(state, game)
        return ["▶ Игра выбрана. Теперь её можно изменить или получить новый вариант."], None, build_main_keyboard()

    if normalized in DELETE_SAVED_MESSAGES and mode == "view":
        game = get_saved_game(user_id, state.get("selected_saved_game_id"))
        if game is None:
            replies, keyboard = collection_screen(user_id, state)
            return ["🦊 Не удалось найти эту игру.", *replies], None, keyboard
        state["collection_mode"] = "confirm_delete"
        state["delete_return_mode"] = "view"
        return [
            f"🗑 Удалить игру\n«{game['title']}»\nиз коллекции?"
        ], None, build_delete_confirmation_keyboard()

    if normalized in CONFIRM_DELETE_MESSAGES and mode == "confirm_delete":
        deleted = delete_user_saved_game(user_id, state.get("selected_saved_game_id"))
        print(f"[DELETE GAME] user_id={user_id} deleted={str(deleted).lower()}")
        replies, keyboard = collection_screen(user_id, state)
        prefix = "🗑 Игра удалена." if deleted else "🦊 Игра уже отсутствует в коллекции."
        return [prefix, *replies], None, keyboard

    if normalized in CANCEL_MESSAGES and mode == "confirm_delete":
        game = get_saved_game(user_id, state.get("selected_saved_game_id"))
        if state.get("delete_return_mode") == "manage" or game is None:
            replies, keyboard = collection_screen(user_id, state, management=True)
        else:
            replies, keyboard = saved_game_screen(user_id, state, game)
        return replies, None, keyboard

    collection_list_modes = {
        "list",
        "manage",
        "search_results",
        "filter_results",
        "favorites",
        "recent",
    }
    if mode in collection_list_modes:
        game = selected_visible_game(user_id, state, text)
        if game is None:
            visible_games = [
                saved
                for game_id in state.get("collection_visible_ids", [])
                if (saved := get_saved_game(user_id, game_id)) is not None
            ]
            return ["🦊 Выбери игру из списка."], None, build_collection_keyboard(
                visible_games, mode == "manage"
            )
        if mode == "manage":
            state["collection_mode"] = "confirm_delete"
            state["selected_saved_game_id"] = game["id"]
            state["delete_return_mode"] = "manage"
            return [
                f"🗑 Удалить игру\n«{game['title']}»\nиз коллекции?"
            ], None, build_delete_confirmation_keyboard()
        replies, keyboard = saved_game_screen(user_id, state, game)
        return replies, None, keyboard

    if mode in collection_list_modes | {"view", "confirm_delete", "search_query", "filter_field", "filter_value"}:
        if mode == "confirm_delete":
            return ["🦊 Удали игру или оставь её в коллекции."], None, build_delete_confirmation_keyboard()
        if mode == "view":
            game = get_saved_game(user_id, state.get("selected_saved_game_id"))
            return ["🦊 Выбери действие для сохранённой игры."], None, build_saved_game_keyboard(
                bool(game and game.get("favorite", False))
            )
        if mode == "search_query":
            return ["🔎 Напиши название игры или topic."], None, build_collection_back_keyboard()
        if mode == "filter_field":
            return ["🎯 Выбери age, level, topic или skill."], None, build_filter_fields_keyboard()
        if mode == "filter_value":
            return ["🎯 Выбери или напиши значение фильтра."], None, build_filter_values_keyboard([])
        visible_games = [
            saved
            for game_id in state.get("collection_visible_ids", [])
            if (saved := get_saved_game(user_id, game_id)) is not None
        ]
        return ["🦊 Выбери игру из списка."], None, build_collection_keyboard(
            visible_games, mode == "manage"
        )

    variation = VARIATION_COMMANDS.get(normalized)
    if variation:
        if not state.get("current_game"):
            return ["🦊 Сначала закончим новую игру — ответь на текущий вопрос."], None, None
        return [COMMAND_PROGRESS[variation]], variation, empty_keyboard()
    if normalized in IGNORED_CAROUSEL_ACTIONS:
        return [], None, None

    current_step = state["current_step"]
    transitions = {
        "age": ("age", "level", LEVEL_REPLY, build_level_keyboard()),
        "level": ("level", "topic", TOPIC_REPLY, empty_keyboard()),
        "topic": ("topic", "skill", SKILL_REPLY, build_skill_keyboard()),
        "skill": ("skill", "duration", TIME_REPLY, build_duration_keyboard()),
    }
    if current_step in transitions:
        field, next_step, reply, keyboard = transitions[current_step]
        set_current_parameter(state, field, text)
        state["current_step"] = next_step
        return [reply], None, keyboard
    if current_step == "duration":
        set_current_parameter(state, "duration", text)
        state["current_step"] = "ready"
        return [build_summary(state)], "base", empty_keyboard()

    return ["🦊 Выбери действие на клавиатуре или начни новую игру."], None, build_main_keyboard()


def clean_vk_text(text: str) -> str:
    text = re.sub(r"(?m)^\s*[-–—*]\s+", "• ", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    return text.replace("**", "").replace("*", "").replace("#", "").replace("`", "").strip()


def build_generation_request(state: dict[str, Any], variation: str) -> str:
    normalize_user_state(state)
    prompts = {
        "base": "Создай новую игру по параметрам.",
        "another": "Сохрани все параметры, но создай совершенно другую игровую механику. Тип и основной игровой цикл предыдущей игры повторять запрещено. Выбери другой формат из mission, auction, hidden role, escape, team challenge, information gap, movement, bluff или collect clues.",
        "active": "Сохрани основную идею текущей игры, но добавь движение по классу, поиск, смену партнёров, команды, таймер и физическую динамику.",
        "no_prep": "Сохрани текущую игру и параметры, но сделай версию без печати, без карточек и без раздаточных материалов. Используй только доску, речь учеников и телефон учителя. Механика должна запускаться сразу.",
        "harder": "Сохрани возраст, уровень, тему и основную механику текущей игры. Добавь больше speaking, убери часть подсказок, введи дополнительный twist и передай ученикам больше самостоятельных решений. Не повышай CEFR и не меняй параметры.",
        "surprise": "Сохрани параметры и создай необычную, но проводимую механику. Обязательно сочетай минимум два элемента из secret roles, mystery, movement, team challenge, information gap и неожиданный twist. Не используй bingo, quiz и обычную board game.",
    }
    request = f"""Возраст: {state['age']}
Уровень: {state['level']}
Тема: {state['topic']}
Фокус: {state['skill']}
Время: {state['duration']}
Задача: {prompts[variation]}"""
    if variation != "base" and state.get("current_game"):
        previous = json.dumps(state["current_game"], ensure_ascii=False)
        request += f"\nПредыдущая игра: {previous}"
        if variation == "another" and state.get("current_game_type"):
            request += f"\nТип предыдущей механики, который нельзя повторять: {state['current_game_type']}"
    return request


def extract_json_object(raw_text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", raw_text):
        try:
            value, _ = decoder.raw_decode(raw_text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("JSON object not found")


def validate_game(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")

    scalar_fields = ("title", "mission", "fox_twist", "how_to_win")
    for field in scalar_fields:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"Invalid field: {field}")
        data[field] = clean_vk_text(data[field])

    list_limits = {"how_to_play": (3, 4), "english_toolkit": (4, 6)}
    for field, (minimum, maximum) in list_limits.items():
        value = data.get(field)
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            raise ValueError(f"Invalid field: {field}")
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError(f"Invalid items: {field}")
        data[field] = [clean_vk_text(item) for item in value]
    return data


def fallback_game(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"The Secret {state['topic']} Hunt",
        "mission": "Complete the secret mission by collecting clues in English.",
        "how_to_play": [
            "Split into teams.",
            "Earn each clue with an English phrase.",
            "Exchange information and solve the mystery.",
            "Finish the mission before time runs out.",
        ],
        "english_toolkit": [
            "Can I have a clue?",
            "What did you find?",
            "I think the answer is...",
            "Let's try this!",
        ],
        "fox_twist": "During the last two minutes, one clue secretly becomes false.",
        "how_to_win": "The first team to solve the mission and explain it in English wins.",
    }


def detect_game_type(game: dict[str, Any]) -> str:
    text = " ".join(
        [
            game.get("title", ""),
            game.get("mission", ""),
            " ".join(game.get("how_to_play", [])),
            game.get("fox_twist", ""),
        ]
    ).casefold()
    mechanics = (
        "bingo",
        "quiz",
        "auction",
        "detective",
        "escape",
        "hidden role",
        "spy",
        "mafia",
        "impostor",
        "board game",
        "treasure hunt",
        "secret mission",
    )
    return next((mechanic for mechanic in mechanics if mechanic in text), clean_vk_text(game.get("title", "game")))


def generate_game(
    session: requests.Session,
    api_key: str,
    folder_id: str,
    state: dict[str, Any],
    variation: str,
) -> dict[str, Any]:
    response = session.post(
        YANDEX_COMPLETION_URL,
        headers={"Authorization": f"Api-Key {api_key}"},
        json={
            "modelUri": f"gpt://{folder_id}/yandexgpt/latest",
            "completionOptions": {"stream": False, "temperature": 0.8, "maxTokens": "1800"},
            "messages": [
                {"role": "system", "text": AI_INSTRUCTIONS},
                {"role": "user", "text": build_generation_request(state, variation)},
            ],
        },
        timeout=(5, 30),
    )
    response.raise_for_status()
    raw_text = response.json()["result"]["alternatives"][0]["message"]["text"]
    try:
        game = validate_game(extract_json_object(raw_text))
        print("[JSON OK] fallback=false")
        return game
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"[JSON OK] fallback=true error={type(error).__name__}")
        return fallback_game(state)


def build_material_request(state: dict[str, Any], material_kind: str) -> str:
    normalize_user_state(state)
    tasks = {
        "cards": """Создай полный набор разных физических игровых карточек для игроков. Первая строка строго SET: X CARDS. Затем каждая карточка — отдельный блок без слова CARD: ROLE или TYPE + номер и максимум три короткие строки. Для A1 detective/Spy Hunt сделай строго SET: 6 CARDS: два SPY и четыре STUDENT; слово CIVILIAN и сложная лексика запрещены. SPY 1: Keep your secret.; Change one answer after 2 minutes.; Say: "No, I am not a spy." SPY 2: Keep your secret.; Change one answer after 2 minutes.; Say: "Yes, I am a student." STUDENT 1: Ask 2 classmates.; Listen carefully.; Find the spies. STUDENT 2: Answer the questions.; Watch for changes.; Find the spies. STUDENT 3: Ask simple questions.; Listen carefully.; Make your guess. STUDENT 4: Ask and answer.; Watch the other players.; Find the spies. Не добавляй инструкцию учителю или пересказ правил.""",
        "worksheet": """Создай плотный PLAYER WORKSHEET, напрямую встроенный в механику текущей игры. Дай минимум 7 основных activity blocks и отдельный финальный FOX CHALLENGE; если задания короткие, используй 8–9 блоков. Каждый основной заголовок начинай строго с TASK N — и короткого типа действия. Не добавляй общий заголовок, название игры или строку параметров — бот оформит их сам.

Сбалансируй controlled practice, semi-controlled practice, speaking/game use и финальное самостоятельное применение. Для A1 делай минимум 8 TASK, для остальных уровней — минимум 7. Последние 1–2 TASK должны прямо использоваться в механике игры. Для грамматики адаптивно используй build/order, short answers, choose the correct form, fix the mistake, complete, match, speak/report и final game result; не копируй эту последовательность механически для vocabulary, speaking, reading или functional language. Все practice items тренируют переданную тему; не подменяй целевую грамматику другой структурой.

Для detective-механики на A1 обязательно включи восемь конкретных функций и точный объём: TASK 1 — BUILD THE QUESTION: 5 jumbled-word items с символом / и answer line; TASK 2 — SHORT ANSWERS: 6 items, в каждой строке полностью написанный вопрос со знаком ? и место для short answer; TASK 3 — CHOOSE THE CORRECT FORM: 6 items; TASK 4 — FIX THE MISTAKE: 5 items; TASK 5 — COMPLETE THE SENTENCES: 5 items; TASK 6 — MATCH QUESTION + ANSWER: 4 pairs; TASK 7 — SPEAK AND REPORT: три компактные строки в формате Classmate N: Are you a student? ___ | He/She is ___.; TASK 8 — MY FINAL GUESS: один составной item с clue + guess + because. После него FOX CHALLENGE с 2 отдельными пронумерованными строками, в каждой собственное предложение или вопрос и answer line. Для A1 не используй CIVILIAN, SUSPECT, EVIDENCE, INVESTIGATE или STRATEGY.

Обязательный объём реальных языковых действий: A1 — 25–35, A2 — 25–40, B1 — 20–35, B2 — 15–30. Для A1 используй 8 TASK: в TASK 1–6 минимум по 4 отдельных действия, в TASK 7–8 минимум по 3, итого около 30. Считай отдельными действиями каждый выбор формы, вписанное слово, исправление, составленный вопрос, matched answer, реплику, вопрос партнёру или короткий ответ. Инструкции, заголовки и варианты ответа не считаются отдельными действиями. Для A1 используй короткие инструкции, знакомую лексику, мало письма и больше повторения. Для A2 добавь самостоятельный выбор, sentence building, speaking prompts, error correction и mini-dialogues. Для B1/B2 уменьши mechanical drill и добавь reasoning, information gap, strategy, paraphrasing, justification, freer speaking и mini-writing.

Внутри блоков печатай все stimulus items, варианты, sentence starters, маленькие таблицы, checkboxes ☐ и аккуратные answer lines ______. Каждое языковое действие выводи отдельной строкой с номером или checkbox, чтобы объём можно было проверить автоматически. Не ссылайся на внешние картинки или аудио. Закрой worksheet отдельным блоком FOX CHALLENGE: короткое, чуть более сложное самостоятельное действие с языком, а не обычное дополнительное упражнение.

Перед ответом проверь: минимум 7 TASK; нужное число языковых действий для CEFR; controlled practice; speaking/game task; последние задания связаны с механикой; короткие читаемые строки; FOX CHALLENGE присутствует. Если любой пункт не выполнен — пересобери worksheet до ответа.""",
        "pack": """Создай компактную teacher cheat sheet из ровно 9 блоков: START; SAY THIS; ENGLISH SUPPORT; TEACHER TIPS; FOX TWIST; IF TOO EASY; IF TOO HARD; AFTER THE GAME; QUICK CHECK — WHAT TO PREPARE. Для Spy Hunt A1 используй конкретные classroom actions. START: groups, secret cards, two spies, model 2–3 questions и Teacher Note о скрытых spy cards. SAY THIS: 4 готовые реплики и Teacher Tip: Say these lines with energy to build excitement. ENGLISH SUPPORT: 6 фраз I am/Are you/Yes/No. TEACHER TIPS: 8 действий про shy/weaker/stronger students, eye contact, full sentences, walk around/listen, fluency correction и delayed correction. FOX TWIST: after 2 minutes spies change one answer, реплика Something may change и new clues. IF TOO EASY: time limit, 2 questions per classmate, extra full sentence, remove one support prompt. IF TOO HARD: model together, 3 starters on board, pairs first, worksheet visible, one ready-made question. AFTER THE GAME: Who were the spies?; Which clues helped you?; one to be sentence; praise; correct 2–3 useful points. QUICK CHECK: Game cards; Player worksheet; Timer; Board markers; Optional reward / point tokens. Короткие строки, без общих советов.""",
    }
    game = state["current_game"]
    return f"""Возраст: {state.get('age')}
Уровень CEFR: {state.get('level')}
Тема: {state.get('topic')}
Навык: {state.get('skill')}
Время: {state.get('duration')}
Текущая игра: {json.dumps(game, ensure_ascii=False)}

Задача: {tasks[material_kind]}"""


def generate_material(
    session: requests.Session,
    api_key: str,
    folder_id: str,
    state: dict[str, Any],
    material_kind: str,
) -> str:
    normalize_user_state(state)
    request_text = build_material_request(state, material_kind)
    max_attempts = 5 if material_kind == "worksheet" else 4
    system_instructions = {
        "cards": CARDS_AI_INSTRUCTIONS,
        "worksheet": WORKSHEET_AI_INSTRUCTIONS,
        "pack": TEACHER_PACK_AI_INSTRUCTIONS,
    }[material_kind]
    for attempt in range(max_attempts):
        response = session.post(
            YANDEX_COMPLETION_URL,
            headers={"Authorization": f"Api-Key {api_key}"},
            json={
                "modelUri": f"gpt://{folder_id}/yandexgpt/latest",
                "completionOptions": {"stream": False, "temperature": 0.65, "maxTokens": "1800"},
                "messages": [
                    {
                        "role": "system",
                        "text": system_instructions,
                    },
                    {"role": "user", "text": request_text},
                ],
            },
            timeout=(5, 30),
        )
        response.raise_for_status()
        raw_text = response.json()["result"]["alternatives"][0]["message"]["text"]
        material = clean_vk_text(raw_text)
        if not material:
            raise ValueError("Empty material response")
        if material_kind == "pack":
            material = normalize_teacher_pack(material)
        game_type = str(state.get("current_game_type") or detect_game_type(state["current_game"]))
        level = str(state.get("level") or "")
        if material_kind == "worksheet":
            issues = worksheet_quality_issues(material, level, game_type)
        elif material_kind == "cards":
            issues = cards_quality_issues(material, level, game_type)
        else:
            issues = teacher_pack_quality_issues(material)
        if not issues:
            return material
        print(
            f"[MATERIAL QUALITY] kind={material_kind} attempt={attempt + 1} "
            f"issues={','.join(issues)}"
        )
        metric_note = ""
        if material_kind == "worksheet":
            metrics = worksheet_quality_metrics(material)
            metric_note = (
                f" Фактически: TASK={metrics['activity_blocks']}, "
                f"drill items={metrics['drill_items']}."
            )
        request_text = (
            build_material_request(state, material_kind)
            + "\n\nПредыдущий вариант не прошёл обязательную проверку: "
            + ", ".join(issues)
            + "."
            + metric_note
            + " Полностью пересобери материал и верни только исправленное тело."
        )
    raise ValueError(f"{material_kind} quality validation failed after rebuild")


def split_material_blocks(material: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    for chunk in re.split(r"\n\s*\n", material.strip()):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if lines:
            blocks.append((lines[0], lines[1:]))
    return blocks


def normalize_teacher_pack(material: str) -> str:
    required = (
        "START",
        "SAY THIS",
        "ENGLISH SUPPORT",
        "TEACHER TIPS",
        "FOX TWIST",
        "IF TOO EASY",
        "IF TOO HARD",
        "AFTER THE GAME",
        "QUICK CHECK",
    )
    normalized: list[tuple[str, list[str]]] = []
    for title, lines in split_material_blocks(material):
        clean_title = pdf_preview_text(title).upper()
        if any(heading in clean_title for heading in required):
            normalized.append((title, list(lines)))
        elif normalized:
            normalized[-1][1].extend([title, *lines])
    return "\n\n".join(
        "\n".join([title, *lines]).strip()
        for title, lines in normalized
    )


def cards_quality_issues(material: str, level: str, game_type: str) -> list[str]:
    blocks = split_material_blocks(material)
    set_match = re.search(r"(?i)\bSET:\s*(\d+)\s+CARDS?\b", material)
    announced = int(set_match.group(1)) if set_match else None
    cards = [(title, lines) for title, lines in blocks if not title.upper().startswith("SET:")]
    issues: list[str] = []
    if announced is None:
        issues.append("set_count_missing")
    if len(cards) < 6:
        issues.append("fewer_than_6_cards")
    if any(len(lines) < 2 or len(lines) > 3 for _, lines in cards):
        issues.append("card_text_not_2_to_3_lines")
    if level.upper() == "A1" and game_type == "detective":
        titles = [pdf_preview_text(title).upper() for title, _ in cards]
        if announced != 6 or len(cards) != 6:
            issues.append("a1_detective_requires_6_cards")
        if sum(title.startswith("SPY ") for title in titles) != 2:
            issues.append("requires_2_spy_cards")
        if sum(title.startswith("STUDENT ") for title in titles) != 4:
            issues.append("requires_4_student_cards")
        banned = (
            "civilian",
            "suspect",
            "identity detail",
            "evidence",
            "investigate",
            "strategy",
            "truthfully",
        )
        lowered = material.lower()
        found_banned = [word for word in banned if word in lowered]
        if found_banned:
            issues.append("forbidden_words_" + "_".join(word.replace(" ", "_") for word in found_banned))
        spy_blocks = [
            lines
            for title, lines in cards
            if pdf_preview_text(title).upper().startswith("SPY ")
        ]
        if any(not any("say:" in line.lower() for line in lines) for lines in spy_blocks):
            issues.append("each_spy_requires_ready_say_line")
        if any(not any("change" in line.lower() and "2 minutes" in line.lower() for line in lines) for lines in spy_blocks):
            issues.append("each_spy_requires_change_after_2_minutes")
    return issues


def teacher_pack_quality_issues(material: str) -> list[str]:
    required = (
        "START",
        "SAY THIS",
        "ENGLISH SUPPORT",
        "TEACHER TIPS",
        "FOX TWIST",
        "IF TOO EASY",
        "IF TOO HARD",
        "AFTER THE GAME",
        "QUICK CHECK",
    )
    titles = [pdf_preview_text(title).upper() for title, _ in split_material_blocks(material)]
    issues = [
        f"missing_{re.sub(r'[^a-z0-9]+', '_', heading.lower()).strip('_')}"
        for heading in required
        if not any(heading in title for title in titles)
    ]
    if len(titles) != 9:
        issues.append("teacher_pack_requires_9_blocks")
    lowered = material.lower()
    if "teacher note" not in lowered:
        issues.append("teacher_note_missing")
    if not any(word in lowered for word in ("shy", "weaker", "stronger", "strong students")):
        issues.append("learner_adaptation_missing")
    if not any(word in lowered for word in ("walk around", "monitor", "listen for")):
        issues.append("classroom_monitoring_missing")
    if not any(word in lowered for word in ("energy", "excitement")):
        issues.append("say_this_energy_tip_missing")
    if "worksheet" not in lowered:
        issues.append("preparation_worksheet_missing")
    if not all(word in lowered for word in ("timer", "board")):
        issues.append("preparation_timer_or_board_missing")
    if not any(word in lowered for word in ("practise in pairs", "practice in pairs", "round together")):
        issues.append("if_too_hard_pair_or_model_support_missing")
    if not re.search(r"(?i)who (?:were|are) the spies", material):
        issues.append("after_game_spy_question_missing")
    if not re.search(r"(?i)which clues", material):
        issues.append("after_game_clue_question_missing")
    return issues


def pdf_preview_text(value: str) -> str:
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", value)
    return re.sub(r"\s+", " ", text).strip()


def worksheet_quality_issues(material: str, level: str, game_type: str = "") -> list[str]:
    metrics = worksheet_quality_metrics(material)
    task_numbers = metrics["task_numbers"]
    action_lines = metrics["drill_items"]
    issues: list[str] = []
    minimum_tasks = 8 if level.upper() == "A1" else 7
    if len(task_numbers) < minimum_tasks:
        issues.append(f"fewer_than_{minimum_tasks}_tasks")
    if not metrics["has_fox_challenge"]:
        issues.append("fox_challenge_missing")

    action_range = {
        "A1": (25, 35),
        "A2": (25, 40),
        "B1": (20, 35),
        "B2": (15, 30),
    }.get(level.upper(), (20, 35))
    if level.upper() == "A1" and game_type == "detective":
        action_range = (25, 40)
    minimum_actions, maximum_actions = action_range
    if action_lines < minimum_actions:
        issues.append(f"drill_items_below_{minimum_actions}")
    elif action_lines > maximum_actions:
        issues.append(f"drill_items_above_{maximum_actions}")
    if not re.search(r"(?i)\b(?:speak|ask|tell|report|partner|classmate|dialogue)\b", material):
        issues.append("speaking_task_missing")
    if not re.search(r"(?i)\b(?:choose|match|complete|order|build|fix|correct|short answer)\b", material):
        issues.append("controlled_practice_missing")
    if level.upper() == "A1" and game_type == "detective":
        required_detective_patterns = {
            "question_building_missing": r"(?i)\b(?:build|order)\b[^\n]*\bquestions?\b",
            "short_answers_missing": r"(?i)\bshort\s+answers?\b",
            "choose_form_missing": r"(?i)\bchoose\b[^\n]*\bform\b",
            "mistake_correction_missing": r"(?i)\b(?:fix|correct)\b[^\n]*\bmistake\b",
            "sentence_completion_missing": r"(?i)\bcomplete\b[^\n]*\bsentences?\b",
            "matching_missing": r"(?i)\bmatch\b[^\n]*(?:question|answer)",
            "speak_report_missing": r"(?i)\bspeak\b[^\n]*\breport\b",
            "final_clue_guess_missing": r"(?i)\bfinal\b[^\n]*(?:clue|guess)",
        }
        for issue, pattern in required_detective_patterns.items():
            if not re.search(pattern, material):
                issues.append(issue)
        task_blocks: dict[int, list[str]] = {}
        challenge_lines: list[str] = []
        for title, lines in split_material_blocks(material):
            task_match = re.search(r"(?i)\bTASK\s+(\d+)\b", title)
            if task_match:
                task_blocks[int(task_match.group(1))] = lines
            elif "FOX CHALLENGE" in pdf_preview_text(title).upper():
                challenge_lines = lines
        exact_items = {1: 5, 2: 6, 3: 6, 4: 5, 5: 5, 6: 4}
        for task_number, expected in exact_items.items():
            actual = sum(
                1
                for line in task_blocks.get(task_number, [])
                if re.match(r"^\s*(?:\d+[.)]|[☐□])\s*", line)
            )
            if actual != expected:
                issues.append(f"task_{task_number}_requires_{expected}_items_found_{actual}")
        game_task_ranges = {7: (3, 4), 8: (1, 3)}
        for task_number, (minimum, maximum) in game_task_ranges.items():
            actual = sum(
                1
                for line in task_blocks.get(task_number, [])
                if re.match(r"^\s*(?:\d+[.)]|[☐□])\s*", line)
            )
            if not minimum <= actual <= maximum:
                issues.append(
                    f"task_{task_number}_requires_{minimum}_to_{maximum}_items_found_{actual}"
                )
        final_text = " ".join(task_blocks.get(8, [])).lower()
        if not all(word in final_text for word in ("clue", "guess", "because")):
            issues.append("final_guess_requires_clue_guess_because")
        challenge_actions = sum(
            1
            for line in challenge_lines
            if re.match(r"^\s*(?:\d+[.)]|[☐□])\s*", line)
        )
        if challenge_actions != 2:
            issues.append(f"fox_challenge_requires_2_items_found_{challenge_actions}")
        if any("/" not in line for line in task_blocks.get(1, [])):
            issues.append("task_1_requires_jumbled_words")
        if any("?" not in line for line in task_blocks.get(2, [])):
            issues.append("task_2_requires_question_plus_short_answer")
        speaking_text = " ".join(task_blocks.get(7, [])).lower()
        if not all(f"classmate {number}" in speaking_text for number in (1, 2, 3)):
            issues.append("task_7_requires_three_classmate_rows")
        if len(challenge_lines) == 2 and any(
            not any(marker in line for marker in ("______", "___"))
            for line in challenge_lines
        ):
            issues.append("fox_challenge_requires_two_answer_lines")
    return issues


def worksheet_quality_metrics(material: str) -> dict[str, Any]:
    task_matches = re.findall(r"(?im)^\s*(?:[^\w\n]+\s*)?TASK\s+(\d+)\b", material)
    task_numbers = {int(number) for number in task_matches}
    action_lines = 0
    in_challenge = False
    for line in material.splitlines():
        stripped = line.strip()
        if re.match(r"^(?:[^\w]+\s*)?FOX\s+CHALLENGE\b", stripped, re.I):
            in_challenge = True
            continue
        if in_challenge:
            continue
        if not stripped or re.match(r"^(?:[^\w]+\s*)?(?:TASK\s+\d+|FOX\s+CHALLENGE)\b", stripped, re.I):
            continue
        if re.match(r"^(?:instruction|example)\s*:", stripped, re.I):
            continue
        if any(marker in stripped for marker in ("☐", "______", "___")):
            action_lines += 1
        elif re.match(r"^\s*(?:\d+[.)]|[-•])\s+", stripped, re.I):
            action_lines += 1
    return {
        "task_numbers": sorted(task_numbers),
        "activity_blocks": len(task_numbers),
        "drill_items": action_lines,
        "has_fox_challenge": bool(
            re.search(r"(?im)^\s*(?:🦊\s*)?FOX\s+CHALLENGE\b", material)
        ),
    }


def format_material_output(material_kind: str, state: dict[str, Any], body: str) -> str:
    normalize_user_state(state)
    game = state["current_game"]
    headings = {
        "cards": "🃏 GAME CARDS",
        "worksheet": "📄 PLAYER WORKSHEET",
        "pack": "🎒 MINI GAME PACK",
    }
    header = f"{headings[material_kind]}\n\n🎲 {game['title']}"
    if material_kind == "worksheet":
        age = str(state.get("age") or "—")
        if age.isdigit():
            age += " лет"
        header = (
            f"{headings[material_kind]}\n{game['title']}\n"
            f"{state.get('topic') or '—'} • {state.get('level') or '—'} • "
            f"{age} • {state.get('skill') or '—'} • {state.get('duration') or '—'}"
        )
    if material_kind == "cards":
        age = str(state.get("age") or "—")
        if age.isdigit():
            age += " лет"
        header += f"\n{state.get('level') or '—'} • {age} • {state.get('topic') or '—'}"
    return f"{header}\n\n{body}".strip()


def split_vk_text(text: str, limit: int = 3800) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > limit:
            split_at = paragraph.rfind("\n", 0, limit)
            if split_at < limit // 2:
                split_at = paragraph.rfind(" ", 0, limit)
            if split_at <= 0:
                split_at = limit
            chunks.append(paragraph[:split_at].rstrip())
            paragraph = paragraph[split_at:].lstrip()
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def valid_media_item(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("owner_id"), int)
        and isinstance(item.get("media_id"), int)
    )


def load_media_cache() -> dict[str, dict[str, int]]:
    if not MEDIA_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(MEDIA_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {key: value for key, value in data.items() if key in CAROUSEL_ASSETS and valid_media_item(value)}


def save_media_cache(media: dict[str, dict[str, int]]) -> None:
    MEDIA_CACHE_PATH.write_text(json.dumps(media, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_carousel_media(vk_session) -> dict[str, dict[str, int]]:
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)
    media = load_media_cache()
    if all(valid_media_item(media.get(key)) for key in CAROUSEL_ASSETS):
        return media

    missing_files = [
        filename
        for key, filename in CAROUSEL_ASSETS.items()
        if not valid_media_item(media.get(key)) and not (CAROUSEL_DIR / filename).is_file()
    ]
    if missing_files:
        raise FileNotFoundError("Не найдены обложки: " + ", ".join(missing_files))

    uploader = VkUpload(vk_session)
    for key, filename in CAROUSEL_ASSETS.items():
        if valid_media_item(media.get(key)):
            continue
        uploaded = uploader.photo_messages(str(CAROUSEL_DIR / filename))
        if not uploaded:
            raise RuntimeError(f"VK не вернул данные фотографии: {filename}")
        photo = uploaded[0]
        media[key] = {"owner_id": int(photo["owner_id"]), "media_id": int(photo["id"])}
        save_media_cache(media)
    return media


def shorten(text: str, limit: int = 80) -> str:
    text = " ".join(clean_vk_text(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def enforce_preview_limit(text: str, limit: int) -> str:
    text = " ".join(clean_vk_text(text).split())
    if len(text) <= limit:
        return text
    words: list[str] = []
    for word in text.split():
        candidate = " ".join([*words, word])
        if len(candidate) > limit:
            break
        words.append(word)
    return " ".join(words)


def select_tags(text: str, candidates: list[tuple[tuple[str, ...], str]], defaults: list[str], limit: int) -> str:
    lowered = text.casefold()
    tags = [tag for keywords, tag in candidates if any(keyword in lowered for keyword in keywords)]
    for tag in defaults:
        if tag not in tags:
            tags.append(tag)
    selected: list[str] = []
    for tag in tags:
        candidate = " • ".join([*selected, tag])
        if len(candidate) > limit:
            continue
        selected.append(tag)
        if len(selected) == 4:
            break
    return enforce_preview_limit(" • ".join(selected), limit)


def build_carousel_previews(game: dict[str, Any]) -> dict[str, str]:
    mission_text = game["mission"].casefold()
    if "clue" in mission_text:
        mission = "Collect clues using English"
    elif "escape" in mission_text:
        mission = "Escape through English"
    elif "secret" in mission_text:
        mission = "Complete a secret English mission"
    elif "mystery" in mission_text or "solve" in mission_text:
        mission = "Solve the mystery in English"
    elif "point" in mission_text:
        mission = "Earn points through English"
    else:
        mission = "Complete the mission in English"

    how_text = " ".join(game["how_to_play"])
    how_to_play = select_tags(
        how_text,
        [
            (("team",), "teams"),
            (("role", "impostor"), "hidden roles"),
            (("clue", "mystery"), "solve clues"),
            (("move", "walk", "search"), "move & search"),
            (("partner",), "switch partners"),
            (("timer", "time"), "timer"),
            (("bluff",), "bluff"),
            (("point", "score"), "score points"),
            (("strateg",), "strategy"),
        ],
        ["teams", "speak English", "complete mission"],
        55,
    )

    toolkit_text = " ".join(game["english_toolkit"])
    english_toolkit = select_tags(
        toolkit_text,
        [
            (("?", "ask", "what", "can "), "Ask"),
            (("explain", "tell", "think"), "explain"),
            (("guess", "maybe", "answer"), "guess"),
            (("agree", "trade", "negot"), "negotiate"),
            (("describe",), "describe"),
            (("choose",), "choose"),
            (("let's", "suggest"), "suggest"),
        ],
        ["Ask", "explain", "guess", "negotiate"],
        55,
    )

    twist_text = game["fox_twist"].casefold()
    if "false" in twist_text and "clue" in twist_text:
        fox_twist = "One clue is secretly false"
    elif "role" in twist_text:
        fox_twist = "A hidden role changes everything"
    elif "sabot" in twist_text:
        fox_twist = "A saboteur can change the outcome"
    elif "rule" in twist_text or "change" in twist_text:
        fox_twist = "A secret rule changes the game"
    elif "time" in twist_text or "timer" in twist_text:
        fox_twist = "The rules change near the finish"
    else:
        fox_twist = "An unexpected rule changes the game"

    win_text = game["how_to_win"].casefold()
    if "point" in win_text or "score" in win_text:
        how_to_win = "Score the most points to win"
    elif "escape" in win_text:
        how_to_win = "Escape before time runs out"
    elif "solve" in win_text:
        how_to_win = "Solve the mission first to win"
    elif "first team" in win_text:
        how_to_win = "First team to finish wins"
    else:
        how_to_win = "Complete the mission first to win"

    return {
        "mission": enforce_preview_limit(mission, 45),
        "how_to_play": enforce_preview_limit(how_to_play, 55),
        "english_toolkit": enforce_preview_limit(english_toolkit, 55),
        "fox_twist": enforce_preview_limit(fox_twist, 45),
        "how_to_win": enforce_preview_limit(how_to_win, 45),
    }


def build_carousel(game: dict[str, Any], media: dict[str, dict[str, int]]) -> str:
    previews = build_carousel_previews(game)
    cards = [
        ("mission", "🎯 MISSION", previews["mission"]),
        ("how_to_play", "🎮 HOW TO PLAY", previews["how_to_play"]),
        ("english_toolkit", "💬 ENGLISH TOOLKIT", previews["english_toolkit"]),
        ("fox_twist", "🦊 FOX TWIST", previews["fox_twist"]),
        ("how_to_win", "🏆 HOW TO WIN", previews["how_to_win"]),
    ]
    elements = []
    for key, title, description in cards:
        photo = media[key]
        elements.append(
            {
                "title": title,
                "description": description,
                "photo_id": f"{photo['owner_id']}_{photo['media_id']}",
                "action": {"type": "open_photo"},
                # VK requires at least one button per carousel element. A
                # callback does not create a MESSAGE_NEW event, so this small
                # branded control cannot repeat content or affect the flow.
                "buttons": [
                    {
                        "action": {
                            "type": "callback",
                            "label": "🦊",
                            "payload": json.dumps({"carousel": "showcase"}),
                        },
                        "color": VkKeyboardColor.SECONDARY.value,
                    }
                ],
            }
        )
    return json.dumps({"type": "carousel", "elements": elements}, ensure_ascii=False)


def game_header(game: dict[str, Any], state: dict[str, Any]) -> str:
    normalize_user_state(state)
    return f"🎲 {game['title']}\n\n{format_parameters_line(state)}"


def format_parameters_line(state: dict[str, Any]) -> str:
    normalize_user_state(state)
    parameters = state["current_parameters"]
    age = str(parameters.get("age") or "—")
    if age.isdigit():
        age = f"age {age}"
    duration = str(parameters.get("duration") or "—")
    duration = re.sub(r"\s*мин(?:ут(?:а|ы)?)?\.?$", " min", duration, flags=re.IGNORECASE)
    return " · ".join(
        (
            str(parameters.get("level") or "—"),
            age,
            str(parameters.get("topic") or "—"),
            str(parameters.get("skill") or "—"),
            duration,
        )
    )


def format_game_text(game: dict[str, Any]) -> str:
    how_to_play = "\n".join(
        f"{i}. {step}" for i, step in enumerate(game["how_to_play"], 1)
    )
    english_toolkit = "\n".join(
        f"• {item}" for item in game["english_toolkit"]
    )
    text = f"""🎯 MISSION
{game['mission']}

🎮 HOW TO PLAY
{how_to_play}

💬 ENGLISH TOOLKIT
{english_toolkit}

🦊 FOX TWIST
{game['fox_twist']}

🏆 HOW TO WIN
{game['how_to_win']}"""
    return clean_vk_text(text)


def format_game_message(
    game: dict[str, Any],
    state: dict[str, Any],
    prefix: str | None = None,
) -> str:
    parts = []
    if prefix:
        parts.extend([prefix, ""])
    parts.extend([game_header(game, state), "", format_game_text(game)])
    return "\n".join(parts)


def short_error(error: Exception) -> str:
    code = getattr(error, "code", None)
    return f"{type(error).__name__} {code}" if code is not None else type(error).__name__


def safe_error_detail(error: Exception) -> str:
    detail = " ".join(str(error).split())
    for env_name in ("VK_TOKEN", "YANDEX_API_KEY", "YANDEX_FOLDER_ID"):
        secret = os.getenv(env_name)
        if secret:
            detail = detail.replace(secret, "<redacted>")
    detail = re.sub(
        r"(?i)(access_token|authorization|api[-_ ]?key|token)(\s*[=:]\s*)[^\s,&]+",
        r"\1\2<redacted>",
        detail,
    )
    return f"{short_error(error)}: {detail[:300]}" if detail else short_error(error)


def send_message(vk, peer_id: int, text: str, **extra: Any) -> None:
    vk.messages.send(peer_id=peer_id, message=text, random_id=random.getrandbits(31), **extra)


def acknowledge_carousel_callback(vk, event_object: Any) -> bool:
    payload = event_object.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return False
    if payload != {"carousel": "showcase"}:
        return False
    vk.messages.sendMessageEventAnswer(
        event_id=event_object["event_id"],
        user_id=event_object["user_id"],
        peer_id=event_object["peer_id"],
    )
    return True


def deliver_game(
    vk,
    peer_id: int,
    game: dict[str, Any],
    state: dict[str, Any],
    media: dict[str, dict[str, int]],
    keyboard: str,
    show_header: bool = True,
) -> bool:
    send_message(vk, peer_id, format_game_message(game, state), keyboard=keyboard)
    print("[TEXT SENT]")
    print("[KEYBOARD SENT]")
    return True


def user_is_processing(user_id: int) -> bool:
    with USER_STATES_LOCK:
        state = USER_STATES.get(user_id)
        return bool(state and state.get("processing", False))


def reserve_generation(user_id: int, processing_kind: str = "game") -> dict[str, Any] | None:
    with USER_STATES_LOCK:
        state = USER_STATES.get(user_id)
        if state is None or state.get("processing", False):
            return None
        state["processing"] = True
        state["processing_kind"] = processing_kind
        return deepcopy(state)


def release_generation(user_id: int) -> None:
    with USER_STATES_LOCK:
        state = USER_STATES.get(user_id)
        if state is not None:
            state["processing"] = False
            state["processing_kind"] = None


def processing_reply(user_id: int) -> str:
    with USER_STATES_LOCK:
        state = USER_STATES.get(user_id)
        if state and state.get("processing_kind") == "pdf":
            return PDF_PROCESSING_REPLY
        if state and state.get("processing_kind") == "material":
            return MATERIAL_PROCESSING_REPLY
    return ALREADY_PROCESSING_REPLY


def safe_error_reply(vk, peer_id: int, text: str) -> None:
    try:
        send_message(vk, peer_id, text)
    except Exception as error:
        print(f"[ERROR] stage=error_reply error={short_error(error)}")


def generate_and_deliver(
    vk_token: str,
    api_key: str,
    folder_id: str,
    user_id: int,
    peer_id: int,
    variation: str,
    state_snapshot: dict[str, Any],
    media: dict[str, dict[str, int]],
    keyboard: str,
) -> None:
    ai_session = None
    worker_vk = None
    ai_started = None
    try:
        ai_session = requests.Session()
        worker_vk_session = vk_api.VkApi(token=vk_token, api_version=VK_API_VERSION)
        worker_vk = worker_vk_session.get_api()
        ai_started = time.monotonic()
        print(f"[AI START] user_id={user_id} variation={variation}")
        normalize_user_state(state_snapshot)
        previous_game = state_snapshot.get("current_game")
        previous_type = state_snapshot.get("current_game_type")
        game = generate_game(ai_session, api_key, folder_id, state_snapshot, variation)
        if (
            variation == "another"
            and previous_game
            and (
                game_fingerprint(game) == game_fingerprint(previous_game)
                or detect_game_type(game) == previous_type
            )
        ):
            print(f"[AI RETRY] user_id={user_id} variation=another reason=same_mechanic")
            game = generate_game(ai_session, api_key, folder_id, state_snapshot, variation)
        ai_elapsed = time.monotonic() - ai_started
        print(f"[AI DONE] user_id={user_id} variation={variation} elapsed={ai_elapsed:.2f}s")
        if ai_elapsed > 35:
            print(f"[AI SLOW] user_id={user_id} elapsed={ai_elapsed:.2f}s limit=35s")

        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if current_state is None:
                raise RuntimeError("User state disappeared")
            set_current_game(current_state, game)
            clear_current_materials(current_state)
            delivery_state = deepcopy(current_state)

        deliver_game(
            worker_vk,
            peer_id,
            game,
            delivery_state,
            media,
            keyboard,
            show_header=variation == "base",
        )
    except requests.Timeout as error:
        elapsed = time.monotonic() - ai_started if ai_started is not None else 0
        print(f"[ERROR] stage=ai_timeout elapsed={elapsed:.2f}s error={safe_error_detail(error)}")
        if worker_vk is not None:
            safe_error_reply(worker_vk, peer_id, AI_TIMEOUT_REPLY)
    except Exception as error:
        print(f"[ERROR] stage=generation_or_delivery error={safe_error_detail(error)}")
        if worker_vk is not None:
            safe_error_reply(worker_vk, peer_id, REBUILD_ERROR_REPLY)
    finally:
        if ai_session is not None:
            ai_session.close()
        release_generation(user_id)
        print(f"[PROCESSING FALSE] user_id={user_id}")


def generate_and_deliver_material(
    vk_token: str,
    api_key: str,
    folder_id: str,
    user_id: int,
    peer_id: int,
    material_kind: str,
    state_snapshot: dict[str, Any],
) -> None:
    ai_session = None
    worker_vk = None
    started = None
    log_name = MATERIAL_LOG_NAMES[material_kind]
    try:
        ai_session = requests.Session()
        worker_vk_session = vk_api.VkApi(token=vk_token, api_version=VK_API_VERSION)
        worker_vk = worker_vk_session.get_api()
        started = time.monotonic()
        print(f"[{log_name} START] user_id={user_id}")
        body = generate_material(ai_session, api_key, folder_id, state_snapshot, material_kind)
        elapsed = time.monotonic() - started
        print(f"[{log_name} DONE] user_id={user_id} elapsed={elapsed:.2f}s")
        if elapsed > 35:
            print(f"[MATERIAL ERROR] stage=slow kind={material_kind} elapsed={elapsed:.2f}s limit=35s")

        normalize_user_state(state_snapshot)
        snapshot_fingerprint = game_fingerprint(state_snapshot["current_game"])
        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if (
                current_state is not None
                and normalize_user_state(current_state).get("current_game")
                and game_fingerprint(current_state["current_game"]) == snapshot_fingerprint
            ):
                cache_material(current_state, material_kind, body)

        material_text = format_material_output(material_kind, state_snapshot, body)
        for chunk in split_vk_text(material_text):
            send_message(worker_vk, peer_id, chunk)
        send_message(
            worker_vk,
            peer_id,
            "🦊 Материал готов. Что дальше?",
            keyboard=build_material_result_keyboard(),
        )
        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if current_state is not None:
                current_state["material_mode"] = "result"
    except requests.Timeout as error:
        elapsed = time.monotonic() - started if started is not None else 0
        print(
            f"[MATERIAL ERROR] stage=timeout kind={material_kind} "
            f"elapsed={elapsed:.2f}s error={safe_error_detail(error)}"
        )
        if worker_vk is not None:
            try:
                send_message(
                    worker_vk,
                    peer_id,
                    AI_TIMEOUT_REPLY,
                    keyboard=build_material_menu_keyboard(),
                )
            except Exception as reply_error:
                print(f"[MATERIAL ERROR] stage=error_reply error={short_error(reply_error)}")
    except Exception as error:
        print(
            f"[MATERIAL ERROR] stage=generation_or_delivery kind={material_kind} "
            f"error={safe_error_detail(error)}"
        )
        if worker_vk is not None:
            try:
                send_message(
                    worker_vk,
                    peer_id,
                    MATERIAL_ERROR_REPLY,
                    keyboard=build_material_menu_keyboard(),
                )
            except Exception as reply_error:
                print(f"[MATERIAL ERROR] stage=error_reply error={short_error(reply_error)}")
    finally:
        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if current_state is not None and current_state.get("material_mode") == "generating":
                current_state["material_mode"] = "menu"
        if ai_session is not None:
            ai_session.close()
        release_generation(user_id)
        print(f"[PROCESSING FALSE] user_id={user_id}")


def extract_vk_document_attachment(upload_result: Any) -> str:
    result = upload_result
    if isinstance(result, list):
        if not result:
            raise ValueError("VK returned an empty document list")
        result = result[0]
    if not isinstance(result, dict):
        raise ValueError("VK returned invalid document data")
    document = result.get("doc", result)
    if not isinstance(document, dict):
        raise ValueError("VK document payload is invalid")
    owner_id = document.get("owner_id")
    document_id = document.get("id")
    if not isinstance(owner_id, int) or not isinstance(document_id, int):
        raise ValueError("VK document identifiers are missing")
    return f"doc{owner_id}_{document_id}"


def _safe_vk_upload_log(value: Any) -> Any:
    """Keep upload diagnostics useful without writing VK secrets to logs."""
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered == "upload_url" and isinstance(item, str):
                safe[key] = item.split("?", 1)[0] + ("?<redacted>" if "?" in item else "")
            elif any(secret in lowered for secret in ("token", "access_key")) or lowered == "file":
                safe[key] = "<redacted>"
            else:
                safe[key] = _safe_vk_upload_log(item)
        return safe
    if isinstance(value, list):
        return [_safe_vk_upload_log(item) for item in value]
    return value


def is_temporary_vk_upload_error(error: Exception) -> bool:
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(error, requests.HTTPError):
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        return status == 429 or (isinstance(status, int) and status >= 500)
    return getattr(error, "code", None) in {1, 6, 9, 10, 29}


def vk_upload_error_reply(error: Exception) -> str:
    detail = safe_error_detail(error)
    if getattr(error, "code", None) == 15:
        detail += " — у community token нет права docs"
    return f"{PDF_UPLOAD_ERROR_REPLY}\n\nОшибка VK: {detail}"


def upload_pdf_document(
    vk,
    pdf_path: str | Path,
    peer_id: int,
    http_session: requests.Session | None = None,
    max_attempts: int = 2,
) -> str:
    """Upload one existing PDF through the explicit VK Docs API flow."""
    path = Path(pdf_path).resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError(f"PDF path is not a file: {path}")
    file_size = path.stat().st_size
    if file_size <= 0:
        raise ValueError(f"PDF file is empty: {path}")
    if max_attempts != 2:
        raise ValueError("VK PDF upload must use exactly one retry")

    owns_session = http_session is None
    session = http_session or requests.Session()
    last_error: Exception | None = None
    try:
        for attempt in range(1, max_attempts + 1):
            stage = "get_upload_url"
            try:
                print(
                    f"[VK DOC FILE] path={path} bytes={file_size} "
                    f"peer_id={peer_id} attempt={attempt}/{max_attempts}"
                )
                upload_url_response = vk.docs.getMessagesUploadServer(peer_id=peer_id)
                print(
                    "[VK DOC UPLOAD URL] response="
                    + json.dumps(
                        _safe_vk_upload_log(upload_url_response),
                        ensure_ascii=False,
                        default=str,
                    )
                )
                if not isinstance(upload_url_response, dict):
                    raise ValueError("VK upload_url response is not an object")
                upload_url = upload_url_response.get("upload_url")
                if not isinstance(upload_url, str) or not upload_url.startswith(("http://", "https://")):
                    raise ValueError("VK upload_url is missing or invalid")

                stage = "http_upload"
                with path.open("rb") as pdf_stream:
                    upload_response = session.post(
                        upload_url,
                        files={"file": (path.name, pdf_stream, "application/pdf")},
                        timeout=(5, 60),
                    )
                print(
                    f"[VK DOC HTTP UPLOAD] status={upload_response.status_code} "
                    f"attempt={attempt}/{max_attempts}"
                )
                upload_response.raise_for_status()
                try:
                    upload_payload = upload_response.json()
                except ValueError as error:
                    raise ValueError("VK upload server returned invalid JSON") from error
                print(
                    "[VK DOC HTTP RESPONSE] payload="
                    + json.dumps(
                        _safe_vk_upload_log(upload_payload),
                        ensure_ascii=False,
                        default=str,
                    )
                )
                if not isinstance(upload_payload, dict) or not upload_payload.get("file"):
                    raise ValueError("VK upload response does not contain file token")

                stage = "docs_save"
                save_response = vk.docs.save(
                    file=upload_payload["file"],
                    title=path.name,
                )
                print(
                    "[VK DOC SAVE] response="
                    + json.dumps(
                        _safe_vk_upload_log(save_response),
                        ensure_ascii=False,
                        default=str,
                    )
                )
                attachment = extract_vk_document_attachment(save_response)
                document = save_response[0] if isinstance(save_response, list) else save_response
                if isinstance(document, dict) and isinstance(document.get("doc"), dict):
                    document = document["doc"]
                owner_id = document.get("owner_id") if isinstance(document, dict) else None
                document_id = document.get("id") if isinstance(document, dict) else None
                print(f"[VK DOC IDS] owner_id={owner_id} doc_id={document_id}")
                print(f"[VK DOC ATTACHMENT] attachment={attachment}")
                return attachment
            except Exception as error:
                last_error = error
                print(
                    f"[VK DOC ERROR] stage={stage} attempt={attempt}/{max_attempts} "
                    f"error={safe_error_detail(error)}"
                )
                if attempt < max_attempts and is_temporary_vk_upload_error(error):
                    print(f"[VK DOC RETRY] next_attempt={attempt + 1}/{max_attempts}")
                    continue
                raise
    finally:
        if owns_session:
            session.close()
    if last_error is not None:
        raise last_error
    raise RuntimeError("VK PDF upload failed without an error")


def generate_and_deliver_pdf(
    vk_token: str,
    api_key: str,
    folder_id: str,
    user_id: int,
    peer_id: int,
    state_snapshot: dict[str, Any],
) -> None:
    ai_session = None
    worker_vk_session = None
    worker_vk = None
    try:
        print(f"[PDF START] user_id={user_id}")
        ai_session = requests.Session()
        worker_vk_session = vk_api.VkApi(token=vk_token, api_version=VK_API_VERSION)
        worker_vk = worker_vk_session.get_api()
        normalize_user_state(state_snapshot)
        game = state_snapshot["current_game"]
        fingerprint = game_fingerprint(game)
        generated_count = 0
        reused_count = 0
        materials: dict[str, str] = {}

        for material_kind in ("cards", "worksheet", "pack"):
            body = get_cached_material(state_snapshot, material_kind)
            if body:
                reused_count += 1
            else:
                log_name = MATERIAL_LOG_NAMES[material_kind]
                print(f"[{log_name} START] user_id={user_id} source=pdf")
                body = generate_material(
                    ai_session,
                    api_key,
                    folder_id,
                    state_snapshot,
                    material_kind,
                )
                print(f"[{log_name} DONE] user_id={user_id} source=pdf")
                generated_count += 1
                cache_material(state_snapshot, material_kind, body)
                with USER_STATES_LOCK:
                    current_state = USER_STATES.get(user_id)
                    if (
                        current_state is not None
                        and normalize_user_state(current_state).get("current_game")
                        and game_fingerprint(current_state["current_game"]) == fingerprint
                    ):
                        cache_material(current_state, material_kind, body)
            materials[material_kind] = body

        print(
            f"[PDF CONTENT READY] user_id={user_id} "
            f"reused={reused_count} generated={generated_count}"
        )
        print(f"[PDF BUILD] user_id={user_id}")
        pdf_path, page_count = create_printable_pack(
            game,
            state_snapshot,
            materials["cards"],
            materials["worksheet"],
            materials["pack"],
        )
        print(f"[PDF CREATED] user_id={user_id} pages={page_count}")
        print(f"PDF created: {pdf_path}")
        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if (
                current_state is not None
                and normalize_user_state(current_state).get("current_game")
                and game_fingerprint(current_state["current_game"]) == fingerprint
            ):
                current_state["current_materials"]["pdf_path"] = str(pdf_path)

        try:
            print(f"[VK DOC UPLOAD START] user_id={user_id}")
            attachment = upload_pdf_document(
                worker_vk,
                pdf_path,
                peer_id,
                http_session=ai_session,
            )
            print(f"[VK DOC UPLOAD DONE] user_id={user_id}")
            age = str(state_snapshot.get("age") or "—")
            if age.isdigit():
                age += " лет"
            success_text = f"""✅ Printable Pack готов!

🎲 {game['title']}
{state_snapshot.get('level') or '—'} • {age} • {state_snapshot.get('duration') or '—'}

🖨 Можно сохранять и печатать."""
            send_message(
                worker_vk,
                peer_id,
                success_text,
                attachment=attachment,
                keyboard=build_pdf_result_keyboard(),
            )
            with USER_STATES_LOCK:
                current_state = USER_STATES.get(user_id)
                if (
                    current_state is not None
                    and normalize_user_state(current_state).get("current_game")
                    and game_fingerprint(current_state["current_game"]) == fingerprint
                ):
                    current_state["current_materials"]["pdf_attachment"] = attachment
            print(f"[PDF SENT] user_id={user_id}")
        except Exception as upload_error:
            print(f"VK document upload failed: {safe_error_detail(upload_error)}")
            print(
                f"[PDF ERROR] stage=vk_upload user_id={user_id} "
                f"error={safe_error_detail(upload_error)}"
            )
            send_message(
                worker_vk,
                peer_id,
                vk_upload_error_reply(upload_error),
                keyboard=build_pdf_result_keyboard(),
            )

        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if current_state is not None:
                current_state["material_mode"] = "result"
    except requests.Timeout as error:
        print(
            f"[PDF ERROR] stage=material_timeout user_id={user_id} "
            f"error={safe_error_detail(error)}"
        )
        if worker_vk is not None:
            send_message(
                worker_vk,
                peer_id,
                AI_TIMEOUT_REPLY,
                keyboard=build_material_menu_keyboard(),
            )
    except Exception as error:
        print(f"[PDF ERROR] stage=build user_id={user_id} error={safe_error_detail(error)}")
        if worker_vk is not None:
            send_message(
                worker_vk,
                peer_id,
                PDF_ERROR_REPLY,
                keyboard=build_material_menu_keyboard(),
            )
    finally:
        with USER_STATES_LOCK:
            current_state = USER_STATES.get(user_id)
            if current_state is not None and current_state.get("material_mode") == "generating":
                current_state["material_mode"] = "menu"
        if ai_session is not None:
            ai_session.close()
        release_generation(user_id)
        print(f"[PROCESSING FALSE] user_id={user_id}")


def deliver_cached_pdf(
    vk_token: str,
    user_id: int,
    peer_id: int,
    state_snapshot: dict[str, Any],
) -> None:
    worker_vk = None
    try:
        normalize_user_state(state_snapshot)
        materials = state_snapshot["current_materials"]
        worker_vk_session = vk_api.VkApi(token=vk_token, api_version=VK_API_VERSION)
        worker_vk = worker_vk_session.get_api()
        attachment = materials.get("pdf_attachment")
        pdf_path = materials.get("pdf_path")
        if not attachment and pdf_path and Path(pdf_path).is_file():
            attachment = upload_pdf_document(worker_vk, pdf_path, peer_id)
            with USER_STATES_LOCK:
                current_state = USER_STATES.get(user_id)
                if current_state is not None:
                    normalize_user_state(current_state)
                    current_state["current_materials"]["pdf_attachment"] = attachment
        if not attachment:
            raise FileNotFoundError("cached printable pack is unavailable")
        send_message(
            worker_vk,
            peer_id,
            "📚 Весь комплект уже готов — отправляю сохранённый файл.",
            attachment=attachment,
            keyboard=build_pdf_result_keyboard(),
        )
    except Exception as error:
        print(
            f"[PDF ERROR] stage=cached_delivery user_id={user_id} "
            f"error={safe_error_detail(error)}"
        )
        if worker_vk is not None:
            safe_error_reply(worker_vk, peer_id, vk_upload_error_reply(error))
    finally:
        release_generation(user_id)
        print(f"[PROCESSING FALSE] user_id={user_id}")


def command_name(text: str) -> str | None:
    normalized = text.strip().casefold()
    if normalized in NEW_GAME_MESSAGES:
        return "new_game"
    if normalized in PRINTABLE_COMMANDS:
        return "printable"
    if normalized in MATERIAL_COMMANDS:
        return f"material_{MATERIAL_COMMANDS[normalized]}"
    return VARIATION_COMMANDS.get(normalized)


def main() -> None:
    load_dotenv()
    vk_token = os.getenv("VK_TOKEN")
    yandex_api_key = os.getenv("YANDEX_API_KEY")
    yandex_folder_id = os.getenv("YANDEX_FOLDER_ID")
    if not vk_token or not yandex_api_key or not yandex_folder_id:
        raise RuntimeError("В .env должны быть VK_TOKEN, YANDEX_API_KEY и YANDEX_FOLDER_ID.")

    try:
        ensure_saved_games_file()
    except Exception as error:
        print(f"[COLLECTION ERROR] stage=initialize error={short_error(error)}")
    with USER_STATES_LOCK:
        USER_STATES.clear()
    vk_session = vk_api.VkApi(token=vk_token, api_version=VK_API_VERSION)
    vk = vk_session.get_api()
    group_id = get_group_id(vk)
    try:
        carousel_media = prepare_carousel_media(vk_session)
        print(f"Carousel media ready: {len(carousel_media)}/5")
    except Exception as error:
        # The bot and Long Poll must remain available even when VK's photo
        # upload endpoint is temporarily unavailable. deliver_game() will
        # transparently switch to the two-message text representation.
        print(f"Carousel failed: media upload ({type(error).__name__})")
        carousel_media = {}
    keyboard = build_main_keyboard()
    print("Fox Game Lab запущен и ждёт сообщения...")
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fox-game")
    try:
        while True:
            try:
                longpoll = VkBotLongPoll(vk_session, group_id)
                for event in longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_EVENT:
                        try:
                            acknowledge_carousel_callback(vk, event.object)
                        except Exception as error:
                            print(f"[ERROR] stage=callback error={short_error(error)}")
                        continue
                    if event.type != VkBotEventType.MESSAGE_NEW:
                        continue
                    message = event.object.message
                    if message.get("out", 0) != 0:
                        continue

                    user_id = message["from_id"]
                    peer_id = message["peer_id"]
                    text = message.get("text", "")
                    command = command_name(text)
                    if command is not None:
                        print(f"[COMMAND] user_id={user_id} command={command}")

                    if user_is_processing(user_id):
                        safe_error_reply(vk, peer_id, processing_reply(user_id))
                        continue

                    try:
                        with USER_STATES_LOCK:
                            replies, variation, reply_keyboard = handle_user_text(user_id, text)
                    except Exception as error:
                        print(f"[COLLECTION ERROR] stage=command error={short_error(error)}")
                        safe_error_reply(vk, peer_id, COLLECTION_ERROR_REPLY)
                        continue

                    state_snapshot = None
                    if variation is not None:
                        is_material = variation.startswith("material:")
                        state_snapshot = reserve_generation(
                            user_id,
                            "pdf" if variation in {"printable", "cached_pdf"} else ("material" if is_material else "game"),
                        )
                        if state_snapshot is None:
                            safe_error_reply(vk, peer_id, processing_reply(user_id))
                            continue

                    try:
                        for index, reply in enumerate(replies):
                            extra = {}
                            if reply_keyboard is not None and index == len(replies) - 1:
                                extra["keyboard"] = reply_keyboard
                            send_message(vk, peer_id, reply, **extra)
                    except Exception as error:
                        print(f"[ERROR] stage=command_ack error={short_error(error)}")
                        if variation is not None:
                            release_generation(user_id)
                        safe_error_reply(vk, peer_id, REBUILD_ERROR_REPLY)
                        continue

                    if variation is None:
                        continue

                    try:
                        if variation == "printable":
                            executor.submit(
                                generate_and_deliver_pdf,
                                vk_token,
                                yandex_api_key,
                                yandex_folder_id,
                                user_id,
                                peer_id,
                                state_snapshot,
                            )
                        elif variation == "cached_pdf":
                            executor.submit(
                                deliver_cached_pdf,
                                vk_token,
                                user_id,
                                peer_id,
                                state_snapshot,
                            )
                        elif variation.startswith("material:"):
                            executor.submit(
                                generate_and_deliver_material,
                                vk_token,
                                yandex_api_key,
                                yandex_folder_id,
                                user_id,
                                peer_id,
                                variation.split(":", 1)[1],
                                state_snapshot,
                            )
                        else:
                            executor.submit(
                                generate_and_deliver,
                                vk_token,
                                yandex_api_key,
                                yandex_folder_id,
                                user_id,
                                peer_id,
                                variation,
                                state_snapshot,
                                carousel_media,
                                keyboard,
                            )
                    except Exception as error:
                        release_generation(user_id)
                        print(f"[ERROR] stage=worker_submit error={short_error(error)}")
                        safe_error_reply(vk, peer_id, REBUILD_ERROR_REPLY)
            except requests.RequestException as error:
                print(f"[ERROR] stage=longpoll error={short_error(error)}")
                time.sleep(2)
    finally:
        executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
