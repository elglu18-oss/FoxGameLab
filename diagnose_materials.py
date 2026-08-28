import json
import os
import re
import sys

import vk_api
from dotenv import load_dotenv

import bot
from diagnose_carousel import find_recent_game_peer


def main() -> None:
    load_dotenv()
    vk_token = os.environ["VK_TOKEN"]
    api_key = os.environ["YANDEX_API_KEY"]
    folder_id = os.environ["YANDEX_FOLDER_ID"]
    session = vk_api.VkApi(token=vk_token, api_version=bot.VK_API_VERSION)
    vk = session.get_api()
    peer_id = find_recent_game_peer(vk)
    state = {
        "age": "9",
        "level": "A1",
        "topic": "to be",
        "skill": "Speaking",
        "duration": "5 минут",
        "last_game": None,
        "last_game_type": None,
        "current_step": "ready",
        "processing": False,
        "processing_kind": None,
        "collection_mode": None,
        "selected_saved_game_id": None,
        "collection_visible_ids": [],
        "delete_return_mode": None,
        "material_mode": None,
    }
    game = {
        "title": "Spy Hunt",
        "mission": "Find the two spies by asking simple questions with to be.",
        "how_to_play": [
            "Give each player a secret role.",
            "Players ask Are you questions and answer in character.",
            "Mark suspicious answers and name the spies.",
            "Spies win if one spy stays hidden.",
        ],
        "english_toolkit": [
            "Are you a student?",
            "Yes, I am.",
            "No, I am not.",
            "He is a spy!",
        ],
        "fox_twist": "After two minutes, the spies secretly swap one identity detail.",
        "how_to_win": "The class wins by finding both spies; the spies win if one stays hidden.",
    }
    state["last_game"] = game
    state["last_game_type"] = bot.detect_game_type(game)
    bot.USER_STATES[peer_id] = state
    original_game = json.dumps(game, ensure_ascii=False, sort_keys=True)
    requested_kinds = set(sys.argv[1:] or ("cards", "worksheet", "pack"))

    if requested_kinds == {"cards", "worksheet", "pack"}:
        media = bot.load_media_cache()
        bot.deliver_game(vk, peer_id, game, state, media, bot.build_main_keyboard())
        menu_replies, _, menu_keyboard = bot.handle_user_text(peer_id, "🧰 Материалы к игре")
        bot.send_message(vk, peer_id, menu_replies[0], keyboard=menu_keyboard)

    original_send_message = bot.send_message
    results = []
    outputs = {}
    try:
        for command, kind, heading in (
            ("🃏 Карточки", "cards", "🃏 GAME CARDS"),
            ("📄 Worksheet", "worksheet", "📄 SPY HUNT — PLAYER SHEET"),
            ("🎒 Мини-набор", "pack", "🎒 MINI GAME PACK"),
        ):
            if kind not in requested_kinds:
                continue
            if bot.USER_STATES[peer_id].get("material_mode") == "result":
                replies, _, keyboard = bot.handle_user_text(peer_id, "🧰 Другой материал")
                original_send_message(vk, peer_id, replies[0], keyboard=keyboard)

            replies, variation, keyboard = bot.handle_user_text(peer_id, command)
            assert variation == f"material:{kind}"
            assert replies == [bot.MATERIAL_PROGRESS[kind]]
            snapshot = bot.reserve_generation(peer_id, "material")
            assert snapshot is not None
            original_send_message(vk, peer_id, replies[0], keyboard=keyboard)

            sent_texts = []

            def recording_send(target_vk, target_peer_id, text, **extra):
                sent_texts.append((text, extra))
                original_send_message(target_vk, target_peer_id, text, **extra)

            bot.send_message = recording_send
            bot.generate_and_deliver_material(
                vk_token,
                api_key,
                folder_id,
                peer_id,
                peer_id,
                kind,
                snapshot,
            )
            bot.send_message = original_send_message

            output = "\n".join(text for text, _ in sent_texts[:-1])
            result_keyboard = sent_texts[-1][1].get("keyboard")
            current = bot.USER_STATES[peer_id]
            assert heading in output
            assert len(output) > len(heading) + len(game["title"])
            assert result_keyboard == bot.build_material_result_keyboard()
            assert current["processing"] is False
            assert json.dumps(current["last_game"], ensure_ascii=False, sort_keys=True) == original_game
            lowered = output.casefold()
            assert "look at the picture" not in lowered
            assert "listen to the recording" not in lowered
            assert "listen to the audio" not in lowered
            assert "see the attachment" not in lowered
            if kind == "cards":
                set_match = re.search(r"SET:\s*(\d+)\s+cards", output, re.IGNORECASE)
                assert set_match is not None and 6 <= int(set_match.group(1)) <= 12
                role_headings = [
                    line.strip()
                    for line in output.splitlines()
                    if line.strip()
                    and ord(line.strip()[0]) >= 0x1F000
                    and re.search(r"\d", line)
                ]
                assert len(role_headings) >= 4
                assert len(set(role_headings)) == len(role_headings)
            elif kind == "worksheet":
                assert "TASK 1" not in output
                for marker in ("MY SUSPECTS", "CLUE", "QUESTIONS I CAN USE", "FINAL GUESS", "FOX CHALLENGE"):
                    assert marker in output
            else:
                for marker in (
                    "▶ START",
                    "🗣 SAY THIS",
                    "🧩 USE THESE",
                    "🦊 TWIST",
                    "⚡ IF TOO EASY",
                    "🛟 IF TOO HARD",
                    "🏁 FINISH",
                ):
                    assert marker in output
            assert all(len(line) <= 120 for line in output.splitlines())
            outputs[kind] = output
            results.append((kind, len(output)))
    finally:
        bot.send_message = original_send_message

    print("target_dialog_found=yes")
    assert len(set(outputs.values())) == len(outputs)
    print("test_game=Spy Hunt")
    print("material_menu=yes")
    for kind, length in results:
        print(f"{kind}_sent=yes chars={length}")
    print("processing_false=yes")
    print("last_game_unchanged=yes")


if __name__ == "__main__":
    main()
