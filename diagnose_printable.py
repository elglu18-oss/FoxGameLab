import hashlib
import json
import os
from pathlib import Path

import vk_api
from dotenv import load_dotenv
from pypdf import PdfReader

import bot
from diagnose_carousel import find_recent_game_peer


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    load_dotenv()
    vk_token = os.environ["VK_TOKEN"]
    api_key = os.environ["YANDEX_API_KEY"]
    folder_id = os.environ["YANDEX_FOLDER_ID"]
    session = vk_api.VkApi(token=vk_token, api_version=bot.VK_API_VERSION)
    vk = session.get_api()
    peer_id = find_recent_game_peer(vk)
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
    state = bot.new_user_state()
    state.update(
        {
            "age": "9",
            "level": "A1",
            "topic": "to be",
            "skill": "Speaking",
            "duration": "5 минут",
            "last_game": game,
            "last_game_type": "spy",
            "current_step": "ready",
        }
    )
    bot.USER_STATES[peer_id] = state
    original_game = json.dumps(game, ensure_ascii=False, sort_keys=True)
    saved_hash = file_hash(bot.SAVED_GAMES_PATH)
    media_hash = file_hash(bot.MEDIA_CACHE_PATH)

    replies, variation, keyboard = bot.handle_user_text(peer_id, "🖨 Printable Pack")
    assert variation == "printable"
    assert replies == [bot.PRINTABLE_PROGRESS]
    snapshot = bot.reserve_generation(peer_id, "pdf")
    assert snapshot is not None
    bot.send_message(vk, peer_id, replies[0], keyboard=keyboard)

    created: dict[str, object] = {}
    sent: list[tuple[str, dict]] = []
    original_builder = bot.create_printable_pack
    original_sender = bot.send_message

    def recording_builder(*args, **kwargs):
        path, pages = original_builder(*args, **kwargs)
        created["path"] = path
        created["pages"] = pages
        return path, pages

    def recording_sender(target_vk, target_peer_id, text, **extra):
        sent.append((text, extra))
        original_sender(target_vk, target_peer_id, text, **extra)

    try:
        bot.create_printable_pack = recording_builder
        bot.send_message = recording_sender
        bot.generate_and_deliver_pdf(
            vk_token,
            api_key,
            folder_id,
            peer_id,
            peer_id,
            snapshot,
        )
    finally:
        bot.create_printable_pack = original_builder
        bot.send_message = original_sender

    current = bot.USER_STATES[peer_id]
    pdf_path = Path(created["path"])
    page_count = int(created["pages"])
    success = [extra for text, extra in sent if "Printable Pack готов" in text]
    assert success and str(success[0].get("attachment", "")).startswith("doc")
    assert pdf_path.is_file() and pdf_path.stat().st_size > 0
    assert len(PdfReader(pdf_path).pages) == page_count > 0
    assert current["processing"] is False
    assert current["processing_kind"] is None
    assert current["last_cards"]
    assert current["last_worksheet"]
    assert current["last_mini_pack"]
    assert json.dumps(current["last_game"], ensure_ascii=False, sort_keys=True) == original_game
    assert file_hash(bot.SAVED_GAMES_PATH) == saved_hash
    assert file_hash(bot.MEDIA_CACHE_PATH) == media_hash

    print("target_dialog_found=yes")
    print("test_game=Spy Hunt")
    print(f"pdf_path={pdf_path}")
    print(f"pdf_pages={page_count}")
    print(f"pdf_bytes={pdf_path.stat().st_size}")
    print("vk_document_sent=yes")
    print("materials_cached=3/3")
    print("processing_false=yes")
    print("last_game_unchanged=yes")
    print("saved_games_unchanged=yes")
    print("carousel_media_unchanged=yes")


if __name__ == "__main__":
    main()
