import asyncio
import hashlib
import hmac
import inspect
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.parse import urlencode


def install_import_stubs() -> None:
    class DummyRouter:
        def message(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def identity_factory(*args, **kwargs):
        return object()

    class DummyWebAppInfo:
        def __init__(self, url: str):
            self.url = url

    class DummyInlineKeyboardButton:
        def __init__(self, text: str, web_app=None):
            self.text = text
            self.web_app = web_app

    class DummyInlineKeyboardMarkup:
        def __init__(self, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    class DummyResponse:
        def __init__(self, content="", status_code=200, **kwargs):
            self.content = content
            self.status_code = status_code
            self.headers = {}
            self.cookies = {}

        def set_cookie(self, key, value, **kwargs):
            self.cookies[key] = (value, kwargs)

        def delete_cookie(self, key, **kwargs):
            self.cookies.pop(key, None)

    class DummyRedirectResponse(DummyResponse):
        def __init__(self, url, status_code=307, **kwargs):
            super().__init__("", status_code, **kwargs)
            self.url = url

    class DummyJSONResponse(DummyResponse):
        pass

    class DummyFastAPI:
        def __init__(self, *args, **kwargs):
            self.routes = {}
            self.middleware_handler = None

        def middleware(self, middleware_type):
            def decorator(func):
                self.middleware_handler = func
                return func

            return decorator

        def get(self, path, **kwargs):
            def decorator(func):
                self.routes[("GET", path)] = func
                return func

            return decorator

        def post(self, path, **kwargs):
            def decorator(func):
                self.routes[("POST", path)] = func
                return func

            return decorator

    modules = {
        "feedparser": ModuleType("feedparser"),
        "httpx": ModuleType("httpx"),
        "yaml": ModuleType("yaml"),
        "uvicorn": ModuleType("uvicorn"),
        "apscheduler": ModuleType("apscheduler"),
        "apscheduler.schedulers": ModuleType("apscheduler.schedulers"),
        "apscheduler.schedulers.asyncio": ModuleType("apscheduler.schedulers.asyncio"),
        "bs4": ModuleType("bs4"),
        "dotenv": ModuleType("dotenv"),
        "aiogram": ModuleType("aiogram"),
        "aiogram.enums": ModuleType("aiogram.enums"),
        "aiogram.exceptions": ModuleType("aiogram.exceptions"),
        "aiogram.filters": ModuleType("aiogram.filters"),
        "aiogram.types": ModuleType("aiogram.types"),
        "aiogram.client": ModuleType("aiogram.client"),
        "aiogram.client.default": ModuleType("aiogram.client.default"),
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "qrcode": ModuleType("qrcode"),
    }
    modules["apscheduler.schedulers.asyncio"].AsyncIOScheduler = object
    modules["bs4"].BeautifulSoup = object
    modules["dotenv"].load_dotenv = lambda *args, **kwargs: None
    modules["yaml"].safe_load = lambda stream: {"bot": {"spam_filter": {"enabled": True, "keywords": []}}}
    modules["yaml"].safe_dump = lambda data, **kwargs: str(data)
    modules["aiogram"].Bot = object
    modules["aiogram"].Dispatcher = object
    modules["aiogram"].F = object()
    modules["aiogram"].Router = DummyRouter
    modules["aiogram.enums"].ParseMode = SimpleNamespace(HTML="HTML")
    modules["aiogram.exceptions"].TelegramAPIError = Exception
    modules["aiogram.filters"].Command = identity_factory
    modules["aiogram.filters"].CommandObject = object
    modules["aiogram.types"].InlineKeyboardButton = DummyInlineKeyboardButton
    modules["aiogram.types"].InlineKeyboardMarkup = DummyInlineKeyboardMarkup
    modules["aiogram.types"].Message = object
    modules["aiogram.types"].WebAppInfo = DummyWebAppInfo
    modules["aiogram.client.default"].DefaultBotProperties = identity_factory
    modules["fastapi"].Depends = identity_factory
    modules["fastapi"].FastAPI = DummyFastAPI
    modules["fastapi"].Form = identity_factory
    modules["fastapi"].HTTPException = Exception
    modules["fastapi"].Request = object
    modules["fastapi"].Response = DummyResponse
    modules["fastapi"].status = object()
    modules["fastapi.responses"].HTMLResponse = DummyResponse
    modules["fastapi.responses"].JSONResponse = DummyJSONResponse
    modules["fastapi.responses"].RedirectResponse = DummyRedirectResponse
    modules["fastapi.responses"].PlainTextResponse = DummyResponse
    modules["fastapi.responses"].FileResponse = DummyResponse
    modules["qrcode"].make = lambda *args, **kwargs: SimpleNamespace(save=lambda *a, **k: None)
    modules["uvicorn"].Server = object
    modules["uvicorn"].Config = identity_factory
    sys.modules.update({name: sys.modules.get(name, module) for name, module in modules.items()})


install_import_stubs()
import app


class FakeBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []
        self.edited_reply_markups: list[tuple[int, int, object]] = []
        self.sent_texts: list[str] = []
        self.sent_chat_ids: list[int] = []
        self.fail_chat_ids: set[int] = set()

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup=None,
    ) -> None:
        self.edited_reply_markups.append((chat_id, message_id, reply_markup))

    async def send_message(self, chat_id: int, text: str, disable_web_page_preview: bool = False):
        if chat_id in self.fail_chat_ids:
            raise RuntimeError("send failed")
        self.sent_chat_ids.append(chat_id)
        self.sent_texts.append(text)
        return SimpleNamespace(message_id=3003)


class FakePrivateMessage:
    def __init__(
        self,
        user_id: int,
        text: str | None = None,
        chat_type: str = "private",
        content_type: str = "text",
    ) -> None:
        self.chat = SimpleNamespace(id=user_id, type=chat_type)
        self.from_user = SimpleNamespace(
            id=user_id,
            first_name="Test",
            last_name="User",
            username=f"user{user_id}",
        )
        self.text = text
        self.caption = None
        self.content_type = content_type
        self.message_id = 5001
        self.answers: list[tuple[str, dict]] = []

    async def answer(self, text: str, **kwargs):
        self.answers.append((text, kwargs))
        return SimpleNamespace(message_id=6001)


class MonitorMessageCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = app.DB_PATH
        app.DB_PATH = Path(self.temp_dir.name) / "test.sqlite3"
        app.init_db()

    def tearDown(self) -> None:
        app.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_monitor_notification_send_is_recorded_for_later_deletion(self) -> None:
        old_bot = app.bot
        old_admin_chat_id = app.admin_chat_id
        old_admin_chat_ids = app.admin_chat_ids
        old_config = app.config
        fake_bot = FakeBot()
        app.bot = fake_bot
        app.admin_chat_id = 1001
        app.admin_chat_ids = []
        app.config = {"cleanup": {"monitor_message_delete_after_minutes": 1}}
        try:
            sent = asyncio.run(app.admin_send_monitor("monitor hit", "NodeSeek 新帖"))
            self.assertTrue(sent)
            self.assertEqual(["monitor hit"], fake_bot.sent_texts)
            with closing(sqlite3.connect(app.DB_PATH)) as conn:
                row = conn.execute(
                    "SELECT chat_id, message_id, monitor_name, delete_after_seconds FROM monitor_messages"
                ).fetchone()
            self.assertEqual((1001, 3003, "NodeSeek 新帖", 60), row)
        finally:
            app.bot = old_bot
            app.admin_chat_id = old_admin_chat_id
            app.admin_chat_ids = old_admin_chat_ids
            app.config = old_config

    def test_monitor_event_history_is_recorded(self) -> None:
        app.record_monitor_event("NodeSeek 新帖", "title", "https://example.com", ["关键词"], False)
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            row = conn.execute("SELECT monitor_name, title, pushed FROM monitor_events").fetchone()
        self.assertEqual(("NodeSeek 新帖", "title", 0), row)

    def test_monitor_notification_is_sent_to_all_admins(self) -> None:
        old_bot = app.bot
        old_admin_chat_ids = app.admin_chat_ids
        old_config = app.config
        fake_bot = FakeBot()
        app.bot = fake_bot
        app.admin_chat_ids = [1001, 1002, 1003]
        app.config = {"cleanup": {"monitor_message_delete_after_minutes": 1}}
        try:
            self.assertTrue(asyncio.run(app.admin_send_monitor("monitor hit", "NodeSeek 新帖")))
            self.assertEqual([1001, 1002, 1003], fake_bot.sent_chat_ids)
        finally:
            app.bot = old_bot
            app.admin_chat_ids = old_admin_chat_ids
            app.config = old_config

    def test_monitor_notification_continues_when_one_admin_fails(self) -> None:
        old_bot = app.bot
        old_admin_chat_ids = app.admin_chat_ids
        old_config = app.config
        fake_bot = FakeBot()
        fake_bot.fail_chat_ids.add(1002)
        app.bot = fake_bot
        app.admin_chat_ids = [1001, 1002, 1003]
        app.config = {"cleanup": {"monitor_message_delete_after_minutes": 1}}
        try:
            with self.assertLogs("tg-watchbot", level="ERROR"):
                self.assertTrue(asyncio.run(app.admin_send_monitor("monitor hit", "NodeSeek 新帖")))
            self.assertEqual([1001, 1003], fake_bot.sent_chat_ids)
        finally:
            app.bot = old_bot
            app.admin_chat_ids = old_admin_chat_ids
            app.config = old_config

    def test_outbound_message_is_recorded_in_conversation_log(self) -> None:
        app.upsert_user(2001, "User", "user")
        outbox_id = app.create_outbox_message(2001, "reply text", "web:inbox", 4004)
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT direction, source, text, forwarded FROM inbox_messages WHERE id=?", (outbox_id,)).fetchone()
        self.assertEqual(("out", "web:inbox", "reply text", 1), (row["direction"], row["source"], row["text"], row["forwarded"]))

    def test_save_message_map_supports_message_id_only_payload(self) -> None:
        app.save_message_map(1001, 3003, 2001, 4004)
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            row = conn.execute(
                "SELECT admin_chat_id, admin_message_id, user_id, user_message_id FROM message_map"
            ).fetchone()
        self.assertEqual((1001, 3003, 2001, 4004), row)

    def test_expired_monitor_message_is_deleted_and_removed_from_queue(self) -> None:
        app.record_monitor_message(1001, 2002, "NodeSeek 新帖", delete_after_seconds=60, sent_at_ts=1000)

        fake_bot = FakeBot()
        deleted_count = asyncio.run(app.delete_expired_monitor_messages(fake_bot, now_ts=1061))

        self.assertEqual(1, deleted_count)
        self.assertEqual([(1001, 2002)], fake_bot.deleted)
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            remaining = conn.execute("SELECT COUNT(*) FROM monitor_messages").fetchone()[0]
        self.assertEqual(0, remaining)

    def test_unexpired_monitor_message_is_kept(self) -> None:
        app.record_monitor_message(1001, 2002, "NodeSeek 新帖", delete_after_seconds=60, sent_at_ts=1000)

        fake_bot = FakeBot()
        deleted_count = asyncio.run(app.delete_expired_monitor_messages(fake_bot, now_ts=1059))

        self.assertEqual(0, deleted_count)
        self.assertEqual([], fake_bot.deleted)
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            remaining = conn.execute("SELECT COUNT(*) FROM monitor_messages").fetchone()[0]
        self.assertEqual(1, remaining)


class UserVerificationStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = app.DB_PATH
        app.DB_PATH = Path(self.temp_dir.name) / "verification.sqlite3"

    def tearDown(self) -> None:
        app.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_legacy_users_are_grandfathered_only_once(self) -> None:
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            conn.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    note TEXT DEFAULT '',
                    blocked INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO users(user_id, full_name, created_at, updated_at) VALUES(?,?,?,?)",
                (1001, "Legacy", "before", "before"),
            )
            conn.commit()

        app.init_db()
        legacy = app.get_user_verification(1001)
        self.assertIsNotNone(legacy)
        self.assertEqual("verified", legacy["status"])
        self.assertEqual("legacy", legacy["verification_method"])

        app.upsert_user(1002, "New", "new")
        app.init_db()
        self.assertIsNone(app.get_user_verification(1002))

    def test_turnstile_nonce_is_hashed_bound_and_expires(self) -> None:
        app.init_db()
        app.upsert_user(2001, "User", "user")
        challenge = app.begin_turnstile_verification(2001, now_ts=1000, ttl_seconds=10)
        row = app.get_user_verification(2001)

        self.assertEqual("pending_turnstile", challenge["status"])
        self.assertNotEqual(challenge["nonce"], row["turnstile_nonce_hash"])
        self.assertEqual(app.verification_nonce_hash(challenge["nonce"]), row["turnstile_nonce_hash"])
        self.assertTrue(app.turnstile_session_is_valid(2001, challenge["nonce"], now_ts=1009))
        self.assertFalse(app.turnstile_session_is_valid(2002, challenge["nonce"], now_ts=1009))
        self.assertFalse(app.turnstile_session_is_valid(2001, challenge["nonce"], now_ts=1010))

    def test_turnstile_can_advance_only_once_to_math(self) -> None:
        app.init_db()
        app.upsert_user(2001, "User", "user")
        challenge = app.begin_turnstile_verification(2001, now_ts=1000)

        math = app.advance_turnstile_to_math(2001, challenge["nonce"], now_ts=1001)
        duplicate = app.advance_turnstile_to_math(2001, challenge["nonce"], now_ts=1002)

        self.assertIsNotNone(math)
        self.assertEqual("pending_math", app.get_user_verification(2001)["status"])
        self.assertIsNone(duplicate)

    def test_math_challenges_stay_in_range_and_never_subtract_below_zero(self) -> None:
        for _ in range(100):
            question, answer = app.generate_math_challenge()
            self.assertRegex(question, r"^\d+ [+-] \d+ = \?$")
            self.assertGreaterEqual(answer, 0)
            self.assertLessEqual(answer, 40)

    def test_math_answer_verifies_or_enters_cooldown_after_three_errors(self) -> None:
        app.init_db()
        app.upsert_user(2001, "User", "user")
        challenge = app.begin_turnstile_verification(2001, now_ts=1000)
        app.advance_turnstile_to_math(2001, challenge["nonce"], now_ts=1001)
        row = app.get_user_verification(2001)
        correct_answer = int(row["math_answer"])
        wrong_answer = str(correct_answer + 1)

        invalid = app.submit_math_verification(2001, "not-a-number", now_ts=1002)
        self.assertEqual("invalid", invalid["result"])
        self.assertEqual(0, app.get_user_verification(2001)["math_attempts"])

        self.assertEqual(
            "incorrect",
            app.submit_math_verification(2001, wrong_answer, now_ts=1003)["result"],
        )
        self.assertEqual(
            "incorrect",
            app.submit_math_verification(2001, wrong_answer, now_ts=1004)["result"],
        )
        cooldown = app.submit_math_verification(2001, wrong_answer, now_ts=1005)
        self.assertEqual("cooldown", cooldown["result"])
        self.assertEqual("cooldown", app.get_user_verification(2001)["status"])
        self.assertEqual(
            "pending_turnstile",
            app.normalize_user_verification(2001, now_ts=1605)["status"],
        )

        restarted = app.begin_turnstile_verification(2001, now_ts=1606)
        app.advance_turnstile_to_math(2001, restarted["nonce"], now_ts=1607)
        correct_answer = str(app.get_user_verification(2001)["math_answer"])
        self.assertEqual(
            "verified",
            app.submit_math_verification(2001, correct_answer, now_ts=1608)["result"],
        )
        self.assertTrue(app.is_user_verified(2001))

    def test_expired_math_returns_to_turnstile_without_verifying(self) -> None:
        app.init_db()
        app.upsert_user(2001, "User", "user")
        challenge = app.begin_turnstile_verification(2001, now_ts=1000)
        app.advance_turnstile_to_math(2001, challenge["nonce"], now_ts=1001, ttl_seconds=10)
        answer = str(app.get_user_verification(2001)["math_answer"])

        result = app.submit_math_verification(2001, answer, now_ts=1011)

        self.assertEqual("expired", result["result"])
        self.assertFalse(app.is_user_verified(2001))
        self.assertEqual("pending_turnstile", app.get_user_verification(2001)["status"])

    def test_reset_user_verification_preserves_user_and_other_users(self) -> None:
        app.init_db()
        app.upsert_user(2001, "Reset User", "reset-user")
        app.upsert_user(2002, "Other User", "other-user")
        app.begin_turnstile_verification(2001, now_ts=1000)
        app.begin_turnstile_verification(2002, now_ts=1000)
        app.set_note(2001, "keep this note")
        app.verification_prompt_times[2001] = 1000
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            conn.execute(
                """
                INSERT INTO inbox_messages(
                    user_id, username, full_name, message_type, text, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (2001, "reset-user", "Reset User", "text", "keep this message", "now"),
            )
            conn.commit()

        self.assertTrue(app.reset_user_verification(2001))

        self.assertIsNotNone(app.get_user(2001))
        self.assertEqual("keep this note", app.get_user(2001)["note"])
        self.assertIsNone(app.get_user_verification(2001))
        self.assertIsNotNone(app.get_user_verification(2002))
        self.assertNotIn(2001, app.verification_prompt_times)
        self.assertFalse(app.reset_user_verification(2001))
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            message = conn.execute(
                "SELECT text FROM inbox_messages WHERE user_id=?",
                (2001,),
            ).fetchone()
        self.assertEqual(("keep this message",), message)

    def test_user_panel_exposes_post_only_verification_reset(self) -> None:
        old_admin_chat_id = os.environ.get("ADMIN_CHAT_ID")
        os.environ["ADMIN_CHAT_ID"] = "9999"
        try:
            app.init_db()
            app.upsert_user(2001, "Reset User", "reset-user")
            app.begin_turnstile_verification(2001, now_ts=1000)
            panel = app.create_panel_app()
            page = asyncio.run(panel.routes[("GET", "/users")]())
            reset_route = panel.routes[("POST", "/users/{user_id}/verification/reset")]

            self.assertIn(
                "method=post action='/users/2001/verification/reset'",
                page,
            )
            self.assertIn("重置验证（测试）", page)
            self.assertIn("验证：等待 Turnstile", page)
            self.assertNotIn(
                ("GET", "/users/{user_id}/verification/reset"),
                panel.routes,
            )

            response = asyncio.run(reset_route(2001))
            self.assertEqual(303, response.status_code)
            self.assertEqual("/users", response.url)
            self.assertIsNone(app.get_user_verification(2001))
            self.assertIsNotNone(app.get_user(2001))
        finally:
            if old_admin_chat_id is None:
                os.environ.pop("ADMIN_CHAT_ID", None)
            else:
                os.environ["ADMIN_CHAT_ID"] = old_admin_chat_id


class PrivateVerificationGateTest(unittest.TestCase):
    ENV_KEYS = [
        "BOT_VERIFICATION_ENABLED",
        "BOT_VERIFICATION_PUBLIC_BASE_URL",
        "BOT_VERIFICATION_SESSION_TTL_SECONDS",
        "BOT_VERIFICATION_MATH_MAX_ATTEMPTS",
        "BOT_VERIFICATION_COOLDOWN_SECONDS",
        "BOT_VERIFICATION_PROMPT_INTERVAL_SECONDS",
        "TURNSTILE_SITE_KEY",
        "TURNSTILE_VERIFY_ENDPOINT",
        "TURNSTILE_VERIFY_AUTH_TOKEN",
        "TURNSTILE_EXPECTED_HOSTNAME",
        "TURNSTILE_EXPECTED_ACTION",
        "TURNSTILE_TEST_MODE",
    ]

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = app.DB_PATH
        self.old_admin_chat_id = app.admin_chat_id
        self.old_admin_chat_ids = app.admin_chat_ids
        self.old_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        app.DB_PATH = Path(self.temp_dir.name) / "gate.sqlite3"
        app.admin_chat_id = None
        app.admin_chat_ids = []
        app.verification_prompt_times.clear()
        os.environ["BOT_VERIFICATION_ENABLED"] = "true"
        os.environ["BOT_VERIFICATION_PUBLIC_BASE_URL"] = "https://verify.example.test"
        os.environ["BOT_VERIFICATION_SESSION_TTL_SECONDS"] = "600"
        os.environ["BOT_VERIFICATION_MATH_MAX_ATTEMPTS"] = "3"
        os.environ["BOT_VERIFICATION_COOLDOWN_SECONDS"] = "600"
        os.environ["BOT_VERIFICATION_PROMPT_INTERVAL_SECONDS"] = "15"
        os.environ["TURNSTILE_SITE_KEY"] = "test-site-key"
        os.environ["TURNSTILE_VERIFY_ENDPOINT"] = "https://worker.example.test"
        os.environ["TURNSTILE_VERIFY_AUTH_TOKEN"] = "shared-siteverify-token"
        os.environ["TURNSTILE_EXPECTED_HOSTNAME"] = "verify.example.test"
        os.environ["TURNSTILE_EXPECTED_ACTION"] = "turnstile-spin-v1"
        os.environ["TURNSTILE_TEST_MODE"] = "false"
        app.init_db()

    def tearDown(self) -> None:
        app.DB_PATH = self.old_db_path
        app.admin_chat_id = self.old_admin_chat_id
        app.admin_chat_ids = self.old_admin_chat_ids
        app.verification_prompt_times.clear()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def test_first_private_message_is_discarded_and_gets_web_app_button(self) -> None:
        message = FakePrivateMessage(3001, "这是第一条消息")

        allowed = asyncio.run(app.handle_private_verification_gate(message, now_ts=1000))

        self.assertFalse(allowed)
        self.assertTrue(app.should_gate_private_message(message))
        self.assertEqual("pending_turnstile", app.get_user_verification(3001)["status"])
        self.assertIn("首次联系需要完成", message.answers[0][0])
        markup = message.answers[0][1]["reply_markup"]
        button = markup.inline_keyboard[0][0]
        self.assertEqual("开始人机验证", button.text)
        self.assertTrue(button.web_app.url.startswith("https://verify.example.test/verify/telegram?nonce="))
        verification = app.get_user_verification(3001)
        self.assertEqual(3001, verification["turnstile_prompt_chat_id"])
        self.assertEqual(6001, verification["turnstile_prompt_message_id"])
        with closing(sqlite3.connect(app.DB_PATH)) as conn:
            inbox_count = conn.execute("SELECT COUNT(*) FROM inbox_messages").fetchone()[0]
        self.assertEqual(0, inbox_count)

    def test_repeated_messages_do_not_regenerate_prompt_inside_interval(self) -> None:
        first = FakePrivateMessage(3001, "one")
        second = FakePrivateMessage(3001, "two")

        asyncio.run(app.handle_private_verification_gate(first, now_ts=1000))
        first_hash = app.get_user_verification(3001)["turnstile_nonce_hash"]
        asyncio.run(app.handle_private_verification_gate(second, now_ts=1001))

        self.assertEqual([], second.answers)
        self.assertEqual(first_hash, app.get_user_verification(3001)["turnstile_nonce_hash"])

    def test_active_turnstile_session_is_not_regenerated_after_prompt_interval(self) -> None:
        first = FakePrivateMessage(3001, "one")
        later = FakePrivateMessage(3001, "two")

        asyncio.run(app.handle_private_verification_gate(first, now_ts=1000))
        first_hash = app.get_user_verification(3001)["turnstile_nonce_hash"]
        asyncio.run(app.handle_private_verification_gate(later, now_ts=1016))

        self.assertEqual(first_hash, app.get_user_verification(3001)["turnstile_nonce_hash"])
        self.assertIn("上一条人机验证入口仍有效", later.answers[0][0])
        self.assertNotIn("reply_markup", later.answers[0][1])

    def test_math_stage_ignores_media_then_accepts_correct_text_answer(self) -> None:
        app.upsert_user(3001, "Test User", "user3001")
        challenge = app.begin_turnstile_verification(3001, now_ts=1000)
        app.advance_turnstile_to_math(3001, challenge["nonce"], now_ts=1001)
        answer = str(app.get_user_verification(3001)["math_answer"])

        media = FakePrivateMessage(3001, None, content_type="photo")
        self.assertFalse(asyncio.run(app.handle_private_verification_gate(media, now_ts=1002)))
        self.assertIn("请输入算数题的数字答案", media.answers[0][0])
        self.assertEqual(0, app.get_user_verification(3001)["math_attempts"])

        correct = FakePrivateMessage(3001, answer)
        self.assertFalse(asyncio.run(app.handle_private_verification_gate(correct, now_ts=1003)))
        self.assertIn("验证成功", correct.answers[0][0])
        self.assertTrue(app.is_user_verified(3001))
        self.assertFalse(app.should_gate_private_message(correct))

    def test_blocked_user_is_rejected_before_verification(self) -> None:
        app.upsert_user(3001, "Test User", "user3001")
        app.set_block(3001, True)
        message = FakePrivateMessage(3001, "/start")

        allowed = asyncio.run(app.handle_private_verification_gate(message, now_ts=1000))

        self.assertFalse(allowed)
        self.assertEqual("你当前无法发送消息。", message.answers[0][0])
        self.assertIsNone(app.get_user_verification(3001))

    def test_admin_group_and_disabled_modes_bypass_gate(self) -> None:
        private = FakePrivateMessage(3001, "hello")
        app.admin_chat_ids = [3001]
        self.assertFalse(app.should_gate_private_message(private))
        self.assertTrue(asyncio.run(app.handle_private_verification_gate(private, now_ts=1000)))

        app.admin_chat_ids = []
        group = FakePrivateMessage(3001, "hello", chat_type="group")
        self.assertFalse(app.should_gate_private_message(group))
        self.assertTrue(asyncio.run(app.handle_private_verification_gate(group, now_ts=1000)))

        os.environ["BOT_VERIFICATION_ENABLED"] = "false"
        self.assertFalse(app.should_gate_private_message(private))
        self.assertTrue(asyncio.run(app.handle_private_verification_gate(private, now_ts=1000)))

    def test_missing_https_public_url_fails_closed(self) -> None:
        os.environ["BOT_VERIFICATION_PUBLIC_BASE_URL"] = "http://127.0.0.1:8765"
        message = FakePrivateMessage(3001, "hello")

        allowed = asyncio.run(app.handle_private_verification_gate(message, now_ts=1000))

        self.assertFalse(allowed)
        self.assertIn("暂不可用", message.answers[0][0])
        self.assertFalse(app.is_user_verified(3001))


class TurnstileVerificationTest(unittest.TestCase):
    ENV_KEYS = [
        "TELEGRAM_BOT_TOKEN",
        "BOT_VERIFICATION_ENABLED",
        "BOT_VERIFICATION_PUBLIC_BASE_URL",
        "BOT_VERIFICATION_INITDATA_MAX_AGE_SECONDS",
        "BOT_VERIFICATION_MATH_TTL_SECONDS",
        "BOT_VERIFICATION_MATH_MAX_ATTEMPTS",
        "TURNSTILE_SITE_KEY",
        "TURNSTILE_VERIFY_ENDPOINT",
        "TURNSTILE_VERIFY_AUTH_TOKEN",
        "TURNSTILE_EXPECTED_HOSTNAME",
        "TURNSTILE_EXPECTED_ACTION",
        "TURNSTILE_TEST_MODE",
    ]

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = app.DB_PATH
        self.old_bot = app.bot
        self.old_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        app.DB_PATH = Path(self.temp_dir.name) / "turnstile.sqlite3"
        app.bot = None
        app.verification_api_buckets.clear()
        os.environ.update(
            {
                "TELEGRAM_BOT_TOKEN": "123456:test-token",
                "BOT_VERIFICATION_ENABLED": "true",
                "BOT_VERIFICATION_PUBLIC_BASE_URL": "https://verify.example.test",
                "BOT_VERIFICATION_INITDATA_MAX_AGE_SECONDS": "300",
                "BOT_VERIFICATION_MATH_TTL_SECONDS": "600",
                "BOT_VERIFICATION_MATH_MAX_ATTEMPTS": "3",
                "TURNSTILE_SITE_KEY": "test-site-key",
                "TURNSTILE_VERIFY_ENDPOINT": "https://worker.example.test",
                "TURNSTILE_VERIFY_AUTH_TOKEN": "shared-siteverify-token",
                "TURNSTILE_EXPECTED_HOSTNAME": "verify.example.test",
                "TURNSTILE_EXPECTED_ACTION": "turnstile-spin-v1",
                "TURNSTILE_TEST_MODE": "false",
            }
        )
        app.init_db()

    def tearDown(self) -> None:
        app.DB_PATH = self.old_db_path
        app.bot = self.old_bot
        app.verification_api_buckets.clear()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    @staticmethod
    def signed_init_data(
        user_id: int,
        auth_date: int,
        bot_token: str = "123456:test-token",
    ) -> str:
        values = {
            "auth_date": str(auth_date),
            "query_id": "AAE-test-query",
            "user": json.dumps(
                {"id": user_id, "first_name": "Test", "is_bot": False},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        values["hash"] = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return urlencode(values)

    def test_telegram_init_data_checks_signature_age_and_duplicate_keys(self) -> None:
        valid = self.signed_init_data(4001, auth_date=1000)
        identity = app.validate_telegram_init_data(
            valid,
            "123456:test-token",
            max_age_seconds=300,
            now_ts=1001,
        )
        self.assertEqual(4001, identity["user_id"])
        self.assertIsNone(
            app.validate_telegram_init_data(
                valid.replace("Test", "Mallory"),
                "123456:test-token",
                now_ts=1001,
            )
        )
        self.assertIsNone(
            app.validate_telegram_init_data(
                valid,
                "123456:test-token",
                max_age_seconds=300,
                now_ts=1301,
            )
        )
        self.assertIsNone(
            app.validate_telegram_init_data(
                valid + "&auth_date=1000",
                "123456:test-token",
                now_ts=1001,
            )
        )

    def test_verification_page_has_required_sdk_action_and_same_origin_api(self) -> None:
        page = app.verification_page_html(
            "safe_nonce-123",
            app.verification_settings(),
            "csp-nonce",
        )
        self.assertIn("https://telegram.org/js/telegram-web-app.js", page)
        self.assertIn("https://challenges.cloudflare.com/turnstile/v0/api.js", page)
        self.assertIn('data-action="turnstile-spin-v1"', page)
        self.assertIn('"turnstile-spin-v1"', page)
        self.assertIn('"test-site-key"', page)
        self.assertIn('fetch("/api/verify/status"', page)
        self.assertIn('fetch("/api/verify/turnstile"', page)
        self.assertIn('"safe_nonce-123"', page)
        self.assertNotIn("123456:test-token", page)

    def test_preflight_returns_current_state_before_checking_stale_nonce(self) -> None:
        app.upsert_user(4001, "Test User", "testuser")
        challenge = app.begin_turnstile_verification(4001, now_ts=1000)
        init_data = self.signed_init_data(4001, auth_date=1000)

        ready = app.telegram_verification_status(
            init_data,
            challenge["nonce"],
            now_ts=1001,
        )
        expired = app.telegram_verification_status(
            init_data,
            "wrong-nonce",
            now_ts=1001,
        )
        app.advance_turnstile_to_math(4001, challenge["nonce"], now_ts=1002)
        pending_math = app.telegram_verification_status(
            init_data,
            "old-nonce",
            now_ts=1003,
        )
        answer = str(app.get_user_verification(4001)["math_answer"])
        app.submit_math_verification(4001, answer, now_ts=1004)
        verified = app.telegram_verification_status(
            init_data,
            "old-nonce",
            now_ts=1005,
        )

        self.assertEqual({"ok": True, "status": "pending_turnstile"}, ready)
        self.assertEqual(
            {"ok": False, "error": "invalid-or-expired-challenge"},
            expired,
        )
        self.assertEqual({"ok": True, "status": "pending_math"}, pending_math)
        self.assertEqual({"ok": True, "status": "verified"}, verified)

    def test_preflight_rejects_unsigned_or_blocked_users(self) -> None:
        app.upsert_user(4001, "Test User", "testuser")
        challenge = app.begin_turnstile_verification(4001, now_ts=1000)
        init_data = self.signed_init_data(4001, auth_date=1000)

        self.assertEqual(
            {"ok": False, "error": "invalid-telegram-session"},
            app.telegram_verification_status(
                "unsigned",
                challenge["nonce"],
                now_ts=1001,
            ),
        )
        app.set_block(4001, True)
        self.assertEqual(
            {"ok": False, "error": "invalid-user"},
            app.telegram_verification_status(
                init_data,
                challenge["nonce"],
                now_ts=1001,
            ),
        )

    def test_configuration_fails_closed_and_test_mode_is_loopback_only(self) -> None:
        settings = app.verification_settings()
        self.assertEqual("", app.turnstile_configuration_error(settings))

        missing_endpoint = dict(settings, turnstile_verify_endpoint="")
        self.assertEqual(
            "missing-secure-verify-endpoint",
            app.turnstile_configuration_error(missing_endpoint),
        )
        public_test_mode = dict(settings, turnstile_test_mode=True)
        self.assertEqual(
            "test-mode-requires-loopback-host",
            app.turnstile_configuration_error(public_test_mode),
        )
        local_test_mode = dict(
            settings,
            turnstile_test_mode=True,
            public_base_url="http://127.0.0.1:8765",
            turnstile_verify_endpoint="",
            turnstile_expected_hostname="",
        )
        self.assertEqual("", app.turnstile_configuration_error(local_test_mode))

    def test_turnstile_success_advances_once_and_sends_math_question(self) -> None:
        app.upsert_user(4001, "Test User", "testuser")
        challenge = app.begin_turnstile_verification(4001, now_ts=1000)
        self.assertTrue(
            app.record_turnstile_prompt(
                4001,
                challenge["nonce"],
                4001,
                7001,
            )
        )
        init_data = self.signed_init_data(4001, auth_date=1000)
        old_verify = app.verify_turnstile_token
        fake_bot = FakeBot()
        app.bot = fake_bot

        async def valid_turnstile(token, remote_ip="", settings=None):
            self.assertEqual("turnstile-token", token)
            return {
                "success": True,
                "hostname": "verify.example.test",
                "action": "turnstile-spin-v1",
            }

        app.verify_turnstile_token = valid_turnstile
        try:
            result = asyncio.run(
                app.complete_turnstile_verification(
                    init_data,
                    challenge["nonce"],
                    "turnstile-token",
                    now_ts=1001,
                )
            )
            replay = asyncio.run(
                app.complete_turnstile_verification(
                    init_data,
                    challenge["nonce"],
                    "turnstile-token",
                    now_ts=1002,
                )
            )
        finally:
            app.verify_turnstile_token = old_verify

        self.assertEqual({"ok": True, "question_sent": True}, result)
        self.assertFalse(replay["ok"])
        self.assertEqual("pending_math", app.get_user_verification(4001)["status"])
        self.assertEqual([4001], fake_bot.sent_chat_ids)
        self.assertIn("第二阶段算数题", fake_bot.sent_texts[0])
        self.assertEqual([(4001, 7001, None)], fake_bot.edited_reply_markups)
        verification = app.get_user_verification(4001)
        self.assertIsNone(verification["turnstile_prompt_chat_id"])
        self.assertIsNone(verification["turnstile_prompt_message_id"])

    def test_concurrent_success_callbacks_only_send_one_math_question(self) -> None:
        app.upsert_user(4001, "Test User", "testuser")
        challenge = app.begin_turnstile_verification(4001, now_ts=1000)
        init_data = self.signed_init_data(4001, auth_date=1000)
        old_verify = app.verify_turnstile_token
        fake_bot = FakeBot()
        app.bot = fake_bot

        async def valid_turnstile(token, remote_ip="", settings=None):
            await asyncio.sleep(0)
            return {
                "success": True,
                "hostname": "verify.example.test",
                "action": "turnstile-spin-v1",
            }

        async def run_callbacks():
            return await asyncio.gather(
                app.complete_turnstile_verification(
                    init_data,
                    challenge["nonce"],
                    "token-one",
                    now_ts=1001,
                ),
                app.complete_turnstile_verification(
                    init_data,
                    challenge["nonce"],
                    "token-two",
                    now_ts=1001,
                ),
            )

        app.verify_turnstile_token = valid_turnstile
        try:
            results = asyncio.run(run_callbacks())
        finally:
            app.verify_turnstile_token = old_verify

        self.assertEqual(1, sum(1 for result in results if result["ok"]))
        self.assertEqual([4001], fake_bot.sent_chat_ids)
        self.assertEqual("pending_math", app.get_user_verification(4001)["status"])

    def test_turnstile_mismatch_and_wrong_nonce_do_not_advance(self) -> None:
        app.upsert_user(4001, "Test User", "testuser")
        challenge = app.begin_turnstile_verification(4001, now_ts=1000)
        init_data = self.signed_init_data(4001, auth_date=1000)
        old_verify = app.verify_turnstile_token
        calls = []

        async def wrong_action(token, remote_ip="", settings=None):
            calls.append(token)
            return {
                "success": True,
                "hostname": "verify.example.test",
                "action": "unexpected-action",
            }

        app.verify_turnstile_token = wrong_action
        try:
            wrong_nonce = asyncio.run(
                app.complete_turnstile_verification(
                    init_data,
                    "wrong-nonce",
                    "turnstile-token",
                    now_ts=1001,
                )
            )
            mismatch = asyncio.run(
                app.complete_turnstile_verification(
                    init_data,
                    challenge["nonce"],
                    "turnstile-token",
                    now_ts=1001,
                )
            )
        finally:
            app.verify_turnstile_token = old_verify

        self.assertEqual("invalid-or-expired-challenge", wrong_nonce["error"])
        self.assertEqual(["turnstile-token"], calls)
        self.assertEqual("turnstile-action-mismatch", mismatch["error"])
        self.assertEqual("pending_turnstile", app.get_user_verification(4001)["status"])

    def test_turnstile_hostname_mismatch_and_network_failure_fail_closed(self) -> None:
        app.upsert_user(4001, "Test User", "testuser")
        challenge = app.begin_turnstile_verification(4001, now_ts=1000)
        init_data = self.signed_init_data(4001, auth_date=1000)
        old_verify = app.verify_turnstile_token

        async def wrong_hostname(token, remote_ip="", settings=None):
            return {
                "success": True,
                "hostname": "attacker.example.test",
                "action": "turnstile-spin-v1",
            }

        app.verify_turnstile_token = wrong_hostname
        try:
            mismatch = asyncio.run(
                app.complete_turnstile_verification(
                    init_data,
                    challenge["nonce"],
                    "turnstile-token",
                    now_ts=1001,
                )
            )
        finally:
            app.verify_turnstile_token = old_verify
        self.assertEqual("turnstile-hostname-mismatch", mismatch["error"])
        self.assertEqual("pending_turnstile", app.get_user_verification(4001)["status"])

        old_client = getattr(app.httpx, "AsyncClient", None)

        class FailingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, *args, **kwargs):
                raise TimeoutError("simulated")

        app.httpx.AsyncClient = FailingClient
        try:
            with self.assertLogs("tg-watchbot", level="WARNING"):
                result = asyncio.run(
                    app.verify_turnstile_token(
                        "turnstile-token",
                        settings=app.verification_settings(),
                    )
                )
        finally:
            if old_client is None:
                delattr(app.httpx, "AsyncClient")
            else:
                app.httpx.AsyncClient = old_client
        self.assertFalse(result["success"])
        self.assertEqual(["verification-request-failed"], result["error-codes"])

    def test_siteverify_bearer_auth_is_sent_only_to_configured_worker(self) -> None:
        old_client = getattr(app.httpx, "AsyncClient", None)
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "success": True,
                    "hostname": "verify.example.test",
                    "action": "turnstile-spin-v1",
                }

        class CapturingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, endpoint, **kwargs):
                calls.append((endpoint, kwargs))
                return FakeResponse()

        app.httpx.AsyncClient = CapturingClient
        try:
            production = app.verification_settings()
            protected_result = asyncio.run(
                app.verify_turnstile_token(
                    "protected-token",
                    settings=production,
                )
            )
            compatible_result = asyncio.run(
                app.verify_turnstile_token(
                    "compatible-token",
                    settings=dict(
                        production,
                        turnstile_verify_auth_token="",
                    ),
                )
            )
            test_result = asyncio.run(
                app.verify_turnstile_token(
                    "test-mode-token",
                    settings=dict(
                        production,
                        public_base_url="http://127.0.0.1:8765",
                        turnstile_test_mode=True,
                    ),
                )
            )
        finally:
            if old_client is None:
                delattr(app.httpx, "AsyncClient")
            else:
                app.httpx.AsyncClient = old_client

        self.assertTrue(protected_result["success"])
        self.assertTrue(compatible_result["success"])
        self.assertTrue(test_result["success"])
        self.assertEqual(
            {"Authorization": "Bearer shared-siteverify-token"},
            calls[0][1]["headers"],
        )
        self.assertEqual({}, calls[1][1]["headers"])
        self.assertEqual(app.TURNSTILE_SITEVERIFY_URL, calls[2][0])
        self.assertEqual({}, calls[2][1]["headers"])

    def test_public_routes_are_exact_and_security_headers_are_strict(self) -> None:
        self.assertTrue(app.panel_path_is_public("/verify/telegram"))
        self.assertTrue(app.panel_path_is_public("/api/verify/status"))
        self.assertTrue(app.panel_path_is_public("/api/verify/turnstile"))
        self.assertFalse(app.panel_path_is_public("/verify/telegram/anything"))
        response = SimpleNamespace(headers={})
        app.apply_verification_security_headers(response, "safe-csp-nonce")
        self.assertEqual("no-store, max-age=0", response.headers["Cache-Control"])
        self.assertIn(
            "https://challenges.cloudflare.com",
            response.headers["Content-Security-Policy"],
        )
        self.assertIn("'nonce-safe-csp-nonce'", response.headers["Content-Security-Policy"])

    def test_verification_api_rate_limit_uses_sliding_window(self) -> None:
        for index in range(10):
            self.assertFalse(
                app.verification_api_rate_limited("127.0.0.1", now_ts=1000 + index)
            )
        self.assertTrue(app.verification_api_rate_limited("127.0.0.1", now_ts=1010))
        self.assertFalse(app.verification_api_rate_limited("127.0.0.1", now_ts=1071))

    def test_panel_routes_serve_verification_without_opening_protected_pages(self) -> None:
        panel = app.create_panel_app()
        page_route = panel.routes[("GET", "/verify/telegram")]
        page_response = asyncio.run(page_route("safe_nonce-123"))
        self.assertEqual(200, page_response.status_code)
        self.assertIn("请完成人机验证", page_response.content)
        self.assertIn("Content-Security-Policy", page_response.headers)

        public_request = SimpleNamespace(
            url=SimpleNamespace(path="/verify/telegram"),
            headers={},
            cookies={},
            client=SimpleNamespace(host="127.0.0.1"),
        )
        protected_request = SimpleNamespace(
            url=SimpleNamespace(path="/users"),
            headers={},
            cookies={},
            client=SimpleNamespace(host="127.0.0.1"),
        )

        async def call_next(request):
            return sys.modules["fastapi.responses"].HTMLResponse("ok")

        public_response = asyncio.run(panel.middleware_handler(public_request, call_next))
        protected_response = asyncio.run(panel.middleware_handler(protected_request, call_next))
        self.assertEqual(200, public_response.status_code)
        self.assertEqual("no-store, max-age=0", public_response.headers["Cache-Control"])
        self.assertEqual(303, protected_response.status_code)
        self.assertEqual("/login", protected_response.url)

    def test_panel_api_maps_callback_result_and_rejects_oversized_body(self) -> None:
        panel = app.create_panel_app()
        api_route = panel.routes[("POST", "/api/verify/turnstile")]
        status_route = panel.routes[("POST", "/api/verify/status")]
        old_complete = app.complete_turnstile_verification
        old_status = app.telegram_verification_status

        async def accepted(*args, **kwargs):
            return {"ok": True, "question_sent": True}

        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            url=SimpleNamespace(path="/api/verify/turnstile"),
            headers={},
            cookies={},
        )
        app.complete_turnstile_verification = accepted
        app.telegram_verification_status = lambda *args, **kwargs: {
            "ok": True,
            "status": "verified",
        }
        try:
            response = asyncio.run(
                api_route(
                    request,
                    "signed-init-data",
                    "safe_nonce-123",
                    "turnstile-token",
                )
            )
            status_response = asyncio.run(
                status_route(
                    request,
                    "signed-init-data",
                    "safe_nonce-123",
                )
            )
        finally:
            app.complete_turnstile_verification = old_complete
            app.telegram_verification_status = old_status
        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "question_sent": True}, response.content)
        self.assertEqual(200, status_response.status_code)
        self.assertEqual(
            {"ok": True, "status": "verified"},
            status_response.content,
        )

        oversized_request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            url=SimpleNamespace(path="/api/verify/turnstile"),
            headers={"content-length": "20000"},
            cookies={},
        )

        async def should_not_run(request):
            raise AssertionError("oversized request reached route")

        oversized = asyncio.run(
            panel.middleware_handler(oversized_request, should_not_run)
        )
        self.assertEqual(413, oversized.status_code)


class BotConfigurationTest(unittest.TestCase):
    def test_env_example_documents_verification_without_turnstile_secret(self) -> None:
        env_example = Path(".env.example").read_text(encoding="utf-8")
        for key in [
            "BOT_VERIFICATION_ENABLED=false",
            "BOT_VERIFICATION_PUBLIC_BASE_URL=",
            "BOT_VERIFICATION_MATH_TTL_SECONDS=600",
            "BOT_VERIFICATION_MATH_MAX_ATTEMPTS=3",
            "TURNSTILE_SITE_KEY=",
            "TURNSTILE_VERIFY_ENDPOINT=",
            "TURNSTILE_VERIFY_AUTH_TOKEN=",
            "TURNSTILE_EXPECTED_HOSTNAME=",
            "TURNSTILE_EXPECTED_ACTION=turnstile-spin-v1",
            "TURNSTILE_TEST_MODE=false",
        ]:
            self.assertIn(key, env_example)
        self.assertNotIn("TURNSTILE_SECRET_KEY=", env_example)

    def test_readme_documents_local_and_production_verification_boundaries(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("新用户两阶段验证", readme)
        self.assertIn("https://github.com/u1ra/tg-watchbot-verify", readme)
        self.assertIn("BOT_VERIFICATION_ENABLED", readme)
        self.assertIn("TURNSTILE_", readme)

    def test_readme_ai_deployment_prompts_use_current_repo_and_safe_defaults(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        for expected in [
            "AI 一键部署",
            "AI 一键升级",
            "https://github.com/u1ra/tg-watchbot.git",
            "不得覆盖已有 .env、config.yaml 或 SQLite 数据库",
            "保持 BOT_VERIFICATION_ENABLED=false",
            "不要输出任何密钥内容",
        ]:
            self.assertIn(expected, readme)
        clone_lines = [
            line.strip()
            for line in readme.splitlines()
            if line.strip().startswith("git clone ")
        ]
        self.assertTrue(clone_lines)
        self.assertTrue(
            all("github.com/u1ra/tg-watchbot.git" in line for line in clone_lines)
        )

    def test_parse_admin_chat_ids_keeps_unique_first_three(self) -> None:
        self.assertEqual([1, 2, 3], app.parse_admin_chat_ids("1,2 2;3,4"))

    def test_bot_is_not_configured_without_token_or_admin_chat_id(self) -> None:
        old_token = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        old_admin = os.environ.pop("ADMIN_CHAT_ID", None)
        try:
            self.assertFalse(app.bot_env_configured())
        finally:
            if old_token is not None:
                os.environ["TELEGRAM_BOT_TOKEN"] = old_token
            if old_admin is not None:
                os.environ["ADMIN_CHAT_ID"] = old_admin

    def test_bot_is_configured_with_token_and_admin_chat_id(self) -> None:
        old_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        old_admin = os.environ.get("ADMIN_CHAT_ID")
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456:test-token"
        os.environ["ADMIN_CHAT_ID"] = "1001"
        try:
            self.assertTrue(app.bot_env_configured())
        finally:
            if old_token is None:
                os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            else:
                os.environ["TELEGRAM_BOT_TOKEN"] = old_token
            if old_admin is None:
                os.environ.pop("ADMIN_CHAT_ID", None)
            else:
                os.environ["ADMIN_CHAT_ID"] = old_admin

    def test_write_env_values_preserves_existing_session_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_env_path = app.ENV_PATH
            app.ENV_PATH = Path(temp_dir) / ".env"
            app.ENV_PATH.write_text("WEB_PANEL_SESSION_SECRET=keep-me\n", encoding="utf-8")
            try:
                app.write_env_values({
                    "TELEGRAM_BOT_TOKEN": "123456:test-token",
                    "ADMIN_CHAT_ID": "1001",
                    "WEB_PANEL_USER": "admin",
                    "WEB_PANEL_PASSWORD": "change-me",
                })
                self.assertIn(
                    "WEB_PANEL_SESSION_SECRET=keep-me",
                    app.ENV_PATH.read_text(encoding="utf-8"),
                )
            finally:
                app.ENV_PATH = old_env_path

    def test_write_env_values_preserves_verification_and_unknown_existing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_env_path = app.ENV_PATH
            app.ENV_PATH = Path(temp_dir) / ".env"
            app.ENV_PATH.write_text(
                "BOT_VERIFICATION_ENABLED=true\n"
                "TURNSTILE_SITE_KEY=existing-site-key\n"
                "TURNSTILE_VERIFY_AUTH_TOKEN=existing-auth-token\n"
                "CUSTOM_DEPLOYMENT_VALUE=keep-me\n",
                encoding="utf-8",
            )
            try:
                app.write_env_values({"LOG_LEVEL": "DEBUG"})
                saved = app.ENV_PATH.read_text(encoding="utf-8")
            finally:
                app.ENV_PATH = old_env_path
        self.assertIn("BOT_VERIFICATION_ENABLED=true", saved)
        self.assertIn("TURNSTILE_SITE_KEY=existing-site-key", saved)
        self.assertIn("TURNSTILE_VERIFY_AUTH_TOKEN=existing-auth-token", saved)
        self.assertIn("CUSTOM_DEPLOYMENT_VALUE=keep-me", saved)

    def test_verification_form_normalizes_booleans_numbers_and_hostname(self) -> None:
        normalized = app.normalize_verification_form_values(
            {
                "BOT_VERIFICATION_ENABLED": "on",
                "TURNSTILE_TEST_MODE": "",
                "BOT_VERIFICATION_PUBLIC_BASE_URL": "https://bot.example.com/",
                "BOT_VERIFICATION_INITDATA_MAX_AGE_SECONDS": "0",
                "BOT_VERIFICATION_SESSION_TTL_SECONDS": "invalid",
                "BOT_VERIFICATION_MATH_TTL_SECONDS": "900",
                "BOT_VERIFICATION_MATH_MAX_ATTEMPTS": "5",
                "BOT_VERIFICATION_COOLDOWN_SECONDS": "1200",
                "BOT_VERIFICATION_PROMPT_INTERVAL_SECONDS": "20",
                "TURNSTILE_SITE_KEY": " site-key ",
                "TURNSTILE_VERIFY_ENDPOINT": " https://worker.example.test ",
                "TURNSTILE_VERIFY_AUTH_TOKEN": " shared-siteverify-token ",
                "TURNSTILE_EXPECTED_HOSTNAME": "Bot.Example.COM.",
                "TURNSTILE_EXPECTED_ACTION": "",
            }
        )
        self.assertEqual("true", normalized["BOT_VERIFICATION_ENABLED"])
        self.assertEqual("false", normalized["TURNSTILE_TEST_MODE"])
        self.assertEqual("https://bot.example.com", normalized["BOT_VERIFICATION_PUBLIC_BASE_URL"])
        self.assertEqual("1", normalized["BOT_VERIFICATION_INITDATA_MAX_AGE_SECONDS"])
        self.assertEqual("600", normalized["BOT_VERIFICATION_SESSION_TTL_SECONDS"])
        self.assertEqual(
            "shared-siteverify-token",
            normalized["TURNSTILE_VERIFY_AUTH_TOKEN"],
        )
        self.assertEqual("bot.example.com", normalized["TURNSTILE_EXPECTED_HOSTNAME"])
        self.assertEqual("turnstile-spin-v1", normalized["TURNSTILE_EXPECTED_ACTION"])

    def test_verification_admin_form_exposes_config_without_turnstile_secret(self) -> None:
        values = dict(app.VERIFICATION_ENV_DEFAULTS)
        values.update(
            {
                "WEB_PANEL_ENABLED": "true",
                "BOT_VERIFICATION_ENABLED": "true",
                "BOT_VERIFICATION_PUBLIC_BASE_URL": "https://bot.example.com",
                "TURNSTILE_SITE_KEY": "site-key",
                "TURNSTILE_VERIFY_ENDPOINT": "https://worker.example.test",
                "TURNSTILE_VERIFY_AUTH_TOKEN": "shared-siteverify-token",
                "TURNSTILE_EXPECTED_HOSTNAME": "bot.example.com",
            }
        )
        form = app.verification_settings_form_html(values)
        for key in app.VERIFICATION_ENV_DEFAULTS:
            self.assertIn(f"name={key}", form)
        self.assertIn("必要参数完整", form)
        self.assertIn("name=TURNSTILE_VERIFY_AUTH_TOKEN type=password", form)
        self.assertNotIn("name=TURNSTILE_SECRET", form)

    def test_both_admin_settings_routes_accept_verification_fields(self) -> None:
        panel = app.create_panel_app()
        expected = set(app.VERIFICATION_ENV_DEFAULTS)
        for route_key in [("POST", "/settings"), ("POST", "/users/settings")]:
            route_fields = set(inspect.signature(panel.routes[route_key]).parameters)
            self.assertTrue(expected.issubset(route_fields))


class PanelHtmlContractTest(unittest.TestCase):
    def test_login_form_keeps_expected_fields(self) -> None:
        html = app.login_page()
        self.assertIn("action=/login", html)
        self.assertIn("name=username", html)
        self.assertIn("name=password", html)
        self.assertIn("data-theme-toggle", html)

    def test_layout_includes_theme_toggle(self) -> None:
        html = app.layout("测试", "<p>ok</p>")
        self.assertIn("tg_watchbot_theme", html)
        self.assertIn("data-theme-toggle", html)
        self.assertIn("html[data-theme='dark']", html)

    def test_panel_cookie_secure_follows_request_scheme(self) -> None:
        old_value = os.environ.pop("WEB_PANEL_COOKIE_SECURE", None)
        try:
            self.assertFalse(app.panel_cookie_secure(SimpleNamespace(url=SimpleNamespace(scheme="http"))))
            self.assertTrue(app.panel_cookie_secure(SimpleNamespace(url=SimpleNamespace(scheme="https"))))
        finally:
            if old_value is not None:
                os.environ["WEB_PANEL_COOKIE_SECURE"] = old_value

    def test_monitor_form_keeps_backend_field_names(self) -> None:
        html = app.monitor_form_html()
        for expected in [
            "action='/monitor/create'",
            "name=name",
            "name=mtype",
            "name=url",
            "name=interval_seconds",
            "name=keywords",
            "name=exclude_keywords",
            "name=item_selector",
            "name=title_selector",
            "name=link_selector",
            "name=keyword_match",
            "name=new_item",
            "name=price_change",
            "name=stock_change",
            "name=notify_telegram",
        ]:
            self.assertIn(expected, html)

    def test_monitor_form_defaults_to_30_seconds_with_1_second_minimum(self) -> None:
        html = app.monitor_form_html()
        self.assertIn("最低 1，默认 30", html)
        self.assertIn("min=1", html)
        self.assertIn("value='30'", html)

    def test_monitor_from_form_clamps_interval_to_one_second(self) -> None:
        monitor = app.monitor_from_form(
            None,
            "测试",
            "rss",
            "https://example.com/feed",
            0,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            True,
            True,
            False,
            False,
        )
        self.assertEqual(1, monitor["interval_seconds"])

    def test_monitor_form_places_exclude_keywords_after_keywords_and_round_trips_values(self) -> None:
        html = app.monitor_form_html({
            "type": "rss",
            "keywords": ["VPS", "优惠"],
            "exclude_keywords": ["广告", "已售"],
            "notify_on": {"keyword_match": True},
        })
        keywords_pos = html.index("name=keywords")
        exclude_pos = html.index("name=exclude_keywords")
        selectors_pos = html.index("Web 选择器")
        self.assertLess(keywords_pos, exclude_pos)
        self.assertLess(exclude_pos, selectors_pos)
        self.assertIn("广告\n已售", html)

    def test_monitor_from_form_parses_exclude_keywords_and_item_blocked_uses_them(self) -> None:
        monitor = app.monitor_from_form(
            None,
            "测试",
            "rss",
            "https://example.com/feed",
            30,
            "VPS\n优惠",
            "广告\n已售",
            "",
            "",
            "",
            "",
            "",
            True,
            True,
            False,
            False,
        )
        self.assertEqual(["VPS", "优惠"], monitor["keywords"])
        self.assertEqual(["广告", "已售"], monitor["exclude_keywords"])
        blocked, reason = app.item_blocked(
            app.MonitorItem("item-1", "VPS 优惠", "https://example.com/1", "这是广告内容"),
            monitor,
        )
        self.assertTrue(blocked)
        self.assertIn("广告", reason)

    def test_monitor_form_can_disable_telegram_notification(self) -> None:
        monitor = {
            "type": "rss",
            "interval_seconds": 60,
            "notify_telegram": False,
            "notify_on": {"keyword_match": True},
        }
        html = app.monitor_form_html(monitor)
        self.assertIn("name=notify_telegram", html)
        self.assertNotIn("name=notify_telegram checked", html)

    def test_layout_groups_navigation_by_domain(self) -> None:
        html = app.layout("测试", "<p>ok</p>")
        for expected in ["<b>常用</b>", "<b>转发</b>", "<b>设置</b>", "<b>系统</b>", "收件箱", "群监听"]:
            self.assertIn(expected, html)

    def test_inbox_copy_describes_two_way_conversation(self) -> None:
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("这里显示双向机器人对话记录", source)
        self.assertIn("管理员 -> 用户", source)

    def test_settings_page_warns_about_public_bind(self) -> None:
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("公网提示", source)
        self.assertIn("0.0.0.0", source)
        self.assertIn("docker-compose.yml", source)

    def test_users_page_keeps_shared_settings_form(self) -> None:
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("action='/users/settings'", source)
        self.assertIn("这里和“Bot / 面板设置”共用同一份 .env", source)

    def test_group_monitor_form_keeps_backend_field_names(self) -> None:
        html = app.group_monitor_form_html()
        for expected in [
            "action='/group-monitors/create'",
            "name=name",
            "name=chat_id",
            "name=keywords",
            "name=exclude_keywords",
            "name=enabled",
            "name=notify_telegram",
            "name=listen_source",
            "name=summary_mode",
            "name=ai_interface",
            "name=ai_base_url",
            "name=ai_api_key",
            "name=ai_model",
            "name=ai_temperature",
            "name=ai_timeout_seconds",
            "name=ai_prompt",
            "name=ai_min_interval_seconds",
            "name=ai_dedupe_window_seconds",
        ]:
            self.assertIn(expected, html)


class SpamAndTemplateConfigTest(unittest.TestCase):
    def test_spam_keyword_hits_follow_config(self) -> None:
        old_config = app.config
        app.config = {"bot": {"spam_filter": {"enabled": True, "keywords": ["博彩", "投资"]}}}
        try:
            self.assertEqual(["博彩"], app.spam_keyword_hits("这里有博彩广告"))
        finally:
            app.config = old_config

    def test_quick_replies_are_loaded_from_config(self) -> None:
        old_config = app.config
        app.config = {"bot": {"quick_replies": [{"title": "收到", "text": "稍后处理"}]}}
        try:
            self.assertEqual("收到", app.list_quick_replies()[0]["title"])
        finally:
            app.config = old_config

    def test_update_spam_keywords_writes_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_config_path = app.CONFIG_PATH
            old_config = app.config
            app.CONFIG_PATH = Path(temp_dir) / "config.yaml"
            app.CONFIG_PATH.write_text("bot:\n  spam_filter:\n    enabled: true\n    keywords: []\n", encoding="utf-8")
            app.config = {"bot": {"spam_filter": {"enabled": True, "keywords": []}}}
            try:
                self.assertEqual(["广告"], app.update_spam_keywords("add", "广告"))
                self.assertEqual([], app.update_spam_keywords("delete", "广告"))
            finally:
                app.CONFIG_PATH = old_config_path
                app.config = old_config


class GroupMonitorTest(unittest.TestCase):
    def test_ai_api_url_supports_v1_and_plain_base(self) -> None:
        self.assertEqual("https://api.example.com/v1/responses", app.ai_api_url("https://api.example.com", "/responses"))
        self.assertEqual("https://api.example.com/v1/chat/completions", app.ai_api_url("https://api.example.com/v1", "/chat/completions"))

    def test_extract_responses_text_and_chat_text(self) -> None:
        self.assertEqual(
            "hello",
            app.extract_responses_text({"output_text": "hello"}),
        )
        self.assertEqual(
            "a\nb",
            app.extract_responses_text(
                {"output": [{"content": [{"text": "a"}, {"content": "b"}]}]}
            ),
        )
        self.assertEqual(
            "ok",
            app.extract_chat_text({"choices": [{"message": {"content": "ok"}}]}),
        )

    def test_cfg_save_normalizes_group_monitor_ai_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_config_path = app.CONFIG_PATH
            old_config = app.config
            old_reload = app.reload_scheduler_jobs
            app.CONFIG_PATH = Path(temp_dir) / "config.yaml"
            app.reload_scheduler_jobs = lambda: None
            try:
                cfg = {
                    "monitors": [],
                    "group_monitors": [
                        {
                            "enabled": True,
                            "chat_id": "-10099",
                            "keywords": ["vps"],
                            "exclude_keywords": [],
                            "summary_mode": "bad-mode",
                            "ai_interface": "bad-iface",
                            "ai_temperature": "x",
                            "ai_timeout_seconds": "0",
                        }
                    ],
                }
                app.cfg_save(cfg)
                saved = app.config["group_monitors"][0]
                self.assertEqual(-10099, saved["chat_id"])
                self.assertEqual("template", saved["summary_mode"])
                self.assertEqual("responses", saved["ai_interface"])
                self.assertEqual("bot", saved["listen_source"])
                self.assertEqual(0.2, saved["ai_temperature"])
                self.assertEqual(1, saved["ai_timeout_seconds"])
                self.assertEqual(app.DEFAULT_GROUP_AI_MIN_INTERVAL_SECONDS, saved["ai_min_interval_seconds"])
                self.assertEqual(app.DEFAULT_GROUP_AI_DEDUPE_WINDOW_SECONDS, saved["ai_dedupe_window_seconds"])
            finally:
                app.CONFIG_PATH = old_config_path
                app.config = old_config
                app.reload_scheduler_jobs = old_reload

    def test_build_group_ai_system_prompt_allows_custom_prompt(self) -> None:
        text = app.build_group_ai_system_prompt("请按项目符号输出")
        self.assertIn("Telegram 群消息摘要助手", text)
        self.assertIn("请按项目符号输出", text)

    def test_group_monitor_allow_send_applies_interval_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_db_path = app.DB_PATH
            app.DB_PATH = Path(temp_dir) / "test.sqlite3"
            app.init_db()
            monitor = {
                "name": "测试群",
                "ai_min_interval_seconds": 30,
                "ai_dedupe_window_seconds": 120,
            }
            try:
                ok1, reason1 = app.group_monitor_allow_send(monitor, "fp1", now_ts=1000)
                ok2, reason2 = app.group_monitor_allow_send(monitor, "fp2", now_ts=1010)
                ok3, reason3 = app.group_monitor_allow_send(monitor, "fp1", now_ts=1040)
                self.assertTrue(ok1)
                self.assertEqual("", reason1)
                self.assertFalse(ok2)
                self.assertIn("min-interval", reason2)
                self.assertFalse(ok3)
                self.assertIn("dedupe", reason3)
            finally:
                app.DB_PATH = old_db_path


class MonitorRuntimeAndUpdateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = app.DB_PATH
        app.DB_PATH = Path(self.temp_dir.name) / "test.sqlite3"
        app.init_db()

    def tearDown(self) -> None:
        app.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_record_monitor_runtime_tracks_failures(self) -> None:
        app.record_monitor_runtime("m1", ok=False, duration_ms=120, sent_count=0, error="oops")
        app.record_monitor_runtime("m1", ok=False, duration_ms=90, sent_count=0, error="oops2")
        app.record_monitor_runtime("m1", ok=True, duration_ms=70, sent_count=2)
        data = app.list_monitor_runtime_status()["m1"]
        self.assertEqual(0, data["consecutive_failures"])
        self.assertEqual(2, data["last_sent_count"])
        self.assertEqual(70, data["last_duration_ms"])

    def test_git_update_status_parses_ahead_behind_and_dirty(self) -> None:
        old_git_run = app.git_run

        class FakeResult:
            def __init__(self, out: str):
                self.stdout = out

        def fake_git_run(repo_dir, args, check=True):
            cmd = " ".join(args)
            if cmd.startswith("fetch "):
                return FakeResult("")
            if cmd == "rev-parse HEAD":
                return FakeResult("abc123\n")
            if cmd == "rev-parse origin/main":
                return FakeResult("def456\n")
            if cmd.startswith("rev-list --left-right --count"):
                return FakeResult("2 5\n")
            if cmd == "status --porcelain":
                return FakeResult(" M app.py\n")
            raise AssertionError(f"unexpected git command: {cmd}")

        app.git_run = fake_git_run
        try:
            st = app.git_update_status(Path("."), "main", fetch_remote=True)
            self.assertEqual("abc123", st["head"])
            self.assertEqual("def456", st["remote_head"])
            self.assertEqual(2, st["ahead"])
            self.assertEqual(5, st["behind"])
            self.assertTrue(st["dirty"])
        finally:
            app.git_run = old_git_run

    def test_group_monitor_for_chat_returns_enabled_target(self) -> None:
        old_config = app.config
        app.config = {
            "group_monitors": [
                {"enabled": True, "chat_id": -10001, "keywords": ["vps"], "exclude_keywords": []},
                {"enabled": False, "chat_id": -10002, "keywords": ["api"]},
            ]
        }
        try:
            monitor = app.group_monitor_for_chat(-10001)
            self.assertIsNotNone(monitor)
            self.assertEqual(-10001, monitor["chat_id"])
            self.assertIsNone(app.group_monitor_for_chat(-10002))
        finally:
            app.config = old_config

    def test_group_monitor_for_chat_and_source_returns_matched_monitor(self) -> None:
        old_config = app.config
        app.config = {
            "group_monitors": [
                {"enabled": True, "chat_id": -10001, "listen_source": "bot", "keywords": ["vps"]},
                {"enabled": True, "chat_id": -10001, "listen_source": "user_session", "keywords": ["api"]},
            ]
        }
        try:
            monitor_bot = app.group_monitor_for_chat_and_source(-10001, "bot")
            monitor_session = app.group_monitor_for_chat_and_source(-10001, "user_session")
            self.assertIsNotNone(monitor_bot)
            self.assertIsNotNone(monitor_session)
            self.assertEqual("bot", monitor_bot["listen_source"])
            self.assertEqual("user_session", monitor_session["listen_source"])
        finally:
            app.config = old_config

    def test_handle_group_keyword_message_sends_summary_to_admin(self) -> None:
        old_config = app.config
        old_bot = app.bot
        old_admin_chat_ids = app.admin_chat_ids
        fake_bot = FakeBot()
        app.bot = fake_bot
        app.admin_chat_ids = [9001]
        app.config = {
            "group_monitors": [
                {
                    "enabled": True,
                    "name": "测试群",
                    "chat_id": -100100100,
                    "keywords": ["vps", "优惠"],
                    "exclude_keywords": ["求带"],
                    "notify_telegram": True,
                }
            ]
        }
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100100100, username="groupdemo", title="测试群"),
            from_user=SimpleNamespace(id=123, first_name="Alice", last_name="", username="alice"),
            text="今晚 vps 有优惠",
            caption=None,
            reply_to_message=None,
            message_id=777,
            content_type="text",
        )
        try:
            ok = asyncio.run(app.handle_group_keyword_message(msg))
            self.assertTrue(ok)
            self.assertEqual([9001], fake_bot.sent_chat_ids)
            self.assertIn("[群关键词命中]", fake_bot.sent_texts[0])
            self.assertIn("命中：vps, 优惠", fake_bot.sent_texts[0])
        finally:
            app.config = old_config
            app.bot = old_bot
            app.admin_chat_ids = old_admin_chat_ids

    def test_handle_group_keyword_message_respects_exclude_keywords(self) -> None:
        old_config = app.config
        old_bot = app.bot
        old_admin_chat_ids = app.admin_chat_ids
        fake_bot = FakeBot()
        app.bot = fake_bot
        app.admin_chat_ids = [9001]
        app.config = {
            "group_monitors": [
                {
                    "enabled": True,
                    "chat_id": -100100100,
                    "keywords": ["vps"],
                    "exclude_keywords": ["求带"],
                    "notify_telegram": True,
                }
            ]
        }
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100100100, username="groupdemo", title="测试群"),
            from_user=SimpleNamespace(id=123, first_name="Alice", last_name="", username="alice"),
            text="vps 求带",
            caption=None,
            reply_to_message=None,
            message_id=777,
            content_type="text",
        )
        try:
            ok = asyncio.run(app.handle_group_keyword_message(msg))
            self.assertFalse(ok)
            self.assertEqual([], fake_bot.sent_chat_ids)
        finally:
            app.config = old_config
            app.bot = old_bot
            app.admin_chat_ids = old_admin_chat_ids

    def test_group_ai_summary_fallback_to_template_when_ai_fails(self) -> None:
        old_config = app.config
        old_bot = app.bot
        old_admin_chat_ids = app.admin_chat_ids
        old_ai = app.summarize_group_message_ai
        fake_bot = FakeBot()
        app.bot = fake_bot
        app.admin_chat_ids = [9001]
        app.config = {
            "group_monitors": [
                {
                    "enabled": True,
                    "name": "测试群",
                    "chat_id": -100100100,
                    "keywords": ["vps"],
                    "exclude_keywords": [],
                    "notify_telegram": True,
                    "summary_mode": "ai",
                    "ai_base_url": "https://api.example.com/v1",
                    "ai_api_key": "sk-test",
                    "ai_model": "gpt-4o-mini",
                    "ai_interface": "responses",
                }
            ]
        }

        async def fail_ai(message, monitor, hits):
            raise RuntimeError("ai failed")

        app.summarize_group_message_ai = fail_ai
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100100100, username="groupdemo", title="测试群"),
            from_user=SimpleNamespace(id=123, first_name="Alice", last_name="", username="alice"),
            text="今晚 vps 有货",
            caption=None,
            reply_to_message=None,
            message_id=888,
            content_type="text",
        )
        try:
            ok = asyncio.run(app.handle_group_keyword_message(msg))
            self.assertTrue(ok)
            self.assertEqual([9001], fake_bot.sent_chat_ids)
            self.assertIn("[群AI总结失败，已使用模板]", fake_bot.sent_texts[0])
            self.assertIn("[群关键词命中]", fake_bot.sent_texts[0])
        finally:
            app.config = old_config
            app.bot = old_bot
            app.admin_chat_ids = old_admin_chat_ids
            app.summarize_group_message_ai = old_ai

    def test_record_and_list_discovered_group_chats(self) -> None:
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100123, type="supergroup", title="测试群A", username="group_a"),
            text="hello",
            caption=None,
            reply_to_message=None,
            message_id=1,
            from_user=SimpleNamespace(id=11, first_name="u", last_name="", username="u1"),
            content_type="text",
        )
        app.record_discovered_group_chat(msg)
        rows = app.list_discovered_group_chats()
        self.assertTrue(rows)
        self.assertEqual(-100123, rows[0]["chat_id"])
        self.assertEqual("测试群A", rows[0]["title"])

    def test_group_monitors_page_keeps_discovered_chat_actions_markup(self) -> None:
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("已发现群聊", source)
        self.assertIn("用此群创建监听", source)
        self.assertIn("/group-monitors/new?chat_id=", source)


if __name__ == "__main__":
    unittest.main()
