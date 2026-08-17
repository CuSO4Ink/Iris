#!/usr/bin/env python3
"""Minimal NapCat/OneBot 11 group-message collector and technical digest."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from websockets.datastructures import Headers
from websockets.http11 import Response
from websockets.sync.server import ServerConnection, serve as websocket_serve


DEFAULT_CONFIG = {
    "listen_host": "127.0.0.1",
    "listen_port": 8765,
    "event_path": "/onebot",
    "token": "",
    "groups": [],
    "window_seconds": 900,
    "idle_seconds": 300,
    "poll_seconds": 30,
    "min_score": 2,
    "db_path": "data/qq-tech-digest.sqlite3",
    "digest_dir": "digests",
}

MAX_BODY_BYTES = 2 * 1024 * 1024
MEDIA_TYPES = {"image": "图片", "file": "文件", "record": "语音", "video": "视频"}
PROBLEM_RE = re.compile(r"崩溃|报错|异常|失败|错误|卡死|闪退|无法|error|exception|crash|bug|fatal|timeout", re.I)
CAUSE_RE = re.compile(r"根因|原因|因为|导致|修复|解决|排查|改成|改为|避免|注意|生命周期|竞争|泄漏|释放|workaround", re.I)
TECH_RE = re.compile(
    r"异步|线程|进程|内存|资源|加载|编译|构建|部署|接口|协议|缓存|数据库|网络|渲染|性能|日志|"
    r"unreal|ue[45]?|c\+\+|python|javascript|typescript|java|rust|go(?:lang)?|sql|http|websocket|api|sdk|gpu|cpu|docker|git",
    re.I,
)
ARTIFACT_RE = re.compile(
    r"https?://|```|\b(?:git|pip|npm|pnpm|yarn|python|cmake|docker|kubectl)\s+|"
    r"\b[A-Za-z]:\\|/(?:usr|etc|var|home)/|\bv?\d+\.\d+(?:\.\d+)?\b",
    re.I | re.M,
)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def init_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        config = dict(DEFAULT_CONFIG)
        config["token"] = secrets.token_hex(32)
        atomic_write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
        print(f"Config created: {path}")
    return load_config(path)


def load_config(path: Path) -> dict[str, Any]:
    try:
        user_config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Config not found: {path}; run init or serve first") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid config JSON: {error}") from None
    if not isinstance(user_config, dict):
        raise SystemExit("Config root must be a JSON object")

    config = dict(DEFAULT_CONFIG)
    config.update(user_config)
    if not isinstance(config["token"], str) or len(config["token"]) < 32:
        raise SystemExit("token must be a random secret of at least 32 characters")
    if not isinstance(config["groups"], list):
        raise SystemExit("groups must be an array of group ID strings; empty means all groups")
    if not str(config["event_path"]).startswith("/"):
        raise SystemExit("event_path must start with /")
    for name in ("listen_port", "window_seconds", "idle_seconds", "poll_seconds", "min_score"):
        if not isinstance(config[name], int) or config[name] <= 0:
            raise SystemExit(f"{name} must be a positive integer")
    config["groups"] = [str(group) for group in config["groups"]]
    config["_base_dir"] = path.resolve().parent
    return config


def configured_path(config: dict[str, Any], name: str) -> Path:
    path = Path(config[name])
    return path if path.is_absolute() else config["_base_dir"] / path


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen (
                message_key TEXT PRIMARY KEY,
                seen_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                message_key TEXT PRIMARY KEY,
                group_key TEXT NOT NULL,
                ts INTEGER NOT NULL,
                text TEXT NOT NULL,
                media_json TEXT NOT NULL,
                score INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS messages_window ON messages(group_key, ts);
            CREATE TABLE IF NOT EXISTS digests (
                source_key TEXT PRIMARY KEY,
                day TEXT NOT NULL,
                end_ts INTEGER NOT NULL,
                score INTEGER NOT NULL,
                content TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS digests_day ON digests(day, end_ts);
            CREATE TABLE IF NOT EXISTS ingress (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                received INTEGER NOT NULL,
                accepted INTEGER NOT NULL,
                rejected INTEGER NOT NULL,
                last_event_at INTEGER,
                last_accepted_at INTEGER
            );
            INSERT OR IGNORE INTO ingress(id, received, accepted, rejected)
            VALUES (1, 0, 0, 0);
            """
        )


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n").replace("\x00", "").strip()


def safe_media(segment_type: str, data: Any) -> dict[str, str]:
    item = {"type": segment_type}
    if isinstance(data, dict):
        url = data.get("url")
        if isinstance(url, str) and urlsplit(url).scheme.lower() in {"http", "https"}:
            item["url"] = url
    return item


def compact_message(event: Any, allowed_groups: set[str] | None = None) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    if event.get("post_type") != "message" or event.get("message_type") != "group":
        return None

    group_id = event.get("group_id")
    message_id = event.get("message_id")
    timestamp = event.get("time")
    if group_id is None or message_id is None or isinstance(timestamp, bool):
        return None
    group_id, message_id = str(group_id), str(message_id)
    if allowed_groups and group_id not in allowed_groups:
        return None
    try:
        timestamp = int(timestamp)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0 or not isinstance(event.get("message"), list):
        return None

    texts: list[str] = []
    media: list[dict[str, str]] = []
    for segment in event["message"]:
        if not isinstance(segment, dict):
            continue
        segment_type = segment.get("type")
        data = segment.get("data", {})
        if segment_type == "text" and isinstance(data, dict):
            text = normalize_text(data.get("text"))
            if text:
                texts.append(text)
        elif segment_type in MEDIA_TYPES:
            media.append(safe_media(segment_type, data))

    text = "\n".join(texts)
    if not text and not media:
        return None
    return {
        "group_id": group_id,
        "message_id": message_id,
        "ts": timestamp,
        "text": text,
        "media": media,
    }


def message_score(text: str, media: list[dict[str, str]]) -> int:
    score = sum(bool(pattern.search(text)) for pattern in (PROBLEM_RE, CAUSE_RE, TECH_RE, ARTIFACT_RE))
    if len(text) >= 80:
        score += 1
    if media and text:
        score += 1
    return score


def keyed_hash(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def record_ingress(connection: sqlite3.Connection, accepted: bool) -> None:
    now = int(time.time())
    connection.execute(
        """UPDATE ingress
           SET received = received + 1,
               accepted = accepted + ?,
               rejected = rejected + ?,
               last_event_at = ?,
               last_accepted_at = CASE WHEN ? THEN ? ELSE last_accepted_at END
           WHERE id = 1""",
        (int(accepted), int(not accepted), now, accepted, now),
    )


def ingest_event(db_path: Path, event: Any, allowed_groups: set[str] | None = None) -> bool:
    message = compact_message(event, allowed_groups)
    if message is None:
        with connect(db_path) as connection:
            record_ingress(connection, False)
        return False

    group_id = message.pop("group_id")
    message_id = message.pop("message_id")
    group_key = keyed_hash("group", group_id)[:24]
    message_key = keyed_hash("message", group_id, message_id)
    score = message_score(message["text"], message["media"])

    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO seen(message_key, seen_at) VALUES (?, ?)",
            (message_key, int(time.time())),
        )
        if cursor.rowcount == 0:
            record_ingress(connection, False)
            return False
        connection.execute(
            """INSERT INTO messages
               (message_key, group_key, ts, text, media_json, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                message_key,
                group_key,
                message["ts"],
                message["text"],
                json.dumps(message["media"], ensure_ascii=False, separators=(",", ":")),
                score,
            ),
        )
        record_ingress(connection, True)
    return True


def split_windows(rows: list[sqlite3.Row], gap_seconds: int) -> list[list[sqlite3.Row]]:
    windows: list[list[sqlite3.Row]] = []
    current: list[sqlite3.Row] = []
    for row in rows:
        if current and (row["group_key"] != current[-1]["group_key"] or row["ts"] - current[-1]["ts"] > gap_seconds):
            windows.append(current)
            current = []
        current.append(row)
    if current:
        windows.append(current)
    return windows


def classify(text: str) -> str:
    if PROBLEM_RE.search(text):
        return "故障排查"
    if re.search(r"性能|优化|耗时|帧率|延迟|内存", text, re.I):
        return "性能与资源"
    if re.search(r"配置|部署|安装|编译|构建|命令", text, re.I):
        return "配置与实现"
    return "技术线索"


def markdown_bullet(text: str) -> str:
    clipped = text if len(text) <= 800 else text[:797] + "..."
    return "- " + clipped.replace("\n", "\n  ")


def extract_window(rows: list[sqlite3.Row], min_score: int) -> tuple[str, int, str] | None:
    # ponytail: deterministic rules are the MVP ceiling; swap this function for a model after measuring real misses.
    selected = [row for row in rows if row["score"] > 0]
    score = min(10, sum(row["score"] for row in selected))
    if score < min_score:
        return None

    texts: list[str] = []
    media: list[dict[str, str]] = []
    seen_texts: set[str] = set()
    seen_media: set[tuple[str, str]] = set()
    for row in selected[:12]:
        text = row["text"].strip()
        if text and text not in seen_texts:
            seen_texts.add(text)
            texts.append(text)
        for item in json.loads(row["media_json"]):
            key = (item["type"], item.get("url", ""))
            if key not in seen_media:
                seen_media.add(key)
                media.append(item)

    joined = "\n".join(texts)
    title = classify(joined)
    when = datetime.fromtimestamp(rows[-1]["ts"]).astimezone().strftime("%H:%M")
    lines = [f"## {when} · {title}", ""]
    lines.extend(markdown_bullet(text) for text in texts[:8])
    for item in media[:8]:
        label = MEDIA_TYPES.get(item["type"], "附件")
        if item.get("url"):
            lines.append(f"- 附件：[{label}]({item['url']})")
        else:
            lines.append(f"- 附件：{label}（未保存文件）")
    return title, score, "\n".join(lines).rstrip()


def render_day(connection: sqlite3.Connection, digest_dir: Path, day: str) -> None:
    rows = connection.execute(
        "SELECT content FROM digests WHERE day = ? ORDER BY end_ts, source_key", (day,)
    ).fetchall()
    content = f"# QQ 技术摘录 · {day}\n\n> 自动规则筛选；不包含发送者身份。\n"
    if rows:
        content += "\n" + "\n\n".join(row["content"] for row in rows) + "\n"
    atomic_write(digest_dir / f"{day}.md", content)


def render_all_days(db_path: Path, digest_dir: Path) -> None:
    with connect(db_path) as connection:
        days = [row["day"] for row in connection.execute("SELECT DISTINCT day FROM digests")]
        for day in days:
            render_day(connection, digest_dir, day)


def process_ready_windows(
    db_path: Path,
    digest_dir: Path,
    window_seconds: int,
    idle_seconds: int,
    min_score: int,
    *,
    force: bool = False,
    now: int | None = None,
) -> int:
    now = int(time.time()) if now is None else now
    with connect(db_path) as connection:
        # ponytail: a full pending scan is enough for one QQ account; batch only if backlog size proves otherwise.
        rows = connection.execute("SELECT * FROM messages ORDER BY group_key, ts, message_key").fetchall()
        windows = split_windows(rows, window_seconds)
        affected_days: set[str] = set()
        created = 0
        for window in windows:
            if not force and window[-1]["ts"] > now - idle_seconds:
                continue
            source_key = keyed_hash("window", *(row["message_key"] for row in window))
            extracted = extract_window(window, min_score)
            if extracted:
                _, score, content = extracted
                day = datetime.fromtimestamp(window[-1]["ts"]).astimezone().date().isoformat()
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO digests(source_key, day, end_ts, score, content) VALUES (?, ?, ?, ?, ?)",
                    (source_key, day, window[-1]["ts"], score, content),
                )
                created += cursor.rowcount
                affected_days.add(day)
            connection.executemany(
                "DELETE FROM messages WHERE message_key = ?",
                ((row["message_key"],) for row in window),
            )
        connection.execute("DELETE FROM seen WHERE seen_at < ?", (now - 30 * 86400,))
        for day in affected_days:
            render_day(connection, digest_dir, day)
    return created


def verify_signature(token: str, body: bytes, signature: str | None) -> bool:
    expected = "sha1=" + hmac.new(token.encode("utf-8"), body, hashlib.sha1).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature.lower())


def status(db_path: Path) -> dict[str, int | str | None]:
    with connect(db_path) as connection:
        pending = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        digests = connection.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
        ingress = connection.execute(
            "SELECT received, accepted, rejected, last_event_at, last_accepted_at FROM ingress WHERE id = 1"
        ).fetchone()
    return {
        "status": "ok",
        "pending": pending,
        "digests": digests,
        **dict(ingress),
    }


def make_handler(config: dict[str, Any], db_path: Path) -> type[BaseHTTPRequestHandler]:
    event_path = config["event_path"]
    token = config["token"]
    allowed_groups = set(config["groups"]) or None

    class Handler(BaseHTTPRequestHandler):
        server_version = "QQTechDigest/1"

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def send_json(self, code: int, value: Any) -> None:
            body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_json(404, {"error": "not found"})
                return
            self.send_json(200, status(db_path))

        def do_POST(self) -> None:
            if self.path != event_path:
                self.send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                self.close_connection = True
                self.send_json(413, {"error": "invalid body size"})
                return
            body = self.rfile.read(length)
            if not verify_signature(token, body, self.headers.get("X-Signature")):
                self.send_json(401, {"error": "invalid signature"})
                return
            try:
                event = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(400, {"error": "invalid json"})
                return
            ingest_event(db_path, event, allowed_groups)
            self.send_json(200, {})

    return Handler


def authorize_websocket(request: Any, event_path: str, token: str) -> Response | None:
    if request.path != event_path:
        return Response(404, "Not Found", Headers({"Content-Length": "0"}))
    expected = f"Bearer {token}"
    if not hmac.compare_digest(request.headers.get("Authorization", ""), expected):
        return Response(401, "Unauthorized", Headers({"Content-Length": "0"}))
    return None


def make_websocket_handler(
    db_path: Path, allowed_groups: set[str] | None
) -> Any:
    def handler(connection: ServerConnection) -> None:
        for body in connection:
            try:
                event = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                connection.close(1007, "invalid json")
                return
            ingest_event(db_path, event, allowed_groups)

    return handler


def napcat_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "network": {
            "httpServers": [],
            "httpClients": [],
            "websocketServers": [],
            "websocketClients": [
                {
                    "name": "qq-tech-digest",
                    "enable": True,
                    "url": f"ws://{config['listen_host']}:{config['listen_port'] + 1}{config['event_path']}",
                    "messagePostFormat": "array",
                    "reportSelfMessage": False,
                    "token": config["token"],
                    "debug": False,
                    "heartInterval": 30_000,
                    "reconnectInterval": 5_000,
                    "verifyCertificate": True,
                }
            ],
        },
        "musicSignUrl": "",
        "enableLocalFile2Url": False,
        "parseMultMsg": False,
    }


def serve(config: dict[str, Any]) -> None:
    db_path = configured_path(config, "db_path")
    digest_dir = configured_path(config, "digest_dir")
    init_db(db_path)
    render_all_days(db_path, digest_dir)
    stop = threading.Event()

    def worker() -> None:
        while not stop.wait(config["poll_seconds"]):
            try:
                count = process_ready_windows(
                    db_path,
                    digest_dir,
                    config["window_seconds"],
                    config["idle_seconds"],
                    config["min_score"],
                )
                if count:
                    print(f"New technical digests: {count}", flush=True)
            except Exception as error:  # keep receiver alive; no event content is logged
                print(f"Digest worker failed: {error}", file=sys.stderr, flush=True)

    threading.Thread(target=worker, name="digest-worker", daemon=True).start()
    server = ThreadingHTTPServer((config["listen_host"], config["listen_port"]), make_handler(config, db_path))
    ws_port = config["listen_port"] + 1
    ws_server = websocket_serve(
        make_websocket_handler(db_path, set(config["groups"]) or None),
        config["listen_host"],
        ws_port,
        process_request=lambda _, request: authorize_websocket(request, config["event_path"], config["token"]),
        compression=None,
        max_size=MAX_BODY_BYTES,
        server_header="QQTechDigest/1",
    )
    threading.Thread(target=ws_server.serve_forever, name="onebot-websocket", daemon=True).start()

    def shutdown() -> None:
        ws_server.shutdown()
        server.shutdown()

    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=shutdown, daemon=True).start())
    print(
        f"QQTechDigest listening at http://{config['listen_host']}:{config['listen_port']}{config['event_path']} "
        f"and ws://{config['listen_host']}:{ws_port}{config['event_path']} (health: /health)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        ws_server.shutdown()
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "serve", "digest", "napcat-config"), nargs="?", default="serve")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output", type=Path, help="napcat-config 的输出文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config.resolve()
    config = init_config(config_path) if args.command in {"init", "serve"} else load_config(config_path)
    db_path = configured_path(config, "db_path")
    digest_dir = configured_path(config, "digest_dir")

    if args.command == "init":
        init_db(db_path)
    elif args.command == "serve":
        serve(config)
    elif args.command == "digest":
        init_db(db_path)
        count = process_ready_windows(
            db_path,
            digest_dir,
            config["window_seconds"],
            config["idle_seconds"],
            config["min_score"],
            force=True,
        )
        print(f"New technical digests: {count}")
    elif args.command == "napcat-config":
        if not args.output:
            raise SystemExit("napcat-config requires --output")
        atomic_write(args.output.resolve(), json.dumps(napcat_config(config), ensure_ascii=False, indent=2) + "\n")
        print(f"NapCat OneBot config written: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
