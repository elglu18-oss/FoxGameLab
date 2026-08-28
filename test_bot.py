import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import bot
import pdf_pack
from pypdf import PdfReader


def keyboard_labels(raw_keyboard: str) -> list[str]:
    keyboard = json.loads(raw_keyboard)
    return [button["action"]["label"] for row in keyboard["buttons"] for button in row]


class BotTests(unittest.TestCase):
    def setUp(self):
        self.saved_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.saved_temp.cleanup)
        self.saved_path_patch = patch.object(
            bot, "SAVED_GAMES_PATH", Path(self.saved_temp.name) / "saved_games.json"
        )
        self.saved_path_patch.start()
        self.addCleanup(self.saved_path_patch.stop)
        bot.USER_STATES.clear()
        self.state = {
            "age": "10",
            "level": "A2",
            "topic": "Travel",
            "skill": "Speaking",
            "duration": "15 минут",
            "last_game": None,
            "last_game_type": None,
            "current_step": "ready",
        }
        self.game = bot.fallback_game(self.state)
        self.media = {
            key: {"owner_id": -100, "media_id": index}
            for index, key in enumerate(bot.CAROUSEL_ASSETS, 1)
        }
        self.pdf_dir = Path(self.saved_temp.name) / "generated"
        self.cards_text = """SET: 6 CARDS

🕵 SPY 1
Keep your secret.
Change one answer after 2 minutes.
Say: No, I am not a spy.

🕵 SPY 2
Keep your secret.
Change one answer after 2 minutes.
Say: Yes, I am a student.

👤 STUDENT 1
Ask 2 classmates.
Listen carefully.
Find the spies.

👤 STUDENT 2
Answer the questions.
Watch for changes.
Find the spies.

👤 STUDENT 3
Ask simple questions.
Listen carefully.
Make your guess.

👤 STUDENT 4
Ask and answer.
Watch the other players.
Find the spies."""
        self.worksheet_text = """TASK 1 — BUILD THE QUESTION
1. you / a spy / are? ______
2. he / your friend / is? ______
3. they / ready / are? ______
4. she / the detective / is? ______
5. we / students / are? ______

TASK 2 — SHORT ANSWERS
1. Are you ready? ______
2. Is he a spy? ______
3. Is she here? ______
4. Are they friends? ______
5. Are we students? ______
6. Is it a clue? ______

TASK 3 — CHOOSE THE CORRECT FORM
1. I am / is ready.
2. He is / are quiet.
3. We am / are players.
4. She is / am clever.
5. They is / are players.
6. You am / are ready.

TASK 4 — FIX THE MISTAKE
1. I is a pupil. ______
2. He are nine. ______
3. We am ready. ______
4. They is spies. ______
5. She are a student. ______

TASK 5 — COMPLETE THE SENTENCES
1. I ______ ready.
2. She ______ my friend.
3. We ______ detectives.
4. You ______ a player.
5. They ______ students.

TASK 6 — MATCH QUESTION + ANSWER
1. Are you a spy? — A. Yes, she is.
2. Is she ready? — B. No, I am not.
3. Are they here? — C. Yes, they are.
4. Is he nine? — D. No, he is not.

TASK 7 — SPEAK AND REPORT
☐ Classmate 1: Are you a student? ___ | He/She is ___.
☐ Classmate 2: Are you a student? ___ | He/She is ___.
☐ Classmate 3: Are you a student? ___ | He/She is ___.

TASK 8 — MY FINAL GUESS
1. My clue is ______. My final guess is ______ because ______.

FOX CHALLENGE
1. Write your own question with to be: ______
2. Write your own sentence with to be: ______"""
        self.pack_text = """▶ START
Divide students into groups.
Give out the cards secretly.
Explain: two students are spies.
Model 2 sample questions.
Teacher Note: Keep spy cards hidden until the game begins.

🗣 SAY THIS
Are you ready to find the spies?
Ask simple questions with to be.
Listen carefully to every answer.
Speak in full sentences.
Teacher Tip: Say these lines with energy to build excitement.

🧩 ENGLISH SUPPORT
I am a spy.
I am a student.
Are you a student?
Are you a spy?
No, I am not a spy.
Yes, I am a student.

💡 TEACHER TIPS
Put shy students with strong partners.
Let weaker students use worksheet prompts.
Encourage eye contact.
Encourage full sentences.
Walk around and listen.
Praise effort and teamwork.
Do not correct every small mistake during fluency.
Save key correction for after the game.

🦊 FOX TWIST
After 2 minutes, spies change one answer.
Say: Something may change!
Ask students to watch for clues.

⚡ IF TOO EASY
Add a time limit.
Allow only 2 questions per classmate.
Ask for one extra full sentence.
Remove one language support prompt.

🛟 IF TOO HARD
Model the first round together.
Write 3 question starters on the board.
Let students practise in pairs first.
Keep the worksheet visible.
Give weaker students one ready-made question.

🏁 AFTER THE GAME
Ask: Who were the spies?
Ask: Which clues helped you?
Each student says one sentence with to be.
Praise good questions and careful listening.
Correct only 2–3 useful language points.

✅ QUICK CHECK — WHAT TO PREPARE
Game cards
Player worksheet
Timer
Board markers
Optional: small reward / point tokens"""

    def test_full_question_flow_and_step_keyboards(self):
        user_id = 42
        replies, variation, keyboard = bot.handle_user_text(user_id, "Привет")
        self.assertIsNone(variation)
        self.assertIn("Сколько лет", replies[0])
        self.assertEqual(keyboard_labels(keyboard), [])

        replies, _, keyboard = bot.handle_user_text(user_id, "10")
        self.assertIn("уровень", replies[0])
        self.assertEqual(keyboard_labels(keyboard), ["A1", "A2", "B1", "B2"])

        replies, _, keyboard = bot.handle_user_text(user_id, "A2")
        self.assertIn("тема", replies[0])
        self.assertEqual(keyboard_labels(keyboard), [])

        replies, _, keyboard = bot.handle_user_text(user_id, "Travel")
        self.assertIn("прокачивать", replies[0])
        self.assertEqual(
            keyboard_labels(keyboard),
            ["Speaking", "Vocabulary", "Grammar", "Reading", "Listening"],
        )

        replies, _, keyboard = bot.handle_user_text(user_id, "Speaking")
        self.assertIn("времени", replies[0])
        self.assertEqual(
            keyboard_labels(keyboard),
            ["5 минут", "10 минут", "15 минут", "20 минут"],
        )

        replies, variation, keyboard = bot.handle_user_text(user_id, "15 минут")
        self.assertEqual(variation, "base")
        self.assertIn("Возраст: 10", replies[0])
        self.assertEqual(keyboard_labels(keyboard), [])
        self.assertEqual(bot.USER_STATES[user_id]["current_step"], "ready")
        self.assertEqual(bot.USER_STATES[user_id]["duration"], "15 минут")

    def test_new_game_fully_resets_state(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, last_game_type="detective")
        replies, variation, keyboard = bot.handle_user_text(1, "🆕 Новая игра")
        self.assertIsNone(variation)
        self.assertEqual(
            replies,
            ["🦊 NEW GAME\n\nНовая охота за идеей!\n\nСколько лет твоим игрокам?"],
        )
        self.assertEqual(keyboard_labels(keyboard), [])
        self.assertEqual(bot.USER_STATES[1], bot.new_user_state())

    def test_all_main_commands_remain_available(self):
        self.assertEqual(
            keyboard_labels(bot.build_main_keyboard()),
            [
                "📦 Материалы",
                "💾 Сохранить",
                "🎲 Ещё вариант",
                "🧠 Усложнить",
                "⚡ Без подготовки",
                "✨ Удиви меня",
                "🆕 Новая игра",
            ],
        )
        bot.USER_STATES[1] = dict(self.state, last_game=self.game)
        expected = {
            "🎲 Ещё вариант": "another",
            "⚡ Без подготовки": "no_prep",
            "🧠 Усложнить": "harder",
            "✨ Удиви меня": "surprise",
        }
        for label, command in expected.items():
            _, variation, _ = bot.handle_user_text(1, label)
            self.assertEqual(variation, command)

    def test_materials_menu_with_last_game(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, last_game_type="detective")
        replies, variation, keyboard = bot.handle_user_text(1, "📦 Материалы")
        self.assertIsNone(variation)
        self.assertIn("📦 МАТЕРИАЛЫ", replies[0])
        self.assertIn(self.game["title"], replies[0])
        self.assertEqual(
            keyboard_labels(keyboard),
            ["🎴 Game Cards", "📝 Player Worksheet", "🦊 Teacher Mini Pack", "📚 Весь комплект", "↩️ К игре"],
        )

    def test_printable_menu_button(self):
        labels = keyboard_labels(bot.build_material_menu_keyboard())
        self.assertIn("📚 Весь комплект", labels)

    def test_printable_without_last_game(self):
        bot.USER_STATES[1] = dict(self.state)
        replies, variation, keyboard = bot.handle_user_text(1, "🖨 Printable Pack")
        self.assertIsNone(variation)
        self.assertEqual(replies, ["🦊 Сначала создай или выбери игру."])
        self.assertEqual(keyboard_labels(keyboard), ["📚 Моя коллекция", "🆕 Новая игра"])

    def _create_test_pdf(self, game=None, output_dir=None):
        game = game or self.game
        return pdf_pack.create_printable_pack(
            game,
            self.state,
            self.cards_text,
            self.worksheet_text,
            self.pack_text,
            output_dir or self.pdf_dir,
        )

    def test_pdf_generation(self):
        path, pages = self._create_test_pdf()
        self.assertTrue(path.is_file())
        self.assertEqual(pages, 4)

    def test_pdf_filename_sanitization(self):
        component = pdf_pack.sanitize_filename_component('Spy: Hunt / A1? * "test"')
        self.assertEqual(component, "Spy_Hunt_A1_test")
        self.assertFalse(any(char in component for char in '<>:"/\\|?*'))

    def test_generated_folder_is_created_automatically(self):
        target = Path(self.saved_temp.name) / "missing" / "generated"
        self.assertFalse(target.exists())
        path, _ = self._create_test_pdf(output_dir=target)
        self.assertTrue(target.is_dir())
        self.assertTrue(path.is_file())

    def test_pdf_cards_are_rendered(self):
        path, _ = self._create_test_pdf()
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        self.assertIn("GAME CARDS", text)
        self.assertIn("SPY 1", text)
        self.assertIn("SPY 2", text)
        self.assertIn("STUDENT 4", text)
        self.assertNotIn("CIVILIAN", text)

    def test_pdf_has_exactly_six_a1_spy_hunt_cards(self):
        announced, cards = pdf_pack.parse_cards(self.cards_text)
        titles = [pdf_pack.pdf_safe_text(title) for title, _ in cards]
        self.assertEqual(announced, 6)
        self.assertEqual(len(cards), 6)
        self.assertEqual(titles[:2], ["SPY 1", "SPY 2"])
        self.assertEqual(titles[2:], [f"STUDENT {number}" for number in range(1, 5)])

    def test_pdf_worksheet_is_rendered(self):
        path, _ = self._create_test_pdf()
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        self.assertIn("PLAYER WORKSHEET", text)
        self.assertIn("CHOOSE THE CORRECT FORM", text)
        self.assertIn("MY FINAL GUESS", text)
        self.assertIn("FOX CHALLENGE", text)

    def test_pdf_worksheet_can_expand_to_two_pages(self):
        long_blocks = []
        for number in range(1, 17):
            lines = "\n".join(f"{item}. Prompt {item} ______" for item in range(1, 9))
            long_blocks.append(f"TASK {number} — PRACTICE\n{lines}")
        long_blocks.append("FOX CHALLENGE\nWrite two original clues.\nExplain your choice.")
        path, _ = pdf_pack.create_printable_pack(
            self.game,
            self.state,
            self.cards_text,
            "\n\n".join(long_blocks),
            self.pack_text,
            self.pdf_dir,
        )
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        self.assertIn("PLAYER WORKSHEET 1", text)
        self.assertIn("PLAYER WORKSHEET 2", text)

    def test_pdf_mini_pack_is_rendered(self):
        path, _ = self._create_test_pdf()
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        self.assertIn("TEACHER MINI PACK", text)
        self.assertIn("IF TOO HARD", text)
        self.assertIn("AFTER THE GAME", text)
        self.assertIn("WHAT TO PREPARE", text)

    def test_pdf_page_titles_stay_in_compact_top_band(self):
        path, _ = self._create_test_pdf()
        reader = PdfReader(path)
        expected = ((1, "GAME CARDS"), (2, "PLAYER WORKSHEET"), (3, "TEACHER MINI PACK"))
        for page_index, title in expected:
            positions = []

            def visitor(text, _cm, tm, _font_dict, _font_size):
                if title in text:
                    positions.append(float(tm[5]))

            page = reader.pages[page_index]
            page.extract_text(visitor_text=visitor)
            page_height = float(page.mediabox.height)
            self.assertTrue(positions, title)
            self.assertGreater(max(positions), page_height * 0.90)

    def test_pdf_build_preserves_last_game_and_saved_games_file(self):
        game = json.loads(json.dumps(self.game))
        self.state["last_game"] = game
        state_before = json.loads(json.dumps(self.state))
        saved_bytes = b'{"keep":"unchanged"}'
        bot.SAVED_GAMES_PATH.write_bytes(saved_bytes)
        self._create_test_pdf(game)
        self.assertEqual(self.state, state_before)
        self.assertEqual(bot.SAVED_GAMES_PATH.read_bytes(), saved_bytes)

    def test_pdf_with_long_title(self):
        game = dict(self.game, title="The Extremely Long International Secret Airport Detective Adventure")
        path, pages = self._create_test_pdf(game)
        self.assertTrue(path.is_file())
        self.assertGreater(pages, 0)
        self.assertLess(len(path.name), 120)

    def test_pdf_with_cyrillic(self):
        game = dict(self.game, title="Секретная охота")
        path, _ = self._create_test_pdf(game)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        self.assertIn("Секретная охота", text)

    def _run_pdf_worker(self, cached=(), generate_side_effect=None, upload_error=None, build_error=None):
        game = json.loads(json.dumps(self.game))
        fingerprint = bot.game_fingerprint(game)
        state = dict(
            self.state,
            last_game=game,
            last_game_type="detective",
            processing=True,
            processing_kind="pdf",
            material_mode="generating",
            last_cards=self.cards_text if "cards" in cached else None,
            last_worksheet=self.worksheet_text if "worksheet" in cached else None,
            last_mini_pack=self.pack_text if "pack" in cached else None,
            material_cache_fingerprint=fingerprint if cached else None,
        )
        bot.USER_STATES[1] = state
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        uploader = Mock()
        if upload_error:
            uploader.side_effect = upload_error
        else:
            uploader.return_value = "doc-100_55"
        generated = {
            "cards": self.cards_text,
            "worksheet": self.worksheet_text,
            "pack": self.pack_text,
        }
        effect = generate_side_effect or (
            lambda session, api_key, folder_id, snapshot, kind: generated[kind]
        )
        fake_pdf = self.pdf_dir / "pack.pdf"
        fake_pdf.parent.mkdir(parents=True, exist_ok=True)
        fake_pdf.write_bytes(b"%PDF-fake")
        with (
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "upload_pdf_document", uploader),
            patch.object(bot, "generate_material", side_effect=effect) as generate,
            patch.object(
                bot,
                "create_printable_pack",
                side_effect=build_error,
                return_value=(fake_pdf, 5),
            ) as build,
        ):
            bot.generate_and_deliver_pdf("hidden", "hidden", "hidden", 1, 1, dict(state))
        return vk, uploader, generate, build, game

    def test_pdf_processing_prevents_duplicate(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, processing=False)
        self.assertIsNotNone(bot.reserve_generation(1, "pdf"))
        self.assertIsNone(bot.reserve_generation(1, "pdf"))
        self.assertEqual(bot.processing_reply(1), bot.PDF_PROCESSING_REPLY)
        bot.release_generation(1)

    def test_explicit_vk_pdf_upload_flow_returns_attachment(self):
        pdf_path = self.pdf_dir / "ready.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4\nready")
        vk = Mock()
        vk.docs.getMessagesUploadServer.return_value = {
            "upload_url": "https://upload.vk.test/document?token=secret"
        }
        vk.docs.save.return_value = {
            "type": "doc",
            "doc": {"owner_id": -212558195, "id": 77},
        }
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {"file": "opaque-upload-token"}
        session = Mock()
        session.post.return_value = response
        output = StringIO()
        with redirect_stdout(output):
            attachment = bot.upload_pdf_document(vk, pdf_path, 553582367, session)
        self.assertEqual(attachment, "doc-212558195_77")
        vk.docs.getMessagesUploadServer.assert_called_once_with(peer_id=553582367)
        self.assertEqual(session.post.call_args.kwargs["timeout"], (5, 60))
        self.assertEqual(session.post.call_args.kwargs["files"]["file"][2], "application/pdf")
        vk.docs.save.assert_called_once_with(file="opaque-upload-token", title="ready.pdf")
        log = output.getvalue()
        self.assertIn("status=200", log)
        self.assertIn("owner_id=-212558195 doc_id=77", log)
        self.assertIn("attachment=doc-212558195_77", log)
        self.assertNotIn("opaque-upload-token", log)
        self.assertNotIn("token=secret", log)

    def test_vk_pdf_upload_retries_once_without_rebuilding_file(self):
        pdf_path = self.pdf_dir / "retry.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        original_bytes = b"%PDF-1.4\nretry"
        pdf_path.write_bytes(original_bytes)
        vk = Mock()
        vk.docs.getMessagesUploadServer.side_effect = [
            {"upload_url": "https://upload.vk.test/first"},
            {"upload_url": "https://upload.vk.test/second"},
        ]
        success_response = Mock(status_code=200)
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {"file": "saved-token"}
        session = Mock()
        session.post.side_effect = [bot.requests.ConnectionError("temporary"), success_response]
        vk.docs.save.return_value = {"type": "doc", "doc": {"owner_id": -1, "id": 2}}
        attachment = bot.upload_pdf_document(vk, pdf_path, 42, session)
        self.assertEqual(attachment, "doc-1_2")
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(vk.docs.getMessagesUploadServer.call_count, 2)
        self.assertEqual(vk.docs.save.call_count, 1)
        self.assertEqual(pdf_path.read_bytes(), original_bytes)

    def test_vk_pdf_upload_rejects_missing_or_empty_file_before_api(self):
        vk = Mock()
        with self.assertRaises(FileNotFoundError):
            bot.upload_pdf_document(vk, self.pdf_dir / "missing.pdf", 42, Mock())
        empty_path = self.pdf_dir / "empty.pdf"
        empty_path.parent.mkdir(parents=True, exist_ok=True)
        empty_path.write_bytes(b"")
        with self.assertRaises(ValueError):
            bot.upload_pdf_document(vk, empty_path, 42, Mock())
        vk.docs.getMessagesUploadServer.assert_not_called()

    def test_vk_pdf_upload_does_not_retry_permanent_scope_error(self):
        pdf_path = self.pdf_dir / "scope.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4\nscope")

        class ScopeError(Exception):
            code = 15

        vk = Mock()
        vk.docs.getMessagesUploadServer.side_effect = ScopeError("Access denied")
        with self.assertRaises(ScopeError):
            bot.upload_pdf_document(vk, pdf_path, 42, Mock())
        self.assertEqual(vk.docs.getMessagesUploadServer.call_count, 1)
        reply = bot.vk_upload_error_reply(ScopeError("Access denied"))
        self.assertIn("Access denied", reply)
        self.assertIn("нет права docs", reply)

    def test_pdf_reuses_existing_cards(self):
        _, _, generate, _, _ = self._run_pdf_worker(cached=("cards",))
        kinds = [call.args[-1] for call in generate.call_args_list]
        self.assertNotIn("cards", kinds)
        self.assertEqual(set(kinds), {"worksheet", "pack"})

    def test_pdf_reuses_existing_worksheet(self):
        _, _, generate, _, _ = self._run_pdf_worker(cached=("worksheet",))
        kinds = [call.args[-1] for call in generate.call_args_list]
        self.assertNotIn("worksheet", kinds)
        self.assertEqual(set(kinds), {"cards", "pack"})

    def test_pdf_reuses_existing_mini_pack(self):
        _, _, generate, _, _ = self._run_pdf_worker(cached=("pack",))
        kinds = [call.args[-1] for call in generate.call_args_list]
        self.assertNotIn("pack", kinds)
        self.assertEqual(set(kinds), {"cards", "worksheet"})

    def test_pdf_generates_all_missing_materials(self):
        _, _, generate, _, _ = self._run_pdf_worker()
        kinds = [call.args[-1] for call in generate.call_args_list]
        self.assertEqual(kinds, ["cards", "worksheet", "pack"])

    def test_pdf_does_not_change_last_game(self):
        _, _, _, _, original = self._run_pdf_worker(cached=("cards", "worksheet", "pack"))
        self.assertEqual(bot.USER_STATES[1]["last_game"], original)

    def test_pdf_does_not_change_saved_games_json(self):
        bot.ensure_saved_games_file()
        before = bot.SAVED_GAMES_PATH.read_bytes()
        self._run_pdf_worker(cached=("cards", "worksheet", "pack"))
        self.assertEqual(bot.SAVED_GAMES_PATH.read_bytes(), before)

    def test_vk_document_upload_fallback_keeps_pdf(self):
        vk, _, _, build, _ = self._run_pdf_worker(
            cached=("cards", "worksheet", "pack"),
            upload_error=RuntimeError("denied"),
        )
        self.assertTrue(build.called)
        messages = [call.kwargs["message"] for call in vk.messages.send.call_args_list]
        self.assertTrue(any(message.startswith(bot.PDF_UPLOAD_ERROR_REPLY) for message in messages))
        self.assertTrue(any("RuntimeError: denied" in message for message in messages))
        self.assertFalse(bot.USER_STATES[1]["processing"])

    def test_pdf_error_resets_processing(self):
        vk, _, _, _, _ = self._run_pdf_worker(
            cached=("cards", "worksheet", "pack"),
            build_error=RuntimeError("build failed"),
        )
        self.assertFalse(bot.USER_STATES[1]["processing"])
        self.assertEqual(vk.messages.send.call_args.kwargs["message"], bot.PDF_ERROR_REPLY)

    def test_pdf_is_valid_and_non_empty(self):
        path, pages = self._create_test_pdf()
        self.assertGreater(path.stat().st_size, 1000)
        self.assertEqual(len(PdfReader(path).pages), pages)
        self.assertGreater(pages, 0)

    def test_materials_menu_without_last_game(self):
        bot.USER_STATES[1] = dict(self.state)
        replies, variation, keyboard = bot.handle_user_text(1, "🧰 Материалы к игре")
        self.assertIsNone(variation)
        self.assertEqual(replies, ["🦊 Сначала создай или выбери игру."])
        self.assertEqual(keyboard_labels(keyboard), ["📚 Моя коллекция", "🆕 Новая игра"])

    def _run_material_worker(self, material_kind, body):
        state = dict(
            self.state,
            last_game=self.game,
            last_game_type="detective",
            processing=True,
            processing_kind="material",
            material_mode="generating",
        )
        bot.USER_STATES[1] = state
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        ai_session = Mock()
        with (
            patch.object(bot.requests, "Session", return_value=ai_session),
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "generate_material", return_value=body) as generate,
        ):
            bot.generate_and_deliver_material(
                "hidden", "hidden", "hidden", 1, 1, material_kind, dict(state)
            )
        return vk, generate

    def test_cards_generation(self):
        vk, generate = self._run_material_worker("cards", "CARD 1\nPassport\n---\nCARD 2\nTicket")
        generate.assert_called_once()
        self.assertIn("🃏 GAME CARDS", vk.messages.send.call_args_list[0].kwargs["message"])
        self.assertIn("CARD 2", vk.messages.send.call_args_list[0].kwargs["message"])
        self.assertIn("keyboard", vk.messages.send.call_args_list[-1].kwargs)

    def test_worksheet_generation(self):
        vk, generate = self._run_material_worker(
            "worksheet", "🕵 MY SUSPECTS\n☐ ______\n\n🔎 CLUE 1\n______\n\n🦊 FOX CHALLENGE\nUse I am."
        )
        generate.assert_called_once()
        self.assertIn("PLAYER WORKSHEET", vk.messages.send.call_args_list[0].kwargs["message"])
        self.assertIn("MY SUSPECTS", vk.messages.send.call_args_list[0].kwargs["message"])

    def test_mini_pack_generation(self):
        vk, generate = self._run_material_worker(
            "pack", "▶ START\nGive roles.\nStart timer.\n\n🗣 SAY THIS\nFind the spy."
        )
        generate.assert_called_once()
        self.assertIn("🎒 MINI GAME PACK", vk.messages.send.call_args_list[0].kwargs["message"])
        self.assertIn("SAY THIS", vk.messages.send.call_args_list[0].kwargs["message"])

    def test_material_generation_does_not_replace_last_game(self):
        original = json.loads(json.dumps(self.game))
        self._run_material_worker("cards", "CARD 1\nClue")
        self.assertEqual(bot.USER_STATES[1]["last_game"], original)
        self.assertEqual(bot.USER_STATES[1]["last_game_type"], "detective")

    def test_material_processing_blocks_second_request(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, processing=False)
        first = bot.reserve_generation(1, "material")
        second = bot.reserve_generation(1, "material")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(bot.processing_reply(1), bot.MATERIAL_PROCESSING_REPLY)
        bot.release_generation(1)

    def test_material_timeout_releases_processing(self):
        state = dict(
            self.state,
            last_game=self.game,
            processing=True,
            processing_kind="material",
        )
        bot.USER_STATES[1] = state
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        with (
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "generate_material", side_effect=bot.requests.Timeout("slow")),
        ):
            bot.generate_and_deliver_material(
                "hidden", "hidden", "hidden", 1, 1, "cards", dict(state)
            )
        self.assertFalse(bot.USER_STATES[1]["processing"])
        self.assertIsNone(bot.USER_STATES[1]["processing_kind"])
        self.assertEqual(vk.messages.send.call_args.kwargs["message"], bot.AI_TIMEOUT_REPLY)

    def test_back_to_current_game_does_not_generate(self):
        bot.USER_STATES[1] = dict(
            self.state, last_game=self.game, material_mode="result", processing=False
        )
        with patch.object(bot, "generate_game") as generate_game, patch.object(
            bot, "generate_material"
        ) as generate_material:
            replies, variation, keyboard = bot.handle_user_text(1, "↩ К игре")
        self.assertIsNone(variation)
        self.assertIn(self.game["title"], replies[0])
        self.assertIn("📦 Материалы", keyboard_labels(keyboard))
        generate_game.assert_not_called()
        generate_material.assert_not_called()

    def test_another_material_returns_to_menu(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, material_mode="result")
        replies, variation, keyboard = bot.handle_user_text(1, "🧰 Другой материал")
        self.assertIsNone(variation)
        self.assertIn("Что открыть?", replies[0])
        self.assertIn("🎴 Game Cards", keyboard_labels(keyboard))

    def test_material_processing_is_independent_between_users(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, processing=False)
        bot.USER_STATES[2] = dict(self.state, last_game=self.game, processing=False)
        self.assertIsNotNone(bot.reserve_generation(1, "material"))
        self.assertIsNotNone(bot.reserve_generation(2, "material"))
        self.assertTrue(bot.user_is_processing(1))
        self.assertTrue(bot.user_is_processing(2))
        bot.release_generation(1)
        self.assertFalse(bot.user_is_processing(1))
        self.assertTrue(bot.user_is_processing(2))
        bot.release_generation(2)

    def test_material_request_contains_current_game_parameters(self):
        state = dict(self.state, last_game=self.game)
        request = bot.build_material_request(state, "cards")
        for value in ("10", "A2", "Travel", "Speaking", "15 минут", self.game["title"]):
            self.assertIn(value, request)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": {"alternatives": [{"message": {"text": self.cards_text}}]}
        }
        session = Mock()
        session.post.return_value = response
        material = bot.generate_material(session, "hidden", "hidden", state, "cards")
        self.assertIn("SPY 1", material)
        self.assertEqual(session.post.call_args.kwargs["timeout"], (5, 30))

        cards_request = bot.build_material_request(state, "cards")
        worksheet_request = bot.build_material_request(state, "worksheet")
        pack_request = bot.build_material_request(state, "pack")
        self.assertIn("SET: X CARDS", cards_request)
        self.assertIn("четыре STUDENT", cards_request)
        self.assertIn("минимум 7 основных activity blocks", worksheet_request)
        self.assertIn("25–35", worksheet_request)
        self.assertIn("TASK N", worksheet_request)
        self.assertIn("FOX CHALLENGE", worksheet_request)
        self.assertIn("START", pack_request)
        self.assertIn("SAY THIS", pack_request)
        self.assertIn("IF TOO HARD", pack_request)
        self.assertIn("AFTER THE GAME", pack_request)
        self.assertIn("QUICK CHECK", pack_request)
        self.assertEqual(len({cards_request, worksheet_request, pack_request}), 3)
        self.assertIn("Look at the pictures", bot.MATERIAL_AI_INSTRUCTIONS)
        self.assertIn("Listen to the recording", bot.MATERIAL_AI_INSTRUCTIONS)
        self.assertIn("Запрещено", bot.MATERIAL_AI_INSTRUCTIONS)

    def test_a1_detective_cards_quality_requires_students(self):
        self.assertEqual(bot.cards_quality_issues(self.cards_text, "A1", "detective"), [])
        bad = self.cards_text.replace("STUDENT", "CIVILIAN")
        issues = bot.cards_quality_issues(bad, "A1", "detective")
        self.assertIn("requires_4_student_cards", issues)
        self.assertIn("forbidden_words_civilian", issues)

    def test_teacher_pack_quality_requires_nine_practical_blocks(self):
        self.assertEqual(bot.teacher_pack_quality_issues(self.pack_text), [])

    def test_worksheet_quality_standard_passes_dense_a1_sample(self):
        self.assertEqual(
            bot.worksheet_quality_issues(self.worksheet_text, "A1", "detective"),
            [],
        )

    def test_worksheet_quality_rejects_overloaded_a1_sample(self):
        overloaded = self.worksheet_text.replace(
            "FOX CHALLENGE",
            "TASK 9 — EXTRA\n" + "\n".join(f"{n}. Extra ______" for n in range(1, 8))
            + "\n\nFOX CHALLENGE",
        )
        self.assertIn(
            "drill_items_above_40",
            bot.worksheet_quality_issues(overloaded, "A1", "detective"),
        )

    def test_worksheet_quality_rebuilds_once(self):
        bad = Mock()
        bad.raise_for_status.return_value = None
        bad.json.return_value = {
            "result": {"alternatives": [{"message": {"text": "TASK 1 — TRY\nOne item."}}]}
        }
        good = Mock()
        good.raise_for_status.return_value = None
        good.json.return_value = {
            "result": {"alternatives": [{"message": {"text": self.worksheet_text}}]}
        }
        session = Mock()
        session.post.side_effect = [bad, good]
        state = dict(self.state, level="A1", last_game=self.game)
        result = bot.generate_material(session, "hidden", "hidden", state, "worksheet")
        self.assertEqual(result, self.worksheet_text)
        self.assertEqual(session.post.call_count, 2)
        retry_prompt = session.post.call_args.kwargs["json"]["messages"][1]["text"]
        self.assertIn("Предыдущий вариант не прошёл", retry_prompt)

    def test_save_new_game(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, last_game_type="detective")
        replies, variation, keyboard = bot.handle_user_text(1, "💾 Сохранить игру")
        self.assertIsNone(variation)
        self.assertIn("💾 СОХРАНЕНО!", replies[0])
        self.assertIn(self.game["title"], replies[0])
        self.assertIn("🦊 Игра уже в твоей коллекции.", replies[0])
        self.assertNotIn("Теперь она ждёт", replies[0])
        self.assertIn("📚 Моя коллекция", keyboard_labels(keyboard))
        saved = bot.get_user_saved_games(1)
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0]["id"].startswith("game_"))
        self.assertEqual(saved[0]["game_type"], "detective")

    def test_repeated_save_does_not_duplicate_game(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, last_game_type="detective")
        bot.handle_user_text(1, "💾 Сохранить игру")
        replies, variation, _ = bot.handle_user_text(1, "💾 Сохранить игру")
        self.assertIsNone(variation)
        self.assertEqual(
            replies,
            ["🦊 Эта игра уже в твоей коллекции."],
        )
        self.assertEqual(len(bot.get_user_saved_games(1)), 1)

    def test_empty_collection(self):
        bot.USER_STATES[1] = dict(self.state)
        replies, variation, keyboard = bot.handle_user_text(1, "📚 Моя коллекция")
        self.assertIsNone(variation)
        self.assertIn("пока пустая", replies[0])
        self.assertIn("захочется повторить", replies[0])
        self.assertEqual(
            keyboard_labels(keyboard),
            ["🔎 Поиск", "🎯 Фильтры", "⭐ Избранное", "🕘 Недавние", "↩️ Назад"],
        )

    def test_collection_lists_multiple_games_newest_first(self):
        for index in range(3):
            game = dict(self.game, title=f"Game {index + 1}")
            state = dict(self.state, last_game=game, last_game_type="team")
            self.assertEqual(bot.save_user_game(1, state)[0], "saved")
        bot.USER_STATES[1] = dict(self.state)
        replies, _, keyboard = bot.handle_user_text(1, "📚 Моя коллекция")
        self.assertLess(replies[0].index("1. Game 3"), replies[0].index("3. Game 1"))
        self.assertIn("🦊 Здесь живут твои любимые игровые идеи.", replies[0])
        self.assertIn("   Travel • A2 • 15 минут", replies[0])
        labels = keyboard_labels(keyboard)
        self.assertEqual(labels[:3], ["1. Game 3", "2. Game 2", "3. Game 1"])
        self.assertEqual(
            labels[-5:],
            ["🔎 Поиск", "🎯 Фильтры", "⭐ Избранное", "🕘 Недавние", "↩️ Назад"],
        )

    def test_collection_search_by_title_is_case_insensitive(self):
        for title in ("Secret Safari", "Word Auction", "Mystery Train"):
            game = dict(self.game, title=title)
            self.assertEqual(
                bot.save_user_game(1, dict(self.state, last_game=game, last_game_type="team"))[0],
                "saved",
            )
        results = bot.search_user_saved_games(1, "sEcReT sAfArI")
        self.assertEqual([game["title"] for game in results], ["Secret Safari"])
        bot.USER_STATES[1] = dict(self.state)
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "🔎 Поиск")
        replies, variation, _ = bot.handle_user_text(1, "SECRET")
        self.assertIsNone(variation)
        self.assertIn("Secret Safari", replies[0])

    def test_collection_search_by_topic_is_case_insensitive(self):
        travel = dict(self.game, title="Airport Race")
        animals = dict(self.game, title="Animal Detectives")
        bot.save_user_game(1, dict(self.state, topic="Travel", last_game=travel))
        bot.save_user_game(1, dict(self.state, topic="Animals", last_game=animals))
        results = bot.search_user_saved_games(1, "aNiMaLs")
        self.assertEqual([game["title"] for game in results], ["Animal Detectives"])

    def test_collection_filter_by_age(self):
        bot.save_user_game(1, dict(self.state, age="9", last_game=dict(self.game, title="Age Nine")))
        bot.save_user_game(1, dict(self.state, age="12", last_game=dict(self.game, title="Age Twelve")))
        results = bot.filter_user_saved_games(1, "age", "9")
        self.assertEqual([game["title"] for game in results], ["Age Nine"])

    def test_collection_filter_by_level(self):
        bot.save_user_game(1, dict(self.state, level="A1", last_game=dict(self.game, title="A1 Hunt")))
        bot.save_user_game(1, dict(self.state, level="B1", last_game=dict(self.game, title="B1 Hunt")))
        results = bot.filter_user_saved_games(1, "level", "a1")
        self.assertEqual([game["title"] for game in results], ["A1 Hunt"])
        bot.USER_STATES[1] = dict(self.state)
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "🎯 Фильтры")
        bot.handle_user_text(1, "level")
        replies, _, keyboard = bot.handle_user_text(1, "A1")
        self.assertIn("A1 Hunt", replies[0])
        self.assertIn("❌ Сбросить фильтр", keyboard_labels(keyboard))

    def test_add_and_remove_favorite(self):
        bot.save_user_game(1, dict(self.state, last_game=self.game, last_game_type="detective"))
        bot.USER_STATES[1] = dict(self.state)
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "1")
        replies, _, keyboard = bot.handle_user_text(1, "⭐ В избранное")
        self.assertEqual(replies[0], "⭐ Добавлено в избранное.")
        self.assertTrue(bot.get_user_saved_games(1)[0]["favorite"])
        self.assertIn("☆ Убрать из избранного", keyboard_labels(keyboard))
        replies, _, keyboard = bot.handle_user_text(1, "☆ Убрать из избранного")
        self.assertEqual(replies[0], "☆ Убрано из избранного.")
        self.assertFalse(bot.get_user_saved_games(1)[0]["favorite"])
        self.assertIn("⭐ В избранное", keyboard_labels(keyboard))

    def test_recent_games_order_by_last_used_and_limit(self):
        for index in range(12):
            game = dict(self.game, title=f"Recent {index}")
            bot.save_user_game(1, dict(self.state, last_game=game))
        data = json.loads(bot.SAVED_GAMES_PATH.read_text(encoding="utf-8"))
        for index, game in enumerate(data["1"]):
            game["last_used"] = f"2026-08-{index + 1:02d}T10:00:00+00:00"
        bot.SAVED_GAMES_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        recent = bot.get_recent_saved_games(1)
        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0]["title"], "Recent 11")
        self.assertEqual(recent[-1]["title"], "Recent 2")

    def test_old_saved_games_are_migrated_with_collection_fields(self):
        old_record = {
            "1": [
                {
                    "id": "old_game",
                    "saved_at": "2025-01-01T00:00:00+00:00",
                    "title": "Old Game",
                    "topic": "School",
                }
            ]
        }
        bot.SAVED_GAMES_PATH.write_text(
            json.dumps(old_record, ensure_ascii=False),
            encoding="utf-8",
        )
        migrated = bot.get_user_saved_games(1)[0]
        self.assertFalse(migrated["favorite"])
        self.assertIsNone(migrated["last_used"])
        persisted = json.loads(bot.SAVED_GAMES_PATH.read_text(encoding="utf-8"))["1"][0]
        self.assertIn("favorite", persisted)
        self.assertIn("last_used", persisted)

    def test_open_saved_game(self):
        bot.save_user_game(1, dict(self.state, last_game=self.game, last_game_type="detective"))
        bot.USER_STATES[1] = dict(self.state)
        bot.handle_user_text(1, "📚 Моя коллекция")
        replies, variation, keyboard = bot.handle_user_text(1, f"1. {self.game['title']}")
        self.assertIsNone(variation)
        self.assertIn("📚 SAVED GAME", replies[0])
        self.assertIn("A2 · age 10 · Travel · Speaking · 15 min", replies[0])
        self.assertIn("HOW TO PLAY", replies[0])
        self.assertEqual(
            keyboard_labels(keyboard),
            [
                "▶️ Использовать",
                "📦 Материалы",
                "⭐ В избранное",
                "🗑 Удалить",
                "📚 К коллекции",
                "🆕 Новая игра",
            ],
        )

    def test_use_saved_game_restores_generation_state(self):
        stored_state = dict(self.state, last_game=self.game, last_game_type="detective")
        bot.save_user_game(1, stored_state)
        bot.USER_STATES[1] = bot.new_user_state()
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "1")
        replies, variation, keyboard = bot.handle_user_text(1, "▶ Использовать")
        restored = bot.USER_STATES[1]
        self.assertIsNone(variation)
        self.assertIn("Игра выбрана", replies[0])
        self.assertEqual(restored["last_game"], self.game)
        self.assertEqual(restored["last_game_type"], "detective")
        self.assertEqual(restored["topic"], "Travel")
        self.assertEqual(restored["current_step"], "ready")
        self.assertIn("🧠 Усложнить", keyboard_labels(keyboard))

    def test_delete_saved_game_requires_and_accepts_confirmation(self):
        bot.save_user_game(1, dict(self.state, last_game=self.game, last_game_type="detective"))
        bot.USER_STATES[1] = dict(self.state)
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "1")
        replies, _, keyboard = bot.handle_user_text(1, "🗑 Удалить")
        self.assertEqual(
            replies[0], f"🗑 Удалить игру\n«{self.game['title']}»\nиз коллекции?"
        )
        self.assertEqual(keyboard_labels(keyboard), ["✅ Да, удалить", "↩ Оставить"])
        self.assertEqual(len(bot.get_user_saved_games(1)), 1)
        replies, _, _ = bot.handle_user_text(1, "✅ Да, удалить")
        self.assertEqual(replies[0], "🗑 Игра удалена.")
        self.assertIn("пока пустая", replies[1])
        self.assertEqual(bot.get_user_saved_games(1), [])

    def test_cancel_delete_returns_to_saved_game(self):
        bot.save_user_game(1, dict(self.state, last_game=self.game, last_game_type="detective"))
        bot.USER_STATES[1] = dict(self.state)
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "1")
        bot.handle_user_text(1, "🗑 Удалить")
        replies, _, keyboard = bot.handle_user_text(1, "↩ Оставить")
        self.assertIn("📚 SAVED GAME", replies[0])
        self.assertIn("🗑 Удалить", keyboard_labels(keyboard))
        self.assertEqual(len(bot.get_user_saved_games(1)), 1)

    def test_collection_limit_is_twenty_without_automatic_deletion(self):
        for index in range(20):
            game = dict(self.game, title=f"Game {index}")
            status, _ = bot.save_user_game(
                1, dict(self.state, last_game=game, last_game_type="team")
            )
            self.assertEqual(status, "saved")
        extra = dict(self.game, title="Game 21")
        bot.USER_STATES[1] = dict(self.state, last_game=extra, last_game_type="team")
        replies, _, keyboard = bot.handle_user_text(1, "💾 Сохранить игру")
        self.assertIn("уже 20 игр", replies[0])
        self.assertIn("Освободим место", replies[0])
        self.assertEqual(len(bot.get_user_saved_games(1)), 20)
        self.assertEqual(
            keyboard_labels(keyboard),
            ["🗑 Управлять коллекцией", "↩ Оставить как есть"],
        )

    def test_different_users_have_separate_collections(self):
        bot.save_user_game(1, dict(self.state, last_game=self.game, last_game_type="one"))
        other_game = dict(self.game, title="Other game")
        bot.save_user_game(2, dict(self.state, last_game=other_game, last_game_type="two"))
        self.assertEqual([game["title"] for game in bot.get_user_saved_games(1)], [self.game["title"]])
        self.assertEqual([game["title"] for game in bot.get_user_saved_games(2)], ["Other game"])

    def test_corrupt_saved_games_is_backed_up_and_recovered(self):
        bot.SAVED_GAMES_PATH.write_text("{broken json", encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            loaded = bot.load_saved_games()
        self.assertEqual(loaded, {})
        self.assertEqual(json.loads(bot.SAVED_GAMES_PATH.read_text(encoding="utf-8")), {})
        backups = list(bot.SAVED_GAMES_PATH.parent.glob("saved_games.corrupt-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "{broken json")
        self.assertIn("[COLLECTION ERROR]", output.getvalue())

    def test_parallel_saved_game_writes_keep_valid_json(self):
        def save(index):
            game = dict(self.game, title=f"Concurrent {index}")
            return bot.save_user_game(
                1, dict(self.state, last_game=game, last_game_type="team")
            )[0]

        with ThreadPoolExecutor(max_workers=10) as executor:
            statuses = list(executor.map(save, range(10)))
        self.assertEqual(statuses, ["saved"] * 10)
        raw = json.loads(bot.SAVED_GAMES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(raw["1"]), 10)

    def test_collection_commands_never_start_yandex_generation(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, last_game_type="detective")
        with patch.object(bot, "generate_game") as generate:
            bot.handle_user_text(1, "💾 Сохранить игру")
            bot.handle_user_text(1, "📚 Моя коллекция")
            bot.handle_user_text(1, "1")
            bot.handle_user_text(1, "🗑 Удалить")
            bot.handle_user_text(1, "↩ Оставить")
            bot.handle_user_text(1, "📚 К коллекции")
            bot.handle_user_text(1, "↩ Назад")
        generate.assert_not_called()

    def test_variations_use_last_parameters_and_game_type(self):
        state = dict(self.state, last_game=self.game, last_game_type="bingo")
        request = bot.build_generation_request(state, "another")
        self.assertIn("Возраст: 10", request)
        self.assertIn("Время: 15 минут", request)
        self.assertIn("нельзя повторять: bingo", request)
        self.assertIn("Предыдущая игра", request)
        self.assertIn("без печати", bot.build_generation_request(state, "no_prep"))
        self.assertIn("secret roles", bot.build_generation_request(state, "surprise"))

    def test_old_carousel_actions_are_silently_ignored(self):
        bot.USER_STATES[1] = dict(self.state)
        for label in ("Подробнее", "Фразы", "Попробовать twist"):
            replies, variation, keyboard = bot.handle_user_text(1, label)
            self.assertEqual(replies, [])
            self.assertIsNone(variation)
            self.assertIsNone(keyboard)

    def test_required_carousel_callback_is_acknowledged_without_message(self):
        vk = Mock()
        handled = bot.acknowledge_carousel_callback(
            vk,
            {
                "payload": {"carousel": "showcase"},
                "event_id": "event",
                "user_id": 1,
                "peer_id": 1,
            },
        )
        self.assertTrue(handled)
        vk.messages.sendMessageEventAnswer.assert_called_once_with(
            event_id="event", user_id=1, peer_id=1
        )
        vk.messages.send.assert_not_called()

    def test_users_have_independent_state(self):
        bot.handle_user_text(1, "Привет")
        bot.handle_user_text(2, "Привет")
        bot.handle_user_text(1, "8")
        bot.handle_user_text(2, "14")
        self.assertEqual(bot.USER_STATES[1]["age"], "8")
        self.assertEqual(bot.USER_STATES[2]["age"], "14")

    def test_carousel_has_only_inert_required_callbacks(self):
        template = json.loads(bot.build_carousel(self.game, self.media))
        self.assertEqual(template["type"], "carousel")
        self.assertEqual(len(template["elements"]), 5)
        self.assertEqual(
            [element["photo_id"] for element in template["elements"]],
            [f"-100_{number}" for number in range(1, 6)],
        )
        buttons = [element["buttons"][0] for element in template["elements"]]
        self.assertTrue(all(button["action"]["type"] == "callback" for button in buttons))
        self.assertTrue(all(button["action"]["label"] == "🦊" for button in buttons))
        self.assertFalse(any(button["action"]["label"] in {"Подробнее", "Фразы", "Twist"} for button in buttons))
        descriptions = [element["description"] for element in template["elements"]]
        limits = [45, 55, 55, 45, 45]
        self.assertTrue(all(len(text) <= limit for text, limit in zip(descriptions, limits)))
        self.assertTrue(all(text and not text.endswith(("…", ".", ",")) for text in descriptions))
        self.assertNotIn("1.", descriptions[1])
        self.assertNotIn("2.", descriptions[1])
        self.assertIn(" • ", descriptions[1])
        self.assertIn(" • ", descriptions[2])

    def test_carousel_previews_are_semantic_and_never_split_words(self):
        game = dict(self.game)
        game.update(
            {
                "mission": "Collect clues and solve an extremely detailed mystery using English.",
                "how_to_play": [
                    "Split into two teams with hidden roles.",
                    "Move around, search for clues, switch partners and use a timer.",
                ],
                "english_toolkit": [
                    "Ask questions, explain ideas, guess answers, negotiate and describe clues."
                ],
                "fox_twist": "One of the clues is secretly false and changes the entire story.",
                "how_to_win": "Score the most points before the other teams finish.",
            }
        )
        previews = bot.build_carousel_previews(game)
        limits = {
            "mission": 45,
            "how_to_play": 55,
            "english_toolkit": 55,
            "fox_twist": 45,
            "how_to_win": 45,
        }
        for key, limit in limits.items():
            self.assertLessEqual(len(previews[key]), limit)
            self.assertNotIn("…", previews[key])
        self.assertEqual(previews["mission"], "Collect clues using English")
        self.assertIn("hidden roles", previews["how_to_play"])
        self.assertIn("negotiate", previews["english_toolkit"])
        self.assertEqual(previews["fox_twist"], "One clue is secretly false")
        self.assertEqual(previews["how_to_win"], "Score the most points to win")

        source = "Short words followed by Supercalifragilisticexpialidocious"
        limited = bot.enforce_preview_limit(source, 24)
        self.assertEqual(limited, "Short words followed by")

    def test_full_game_text_is_single_clean_mobile_message(self):
        text = bot.format_game_text(self.game)
        for heading in ("MISSION", "HOW TO PLAY", "ENGLISH TOOLKIT", "FOX TWIST", "HOW TO WIN"):
            self.assertEqual(text.count(heading), 1)
        self.assertNotIn("*", text)
        self.assertNotIn("#", text)
        self.assertIn("1. Split into teams.", text)
        self.assertIn("• Can I have a clue?", text)

    def test_game_header_has_title_parameters_and_teaser(self):
        header = bot.game_header(self.game, self.state)
        self.assertIn("🎲 The Secret Travel Hunt", header)
        self.assertIn("A2 · age 10 · Travel · Speaking · 15 min", header)

    def test_success_delivery_is_one_compact_message_with_keyboard(self):
        vk = Mock()
        result = bot.deliver_game(vk, 1, self.game, self.state, self.media, bot.build_main_keyboard())
        self.assertTrue(result)
        calls = vk.messages.send.call_args_list
        self.assertEqual(len(calls), 1)
        message = calls[0].kwargs["message"]
        self.assertIn("🎲 The Secret Travel Hunt", message)
        self.assertIn("HOW TO PLAY", message)
        self.assertNotIn("template", calls[0].kwargs)
        self.assertIn("keyboard", calls[0].kwargs)

    def test_revision_delivery_is_also_one_compact_message(self):
        vk = Mock()
        result = bot.deliver_game(
            vk,
            1,
            self.game,
            self.state,
            self.media,
            bot.build_main_keyboard(),
            show_header=False,
        )
        self.assertTrue(result)
        calls = vk.messages.send.call_args_list
        self.assertEqual(len(calls), 1)
        self.assertIn("HOW TO PLAY", calls[0].kwargs["message"])
        self.assertIn("keyboard", calls[0].kwargs)

    def test_game_delivery_does_not_use_carousel(self):
        vk = Mock()
        output = StringIO()
        with redirect_stdout(output):
            result = bot.deliver_game(vk, 1, self.game, self.state, self.media, bot.build_main_keyboard())
        self.assertTrue(result)
        calls = vk.messages.send.call_args_list
        self.assertEqual(len(calls), 1)
        self.assertIn("HOW TO PLAY", calls[0].kwargs["message"])
        self.assertNotIn("template", calls[0].kwargs)

    def test_media_cache_prevents_reupload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "carousel_media.json"
            cache_path.write_text(json.dumps(self.media), encoding="utf-8")
            with (
                patch.object(bot, "MEDIA_CACHE_PATH", cache_path),
                patch.object(bot, "VkUpload") as uploader,
            ):
                loaded = bot.prepare_carousel_media(Mock())
            self.assertEqual(loaded, self.media)
            uploader.assert_not_called()

    def test_incomplete_cache_uploads_only_missing_media(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            carousel_dir = Path(temp_dir) / "assets"
            carousel_dir.mkdir()
            for filename in bot.CAROUSEL_ASSETS.values():
                (carousel_dir / filename).write_bytes(b"png")
            cache_path = Path(temp_dir) / "carousel_media.json"
            uploader = Mock()
            uploader.photo_messages.side_effect = [
                [{"owner_id": -100, "id": index}] for index in range(1, 6)
            ]
            with (
                patch.object(bot, "CAROUSEL_DIR", carousel_dir),
                patch.object(bot, "MEDIA_CACHE_PATH", cache_path),
                patch.object(bot, "VkUpload", return_value=uploader),
            ):
                media = bot.prepare_carousel_media(Mock())
            self.assertEqual(len(media), 5)
            self.assertEqual(uploader.photo_messages.call_count, 5)

    def test_json_extraction_and_invalid_json_fallback(self):
        raw = "Explanation before JSON\n```json\n" + json.dumps(self.game) + "\n```"
        self.assertEqual(bot.extract_json_object(raw), self.game)

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": {"alternatives": [{"message": {"text": "not json"}}]}
        }
        session = Mock()
        session.post.return_value = response
        game = bot.generate_game(session, "hidden", "hidden", self.state, "base")
        rendered = json.dumps(game, ensure_ascii=False)
        self.assertNotIn("*", rendered)
        self.assertNotIn("#", rendered)
        self.assertIn("Complete the secret mission", game["mission"])

    def test_error_log_never_contains_exception_message(self):
        self.assertEqual(bot.short_error(RuntimeError("VK_TOKEN=secret")), "RuntimeError")

    def test_processing_starts_false_and_only_one_generation_is_reserved(self):
        bot.USER_STATES[1] = bot.new_user_state()
        bot.USER_STATES[1].update(self.state)
        self.assertFalse(bot.USER_STATES[1]["processing"])
        first = bot.reserve_generation(1)
        second = bot.reserve_generation(1)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertTrue(bot.user_is_processing(1))
        bot.release_generation(1)
        self.assertFalse(bot.user_is_processing(1))

    def test_variation_commands_have_exact_immediate_acknowledgements(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, processing=False)
        expected = {
            "🎲 Ещё вариант": "🎲 Ищу другую механику...",
            "⚡ Без подготовки": "⚡ Убираю всю подготовку...",
            "🔥 Сделать активнее": "🔥 Добавляю движение и азарт...",
            "🧠 Усложнить": "🧠 Добавляю уровень сложности...",
            "🪄 Удиви меня": "🪄 Сейчас будет что-то необычное...",
        }
        for command, acknowledgement in expected.items():
            replies, variation, _ = bot.handle_user_text(1, command)
            self.assertIsNotNone(variation)
            self.assertEqual(replies, [acknowledgement])

    def test_successful_worker_updates_game_and_releases_processing(self):
        bot.USER_STATES[1] = dict(self.state, processing=True)
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        ai_session = Mock()
        with (
            patch.object(bot.requests, "Session", return_value=ai_session),
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "generate_game", return_value=self.game) as generate,
            patch.object(bot, "deliver_game", return_value=True) as deliver,
        ):
            bot.generate_and_deliver(
                "hidden",
                "hidden",
                "hidden",
                1,
                1,
                "harder",
                dict(self.state),
                self.media,
                bot.build_main_keyboard(),
            )
        generate.assert_called_once()
        deliver.assert_called_once()
        self.assertEqual(bot.USER_STATES[1]["last_game"], self.game)
        self.assertFalse(bot.USER_STATES[1]["processing"])

    def test_more_variant_retries_when_mechanic_is_unchanged(self):
        different_game = dict(
            self.game,
            title="Word Auction",
            mission="Win the auction by bidding with correct English phrases.",
            how_to_play=[
                "Make two teams.",
                "Bid points for each phrase.",
                "Say the phrase correctly.",
                "Keep the points when the answer is correct.",
            ],
        )
        state = dict(
            self.state,
            last_game=self.game,
            last_game_type=bot.detect_game_type(self.game),
            processing=True,
        )
        bot.USER_STATES[1] = dict(state)
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        with (
            patch.object(bot.requests, "Session", return_value=Mock()),
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "generate_game", side_effect=[self.game, different_game]) as generate,
            patch.object(bot, "deliver_game", return_value=True) as deliver,
        ):
            bot.generate_and_deliver(
                "hidden",
                "hidden",
                "hidden",
                1,
                1,
                "another",
                dict(state),
                self.media,
                bot.build_main_keyboard(),
            )
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(deliver.call_args.args[2], different_game)
        self.assertFalse(bot.USER_STATES[1]["processing"])

    def test_timeout_replies_and_always_releases_processing(self):
        bot.USER_STATES[1] = dict(self.state, processing=True)
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        with (
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "generate_game", side_effect=bot.requests.Timeout("slow")),
        ):
            bot.generate_and_deliver(
                "hidden",
                "hidden",
                "hidden",
                1,
                1,
                "harder",
                dict(self.state),
                self.media,
                bot.build_main_keyboard(),
            )
        self.assertFalse(bot.USER_STATES[1]["processing"])
        self.assertEqual(vk.messages.send.call_args.kwargs["message"], bot.AI_TIMEOUT_REPLY)

    def test_delivery_error_replies_and_always_releases_processing(self):
        bot.USER_STATES[1] = dict(self.state, processing=True)
        vk = Mock()
        vk_session = Mock()
        vk_session.get_api.return_value = vk
        with (
            patch.object(bot.vk_api, "VkApi", return_value=vk_session),
            patch.object(bot, "generate_game", return_value=self.game),
            patch.object(bot, "deliver_game", side_effect=RuntimeError("failed")),
        ):
            bot.generate_and_deliver(
                "hidden",
                "hidden",
                "hidden",
                1,
                1,
                "harder",
                dict(self.state),
                self.media,
                bot.build_main_keyboard(),
            )
        self.assertFalse(bot.USER_STATES[1]["processing"])
        self.assertEqual(vk.messages.send.call_args.kwargs["message"], bot.REBUILD_ERROR_REPLY)

    def test_yandex_request_timeout_is_35_seconds(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": {"alternatives": [{"message": {"text": json.dumps(self.game)}}]}
        }
        session = Mock()
        session.post.return_value = response
        bot.generate_game(session, "hidden", "hidden", self.state, "base")
        self.assertEqual(session.post.call_args.kwargs["timeout"], (5, 30))

    def test_variation_command_takes_priority_over_question_step(self):
        bot.USER_STATES[1] = dict(
            self.state,
            current_step="duration",
            duration=None,
            last_game=self.game,
            processing=False,
        )
        replies, variation, _ = bot.handle_user_text(1, "🧠 Усложнить")
        self.assertEqual(variation, "harder")
        self.assertEqual(replies, ["🧠 Добавляю уровень сложности..."])
        self.assertEqual(bot.USER_STATES[1]["current_step"], "duration")
        self.assertIsNone(bot.USER_STATES[1]["duration"])

    def test_state_is_split_into_game_parameters_and_materials(self):
        state = bot.new_user_state()
        self.assertIn("current_game", state)
        self.assertEqual(
            set(state["current_parameters"]),
            {"age", "level", "topic", "skill", "duration"},
        )
        self.assertEqual(
            set(state["current_materials"]),
            {"fingerprint", "cards", "worksheet", "pack", "pdf_path", "pdf_attachment"},
        )

    def test_cached_material_is_opened_without_generation(self):
        state = dict(self.state, last_game=self.game, last_game_type="detective")
        bot.normalize_user_state(state)
        bot.cache_material(state, "cards", self.cards_text)
        bot.USER_STATES[1] = state
        replies, variation, keyboard = bot.handle_user_text(1, "🎴 Game Cards")
        self.assertIsNone(variation)
        self.assertIn("GAME CARDS", replies[0])
        self.assertIn("сохранённую версию", replies[-1])
        self.assertIn("↩ К игре", keyboard_labels(keyboard))

    def test_saved_game_restores_its_material_cache(self):
        state = dict(self.state, last_game=self.game, last_game_type="detective")
        bot.normalize_user_state(state)
        bot.cache_material(state, "worksheet", self.worksheet_text)
        self.assertEqual(bot.save_user_game(1, state)[0], "saved")
        bot.USER_STATES[1] = bot.new_user_state()
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "1")
        replies, variation, _ = bot.handle_user_text(1, "📦 Материалы")
        self.assertIsNone(variation)
        self.assertIn("МАТЕРИАЛЫ", replies[0])
        replies, variation, _ = bot.handle_user_text(1, "📝 Player Worksheet")
        self.assertIsNone(variation)
        self.assertIn("PLAYER WORKSHEET", replies[0])

    def test_ai_processing_lock_uses_short_repeat_reply(self):
        bot.USER_STATES[1] = dict(self.state, last_game=self.game, processing=False)
        self.assertIsNotNone(bot.reserve_generation(1, "game"))
        self.assertEqual(bot.processing_reply(1), "🦊 Уже придумываю...")
        self.assertIsNone(bot.reserve_generation(1, "game"))
        bot.release_generation(1)
        self.assertFalse(bot.USER_STATES[1]["processing"])

    def test_new_game_resets_current_state_but_keeps_saved_games(self):
        state = dict(self.state, last_game=self.game, last_game_type="detective")
        self.assertEqual(bot.save_user_game(1, state)[0], "saved")
        bot.USER_STATES[1] = state
        bot.handle_user_text(1, "🆕 Новая игра")
        reset = bot.USER_STATES[1]
        self.assertIsNone(reset["current_game"])
        self.assertTrue(all(value is None for value in reset["current_parameters"].values()))
        self.assertTrue(all(
            reset["current_materials"][key] is None
            for key in ("cards", "worksheet", "pack", "pdf_path", "pdf_attachment")
        ))
        self.assertEqual(len(bot.get_user_saved_games(1)), 1)

    def test_teacher_ux_path_keeps_parameters_and_correct_game_materials(self):
        bot.handle_user_text(1, "🆕 Новая игра")
        for answer in ("10", "A2", "Travel", "Speaking"):
            bot.handle_user_text(1, answer)
        _, variation, _ = bot.handle_user_text(1, "15 минут")
        self.assertEqual(variation, "base")
        state = bot.USER_STATES[1]
        bot.set_current_game(state, self.game, "detective")
        bot.cache_material(state, "cards", self.cards_text)
        bot.cache_material(state, "worksheet", self.worksheet_text)
        self.assertIsNone(bot.handle_user_text(1, "📦 Материалы")[1])
        self.assertIsNone(bot.handle_user_text(1, "🎴 Game Cards")[1])
        self.assertIsNone(bot.handle_user_text(1, "📝 Player Worksheet")[1])
        self.assertIsNone(bot.handle_user_text(1, "💾 Сохранить")[1])
        bot.handle_user_text(1, "📚 Моя коллекция")
        bot.handle_user_text(1, "1")
        bot.handle_user_text(1, "▶️ Использовать")
        for command, expected in (
            ("🧠 Усложнить", "harder"),
            ("⚡ Без подготовки", "no_prep"),
            ("🎲 Ещё вариант", "another"),
        ):
            self.assertEqual(bot.handle_user_text(1, command)[1], expected)
        bot.handle_user_text(1, "🆕 Новая игра")
        self.assertIsNone(bot.USER_STATES[1]["current_game"])
        self.assertEqual(len(bot.get_user_saved_games(1)), 1)


if __name__ == "__main__":
    unittest.main()
