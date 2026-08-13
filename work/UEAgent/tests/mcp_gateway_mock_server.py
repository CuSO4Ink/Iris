#!/usr/bin/env python3
"""Loopback-only MCP transport fixture for mcp_gateway.ps1 regression tests."""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], mode: str, payload_bytes: int) -> None:
        super().__init__(address, Handler)
        self.mode = mode
        self.payload_bytes = payload_bytes
        self.initialize_count = 0
        self.current_session = ""
        self.successful_call_count = 0


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def fixture(self) -> Server:
        return self.server  # type: ignore[return-value]

    def log_message(self, _format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        return json.loads(body.decode("utf-8"))

    def _reply(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if body:
            self.wfile.write(body)
        self.close_connection = True

    def _stream_forever(self, content_type: str, chunk: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                self.wfile.write(chunk)
                self.wfile.flush()
                time.sleep(0.02)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        request = self._read_json()
        method = str(request.get("method", ""))
        session_id = self.headers.get("Mcp-Session-Id", "")
        print(f"REQUEST {method} SESSION {session_id}", flush=True)

        if method == "initialize":
            if self.fixture.mode == "initialize_hang":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "fixture-session")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    chunk = b" " * 65536
                    while True:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                        time.sleep(0.02)
                except (BrokenPipeError, ConnectionResetError):
                    return

            self.fixture.initialize_count += 1
            response_session = (
                f"fixture-session-{self.fixture.initialize_count}"
                if self.fixture.mode in ("session_lifecycle", "session_init_stale")
                else "fixture-session"
            )
            self.fixture.current_session = response_session
            result = {
                "jsonrpc": "2.0",
                "id": request.get("id", 1),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ueagent-fixture", "version": "1"},
                },
            }
            body = json.dumps(result, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Mcp-Session-Id", response_session)
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
            if self.fixture.mode == "session_init_stale" and self.fixture.initialize_count == 1:
                self.fixture.current_session = "expired"
            return

        if method == "notifications/initialized":
            self._reply(202, b"", "application/json")
            return

        expected_session = self.fixture.current_session if self.fixture.mode in ("session_lifecycle", "session_init_stale") else "fixture-session"
        if self.fixture.mode in ("stale_session", "session_lifecycle", "session_init_stale") and session_id != expected_session:
            error = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32600,
                    "message": f"Unknown session id '{session_id}' for '{method}'; client should reinitialize",
                },
            }
            self._reply(404, json.dumps(error).encode("utf-8"), "application/json")
            return

        if method == "tools/list":
            result = {
                "jsonrpc": "2.0",
                "id": request.get("id", 2),
                "result": {"tools": [{"name": "fixture_tool", "inputSchema": {"type": "object"}}]},
            }
            self._reply(200, json.dumps(result).encode("utf-8"), "application/json")
            return

        if method == "tools/call":
            if self.fixture.mode == "call_hang":
                self._stream_forever("text/event-stream", b": keepalive\n\n")
                return

            payload = "x" * self.fixture.payload_bytes
            structured_content: dict[str, object] = {
                "payload": payload,
                "payloadBytes": self.fixture.payload_bytes,
            }
            if self.fixture.mode == "echo":
                structured_content["request"] = request
            result = {
                "jsonrpc": "2.0",
                "id": request.get("id", 2),
                "result": {
                    "structuredContent": structured_content
                },
            }
            if self.fixture.mode == "json_success":
                body = json.dumps(result, separators=(",", ":")).encode("utf-8")
                self._reply(200, body, "application/json")
                return
            event = "data: " + json.dumps(result, separators=(",", ":")) + "\n\n"
            self._reply(200, event.encode("utf-8"), "text/event-stream")
            if self.fixture.mode == "session_lifecycle":
                self.fixture.successful_call_count += 1
                if self.fixture.successful_call_count == 1:
                    self.fixture.current_session = "expired"
            return

        error = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32601, "message": f"unsupported method: {method}"},
        }
        self._reply(200, json.dumps(error).encode("utf-8"), "application/json")

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._reply(202, b"", "application/json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--mode",
        choices=("success", "json_success", "echo", "stale_session", "session_lifecycle", "session_init_stale", "call_hang", "initialize_hang"),
        required=True,
    )
    parser.add_argument("--payload-bytes", type=int, default=0)
    args = parser.parse_args()

    server = Server(("127.0.0.1", args.port), args.mode, args.payload_bytes)
    print(f"READY {args.port} {args.mode}", flush=True)
    server.serve_forever(poll_interval=0.05)


if __name__ == "__main__":
    main()
