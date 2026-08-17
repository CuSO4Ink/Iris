import hashlib
import hmac
import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from qq_tech_digest import (
    authorize_websocket,
    compact_message,
    ingest_event,
    init_db,
    napcat_config,
    process_ready_windows,
    status,
    verify_signature,
)


class QQTechDigestTest(unittest.TestCase):
    def test_privacy_dedupe_signature_and_digest(self) -> None:
        event = {
            "time": int(time.time()),
            "self_id": 100001,
            "post_type": "message",
            "message_type": "group",
            "sub_type": "normal",
            "message_id": 900001,
            "group_id": 123456789,
            "user_id": 200002,
            "message": [
                {"type": "reply", "data": {"id": "899998"}},
                {"type": "text", "data": {"text": "这个崩溃是资源在异步加载完成前被释放了"}},
                {"type": "image", "data": {"file_id": "secret-file", "url": "https://example.test/crash.png"}},
            ],
            "raw_message": "DO-NOT-STORE",
            "sender": {"nickname": "群友A", "card": "UE开发", "role": "member"},
        }

        compact = compact_message(event)
        self.assertEqual(
            set(compact), {"group_id", "message_id", "ts", "text", "media"}
        )
        self.assertNotIn("secret-file", json.dumps(compact, ensure_ascii=False))

        token = "t" * 32
        body = json.dumps(event, ensure_ascii=False).encode()
        signature = "sha1=" + hmac.new(token.encode(), body, hashlib.sha1).hexdigest()
        self.assertTrue(verify_signature(token, body, signature))
        self.assertFalse(verify_signature(token, body + b" ", signature))

        request = SimpleNamespace(path="/onebot", headers={"Authorization": f"Bearer {token}"})
        self.assertIsNone(authorize_websocket(request, "/onebot", token))
        request.headers["Authorization"] = "Bearer wrong"
        self.assertEqual(authorize_websocket(request, "/onebot", token).status_code, 401)
        network = napcat_config(
            {"listen_host": "127.0.0.1", "listen_port": 8765, "event_path": "/onebot", "token": token}
        )["network"]
        self.assertEqual(network["httpClients"], [])
        self.assertEqual(network["websocketClients"][0]["url"], "ws://127.0.0.1:8766/onebot")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db_path = root / "data.sqlite3"
            digest_dir = root / "digests"
            init_db(db_path)
            self.assertTrue(ingest_event(db_path, event))
            self.assertFalse(ingest_event(db_path, event))

            chatter = dict(event)
            chatter["message_id"] = 900002
            chatter["message"] = [{"type": "text", "data": {"text": "大家吃饭了吗"}}]
            self.assertTrue(ingest_event(db_path, chatter))

            ignored = dict(event)
            ignored["message_id"] = 900003
            ignored["group_id"] = 987654321
            self.assertFalse(ingest_event(db_path, ignored, {"123456789"}))
            health = status(db_path)
            self.assertEqual(
                {key: health[key] for key in ("received", "accepted", "rejected")},
                {"received": 4, "accepted": 2, "rejected": 2},
            )
            self.assertIsInstance(health["last_event_at"], int)
            self.assertIsInstance(health["last_accepted_at"], int)

            self.assertEqual(process_ready_windows(db_path, digest_dir, 900, 300, 2, force=True), 1)

            output = next(digest_dir.glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("异步加载", output)
            self.assertIn("https://example.test/crash.png", output)
            for forbidden in ("群友A", "UE开发", "200002", "100001", "DO-NOT-STORE", "大家吃饭了吗", "secret-file"):
                self.assertNotIn(forbidden, output)

            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
