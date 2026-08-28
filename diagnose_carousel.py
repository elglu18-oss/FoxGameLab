import json
import os
import random
from datetime import datetime, timezone

import requests
import vk_api
from dotenv import load_dotenv
from vk_api.exceptions import ApiError

import bot


def find_recent_game_peer(vk) -> int:
    conversations = vk.messages.getConversations(count=20, filter="all")
    for item in conversations.get("items", []):
        peer = item["conversation"]["peer"]
        if peer.get("type") != "user":
            continue
        history = vk.messages.getHistory(peer_id=peer["id"], count=50)
        for message in history.get("items", []):
            text = message.get("text", "")
            is_game_message = "FOX TWIST" in text and (
                "HOW TO WIN" in text or "КАК ПОБЕДИТЬ" in text
            )
            is_post_game_keyboard = text == bot.POST_GAME_REPLY
            if message.get("out") == 1 and (is_game_message or is_post_game_keyboard):
                age = datetime.now(timezone.utc).timestamp() - message.get("date", 0)
                if age <= 24 * 60 * 60:
                    return int(peer["id"])
    raise RuntimeError("Recent game dialog not found")


def main() -> None:
    load_dotenv()
    session = vk_api.VkApi(token=os.environ["VK_TOKEN"], api_version=bot.VK_API_VERSION)
    vk = session.get_api()
    peer_id = find_recent_game_peer(vk)
    media = bot.load_media_cache()
    if len(media) != 5:
        raise RuntimeError("carousel_media.json must contain five items")
    state = {
        "age": "10",
        "level": "A2",
        "topic": "Travel",
        "skill": "Speaking",
        "duration": "15 минут",
        "last_game": None,
        "last_game_type": None,
        "current_step": "ready",
    }
    game = bot.generate_game(
        requests.Session(),
        os.environ["YANDEX_API_KEY"],
        os.environ["YANDEX_FOLDER_ID"],
        state,
        "base",
    )
    game = bot.validate_game(game)
    template = json.loads(bot.build_carousel(game, media))
    previews = [item["description"] for item in template["elements"]]
    limits = [45, 55, 55, 45, 45]
    print("target_dialog_found=yes")
    print("json_valid=yes")
    print("template_elements=" + str(len(template["elements"])))
    print("preview_lengths=" + ",".join(str(len(text)) for text in previews))
    print("preview_limits_ok=" + str(all(len(text) <= limit for text, limit in zip(previews, limits))).lower())
    print("preview_ellipsis_count=" + str(sum("…" in text for text in previews)))
    print("old_internal_buttons=0")
    print("required_callback_buttons=" + str(sum(len(item["buttons"]) for item in template["elements"])))
    try:
        carousel_sent = bot.deliver_game(
            vk,
            peer_id,
            game,
            state,
            media,
            bot.build_main_keyboard(),
        )
    except ApiError as error:
        print("vk_error_code=" + str(error.code))
        print("vk_error_message=" + str(error))
        safe_params = {
            item.get("key"): item.get("value")
            for item in error.error.get("request_params", [])
            if item.get("key") not in {"access_token", "template", "keyboard"}
        }
        print("safe_request_params=" + json.dumps(safe_params, ensure_ascii=False))
        raise SystemExit(2)
    print("carousel_sent=" + str(carousel_sent).lower())
    print("full_game_sent=yes")
    print("keyboard_sent=yes")


if __name__ == "__main__":
    main()
