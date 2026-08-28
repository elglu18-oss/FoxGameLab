import os
from concurrent.futures import ThreadPoolExecutor

import vk_api
from dotenv import load_dotenv

import bot
from diagnose_carousel import find_recent_game_peer


def main() -> None:
    load_dotenv()
    vk_token = os.environ["VK_TOKEN"]
    api_key = os.environ["YANDEX_API_KEY"]
    folder_id = os.environ["YANDEX_FOLDER_ID"]
    vk = vk_api.VkApi(token=vk_token, api_version=bot.VK_API_VERSION).get_api()
    peer_id = find_recent_game_peer(vk)
    user_id = peer_id
    media = bot.load_media_cache()
    if len(media) != 5:
        raise RuntimeError("carousel_media.json must contain five items")

    previous_game = bot.fallback_game({"topic": "Travel"})
    state = {
        "age": "10",
        "level": "A2",
        "topic": "Travel",
        "skill": "Speaking",
        "duration": "15 минут",
        "last_game": previous_game,
        "last_game_type": bot.detect_game_type(previous_game),
        "current_step": "ready",
        "processing": False,
    }
    with bot.USER_STATES_LOCK:
        bot.USER_STATES.clear()
        bot.USER_STATES[user_id] = state

    commands = [
        ("🎲 Ещё вариант", "another"),
        ("⚡ Без подготовки", "no_prep"),
        ("🔥 Сделать активнее", "active"),
        ("🧠 Усложнить", "harder"),
        ("🪄 Удиви меня", "surprise"),
    ]
    duplicate_blocked = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        for index, (label, expected_variation) in enumerate(commands):
            print(f"[COMMAND] user_id={user_id} command={expected_variation}")
            replies, variation, reply_keyboard = bot.handle_user_text(user_id, label)
            if variation != expected_variation:
                raise RuntimeError(f"Unexpected variation: {variation}")
            snapshot = bot.reserve_generation(user_id)
            if snapshot is None:
                raise RuntimeError("Generation was not reserved")
            for reply_index, reply in enumerate(replies):
                extra = {}
                if reply_keyboard is not None and reply_index == len(replies) - 1:
                    extra["keyboard"] = reply_keyboard
                bot.send_message(vk, peer_id, reply, **extra)

            future = executor.submit(
                bot.generate_and_deliver,
                vk_token,
                api_key,
                folder_id,
                user_id,
                peer_id,
                variation,
                snapshot,
                media,
                bot.build_main_keyboard(),
            )
            if index == 0:
                duplicate_blocked = bot.reserve_generation(user_id) is None
                if duplicate_blocked:
                    bot.send_message(vk, peer_id, bot.ALREADY_PROCESSING_REPLY)
            future.result(timeout=60)
            if bot.user_is_processing(user_id):
                raise RuntimeError("processing was not released")
            print(f"command_test={variation} result=ok processing=false")

    print("duplicate_blocked=" + str(duplicate_blocked).lower())
    print("all_five_commands=ok")


if __name__ == "__main__":
    main()
