#!/usr/bin/env python3
"""Probe a project UnrealMCP stdio server and one cheap live read."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _content_value(call_result: Any) -> Any:
    dumped = _jsonable(call_result)
    if not isinstance(dumped, dict):
        return dumped
    content = dumped.get("content")
    if not isinstance(content, list) or not content:
        return dumped
    first = content[0]
    if not isinstance(first, dict) or first.get("type") != "text":
        return dumped
    text = first.get("text")
    if not isinstance(text, str):
        return dumped
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def _probe(args: argparse.Namespace) -> dict[str, Any]:
    child_env = os.environ.copy()
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    parameters = StdioServerParameters(
        command=args.server_command,
        args=args.server_arg,
        cwd=args.server_cwd,
        env=child_env,
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            tool_names = sorted(tool.name for tool in listed.tools)
            missing = sorted(set(args.required_tool) - set(tool_names))
            unexpected = sorted(set(tool_names) - set(args.required_tool))

            live_read = False
            live_value: Any = None
            live_error: str | None = None
            if missing:
                live_error = f"Missing required tools: {', '.join(missing)}"
            elif unexpected:
                live_error = f"Unexpected tools outside the read-only allow-list: {', '.join(unexpected)}"
            elif args.live_tool:
                result = await session.call_tool(args.live_tool, args.live_arguments)
                live_value = _content_value(result)
                result_dump = _jsonable(result)
                protocol_error = isinstance(result_dump, dict) and bool(result_dump.get("isError"))
                command_error = (
                    isinstance(live_value, dict)
                    and (
                        live_value.get("status") == "error"
                        or live_value.get("success") is False
                    )
                )
                live_read = not protocol_error and not command_error
                if not live_read:
                    live_error = "The live read tool returned an error."

            return {
                "ok": not missing and not unexpected and live_read,
                "toolsList": True,
                "topLevelTools": tool_names,
                "missingTools": missing,
                "unexpectedTools": unexpected,
                "liveRead": live_read,
                "liveTool": args.live_tool,
                "liveValue": live_value,
                "liveError": live_error,
            }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-command", required=True)
    parser.add_argument("--server-arg", action="append", default=[])
    parser.add_argument("--server-cwd", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--required-tool", action="append", default=[])
    parser.add_argument("--live-tool", default="get_project_info")
    parser.add_argument("--live-arguments-json", default="{}")
    parser.add_argument("--live-argument", action="append", default=[])
    args = parser.parse_args()
    args.live_arguments = json.loads(args.live_arguments_json)
    if not isinstance(args.live_arguments, dict):
        parser.error("--live-arguments-json must decode to an object")
    for item in args.live_argument:
        if "=" not in item:
            parser.error("--live-argument must use key=value")
        key, raw_value = item.split("=", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        args.live_arguments[key] = value
    return args


def main() -> int:
    args = _parse_args()
    try:
        result = asyncio.run(asyncio.wait_for(_probe(args), timeout=args.timeout))
    except Exception as exc:  # The caller needs one compact machine-readable failure.
        result = {
            "ok": False,
            "toolsList": False,
            "topLevelTools": [],
            "missingTools": args.required_tool,
            "unexpectedTools": [],
            "liveRead": False,
            "liveTool": args.live_tool,
            "liveValue": None,
            "liveError": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
