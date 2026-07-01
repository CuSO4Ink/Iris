#!/usr/bin/env python3
"""Simplify Unreal Engine Blueprint clipboard text into an AI-friendly graph.

Usage examples:
  python bp_clipboard_to_ai.py blueprint_clipboard.txt --json-out simplified.json --summary-out summary.txt
  python bp_clipboard_to_ai.py --clipboard --json-out simplified.json --summary-out summary.txt
  type blueprint_clipboard.txt | python bp_clipboard_to_ai.py - --print-summary

The script is intentionally lossy: it keeps node semantics, pin defaults, and
link relationships, while dropping most editor-only serialization noise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


HEADER_RE = re.compile(r'^Begin Object Class=(?P<class>.+?) Name="(?P<name>.+?)"')
PROP_RE = re.compile(r'^(?P<key>[A-Za-z0-9_\.]+)=(?P<value>.*)$')
LINK_RE = re.compile(r'^(?P<node>[A-Za-z0-9_]+)\s+(?P<pin>[A-Za-z0-9_\-]+)$')
OBJECT_NAME_RE = re.compile(r'([A-Za-z0-9_]+)[\'\"]?$')


@dataclass
class PinRecord:
    pin_id: str
    name: str
    direction: str
    pin_type: str
    default: str | None
    links: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_exec(self) -> bool:
        return self.pin_type == "exec"


@dataclass
class NodeRecord:
    source_name: str
    short_id: str
    class_path: str
    class_name: str
    target: dict[str, Any]
    title: str
    pure: bool | None
    comment: str | None
    pins: list[PinRecord] = field(default_factory=list)


class ParseError(RuntimeError):
    pass


def split_top_level(text: str, delimiter: str = ',') -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    in_string = False
    quote_char = ''
    escape = False

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote_char:
                in_string = False
            continue

        if ch in ('"', "'"):
            in_string = True
            quote_char = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == delimiter and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1

    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def trim_wrapper(value: str) -> str:
    value = value.strip()
    if value.startswith('(') and value.endswith(')'):
        return value[1:-1]
    return value


def parse_tuple_fields(value: str) -> dict[str, str]:
    inner = trim_wrapper(value)
    result: dict[str, str] = {}
    for item in split_top_level(inner):
        if not item or '=' not in item:
            continue
        key, raw = item.split('=', 1)
        result[key.strip()] = raw.strip()
    return result


def extract_object_name(value: str | None) -> str | None:
    if not value:
        return None
    value = strip_quotes(value) or ''
    value = value.split('/')[-1]
    value = value.split('.')[-1]
    value = value.rstrip("'")
    match = OBJECT_NAME_RE.search(value)
    if match:
        return match.group(1)
    return value or None


def friendly_type(fields: dict[str, str]) -> str:
    category = strip_quotes(fields.get('PinType.PinCategory')) or 'wildcard'
    category_lower = category.lower()
    if category_lower == 'exec':
        return 'exec'

    subcategory = strip_quotes(fields.get('PinType.PinSubCategory'))
    obj_name = extract_object_name(fields.get('PinType.PinSubCategoryObject'))
    container = strip_quotes(fields.get('PinType.ContainerType'))
    is_ref = (fields.get('PinType.bIsReference') or '').lower() == 'true'

    if category_lower in {'struct', 'object', 'class', 'softobject', 'softclass', 'interface'}:
        base = obj_name or category
    elif category_lower == 'byte' and obj_name:
        base = obj_name
    elif category_lower == 'name':
        base = 'Name'
    elif category_lower == 'text':
        base = 'Text'
    elif category_lower == 'int64':
        base = 'int64'
    elif category_lower == 'int':
        base = 'int'
    elif category_lower == 'float':
        base = 'float'
    elif category_lower == 'real':
        base = 'real'
    elif category_lower == 'bool':
        base = 'bool'
    elif category_lower == 'string':
        base = 'string'
    else:
        base = subcategory or category

    if container and container.lower() not in {'none', ''}:
        container_lower = container.lower()
        if container_lower == 'array':
            base = f'{base}[]'
        elif container_lower == 'set':
            base = f'set<{base}>'
        elif container_lower == 'map':
            base = f'map<{base}>'
        else:
            base = f'{container}<{base}>'

    if is_ref:
        base = f'{base}&'
    return base


def parse_links(value: str | None) -> list[dict[str, str]]:
    if not value:
        return []
    inner = trim_wrapper(value)
    links: list[dict[str, str]] = []
    for item in split_top_level(inner):
        match = LINK_RE.match(item.strip())
        if not match:
            continue
        links.append({'node': match.group('node'), 'pin_id': match.group('pin')})
    return links


RELEVANT_DEFAULT_KEYS = (
    'DefaultValue',
    'DefaultTextValue',
    'DefaultObject',
    'AutogeneratedDefaultValue',
)


def pick_default(fields: dict[str, str]) -> str | None:
    for key in RELEVANT_DEFAULT_KEYS:
        value = fields.get(key)
        if value is None:
            continue
        cleaned = strip_quotes(value)
        if cleaned in (None, '', 'None', '()'):
            continue
        return cleaned
    return None


def parse_pin_line(line: str) -> PinRecord:
    prefix = 'CustomProperties Pin '
    payload = line[len(prefix):].strip()
    fields = parse_tuple_fields(payload)
    return PinRecord(
        pin_id=strip_quotes(fields.get('PinId')) or '',
        name=strip_quotes(fields.get('PinName')) or '<unnamed>',
        direction=strip_quotes(fields.get('Direction')) or '',
        pin_type=friendly_type(fields),
        default=pick_default(fields),
        links=parse_links(fields.get('LinkedTo')),
    )


def classify_target(class_name: str, props: dict[str, str]) -> tuple[dict[str, Any], str, bool | None]:
    fn_ref = parse_tuple_fields(props.get('FunctionReference', '')) if 'FunctionReference' in props else {}
    var_ref = parse_tuple_fields(props.get('VariableReference', '')) if 'VariableReference' in props else {}
    macro_ref = parse_tuple_fields(props.get('MacroGraphReference', '')) if 'MacroGraphReference' in props else {}
    pure = None
    if 'bIsPureFunc' in props:
        pure = props['bIsPureFunc'].strip().lower() == 'true'

    if class_name == 'K2Node_CallFunction':
        member_name = strip_quotes(fn_ref.get('MemberName')) or 'UnknownFunction'
        owner = extract_object_name(fn_ref.get('MemberParent'))
        target = {'type': 'function', 'name': member_name}
        if owner:
            target['owner'] = owner
        title = member_name if not owner else f'{owner}.{member_name}'
        return target, title, pure

    if class_name in {'K2Node_VariableGet', 'K2Node_VariableSet'}:
        member_name = strip_quotes(var_ref.get('MemberName')) or 'UnknownVariable'
        owner = extract_object_name(var_ref.get('MemberParent'))
        target = {
            'type': 'variable',
            'mode': 'get' if class_name.endswith('Get') else 'set',
            'name': member_name,
        }
        if owner:
            target['owner'] = owner
        title = member_name if not owner else f'{owner}.{member_name}'
        return target, title, None

    if class_name == 'K2Node_CustomEvent':
        custom_name = strip_quotes(props.get('CustomFunctionName')) or 'CustomEvent'
        return {'type': 'event', 'name': custom_name}, custom_name, None

    if class_name == 'K2Node_Event':
        event_ref = parse_tuple_fields(props.get('EventReference', '')) if 'EventReference' in props else {}
        event_name = strip_quotes(event_ref.get('MemberName')) or strip_quotes(props.get('CustomFunctionName')) or 'Event'
        owner = extract_object_name(event_ref.get('MemberParent'))
        target = {'type': 'event', 'name': event_name}
        if owner:
            target['owner'] = owner
        title = event_name if not owner else f'{owner}.{event_name}'
        return target, title, None

    if class_name == 'K2Node_MacroInstance':
        macro_name = strip_quotes(props.get('ResolvedWildcardType')) or strip_quotes(macro_ref.get('MacroGraph')) or 'Macro'
        return {'type': 'macro', 'name': extract_object_name(macro_name) or macro_name}, extract_object_name(macro_name) or macro_name, None

    if class_name == 'K2Node_IfThenElse':
        return {'type': 'flow', 'name': 'Branch'}, 'Branch', None

    if class_name == 'K2Node_Knot':
        return {'type': 'reroute', 'name': 'Reroute'}, 'Reroute', None

    return {'type': 'node', 'name': class_name}, class_name, None


def parse_nodes(text: str) -> list[NodeRecord]:
    lines = text.splitlines()
    nodes_raw: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        header = HEADER_RE.match(stripped)
        if header:
            current = {
                'class_path': header.group('class'),
                'name': header.group('name'),
                'props': {},
                'pins': [],
            }
            nodes_raw.append(current)
            continue
        if stripped == 'End Object':
            current = None
            continue
        if current is None:
            continue
        if stripped.startswith('CustomProperties Pin '):
            current['pins'].append(parse_pin_line(stripped))
            continue
        prop_match = PROP_RE.match(stripped)
        if prop_match:
            current['props'][prop_match.group('key')] = prop_match.group('value').strip()

    if not nodes_raw:
        raise ParseError('未在输入中找到 Blueprint 节点导出内容（Begin Object ... End Object）。')

    nodes: list[NodeRecord] = []
    for index, raw in enumerate(nodes_raw, start=1):
        class_path = raw['class_path']
        class_name = class_path.split('.')[-1]
        props: dict[str, str] = raw['props']
        target, title, pure = classify_target(class_name, props)
        node = NodeRecord(
            source_name=raw['name'],
            short_id=f'N{index}',
            class_path=class_path,
            class_name=class_name,
            target=target,
            title=title,
            pure=pure,
            comment=strip_quotes(props.get('NodeComment')),
            pins=raw['pins'],
        )
        nodes.append(node)
    return nodes


def should_keep_node(node: NodeRecord, include_knot: bool, include_comments: bool) -> bool:
    if not include_knot and node.class_name == 'K2Node_Knot':
        return False
    if not include_comments and node.class_name in {'EdGraphNode_Comment', 'K2Node_Comment'}:
        return False
    return True


def build_graph(nodes: list[NodeRecord], include_knot: bool, include_comments: bool) -> dict[str, Any]:
    kept_nodes = [node for node in nodes if should_keep_node(node, include_knot, include_comments)]
    source_to_node = {node.source_name: node for node in kept_nodes}
    pin_lookup: dict[tuple[str, str], PinRecord] = {}
    for node in kept_nodes:
        for pin in node.pins:
            if pin.pin_id:
                pin_lookup[(node.source_name, pin.pin_id)] = pin

    simplified_nodes: list[dict[str, Any]] = []
    exec_edges: set[tuple[str, str]] = set()

    for node in kept_nodes:
        inputs: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []
        exec_in: list[str] = []
        exec_out: list[str] = []

        for pin in node.pins:
            refs: list[str] = []
            for link in pin.links:
                other_node = source_to_node.get(link['node'])
                if other_node is None:
                    continue
                other_pin = pin_lookup.get((link['node'], link['pin_id']))
                other_pin_name = other_pin.name if other_pin else '<unknown>'
                ref = f'{other_node.short_id}.{other_pin_name}'
                refs.append(ref)
                if pin.is_exec and pin.direction == 'EGPD_Output':
                    exec_edges.add((node.short_id, other_node.short_id))

            if pin.is_exec:
                if pin.direction == 'EGPD_Input':
                    exec_in.extend(refs)
                elif pin.direction == 'EGPD_Output':
                    exec_out.extend(refs)
                continue

            pin_payload: dict[str, Any] = {
                'name': pin.name,
                'type': pin.pin_type,
            }
            if refs:
                if pin.direction == 'EGPD_Input':
                    pin_payload['source'] = refs if len(refs) > 1 else refs[0]
                else:
                    pin_payload['targets'] = refs
            elif pin.default is not None:
                pin_payload['default'] = pin.default

            if pin.direction == 'EGPD_Input':
                inputs.append(pin_payload)
            elif pin.direction == 'EGPD_Output':
                outputs.append(pin_payload)

        entry = {
            'id': node.short_id,
            'class': node.class_name,
            'title': node.title,
            'target': node.target,
            'inputs': inputs,
            'outputs': outputs,
            'exec_in': exec_in,
            'exec_out': exec_out,
        }
        if node.pure is not None:
            entry['pure'] = node.pure
        if node.comment:
            entry['comment'] = node.comment
        simplified_nodes.append(entry)

    roots = sorted(
        node['id']
        for node in simplified_nodes
        if node['exec_out'] and not node['exec_in']
    )

    graph = {
        'graph': {
            'node_count': len(simplified_nodes),
            'entry_exec_nodes': roots,
            'nodes': simplified_nodes,
            'exec_edges': [
                {'from': src, 'to': dst}
                for src, dst in sorted(exec_edges)
            ],
        }
    }
    return graph


def node_label(node: dict[str, Any]) -> str:
    target = node.get('target', {})
    if target.get('type') == 'function':
        owner = target.get('owner')
        name = target.get('name', node['title'])
        return f'Call {owner + "." if owner else ""}{name}'
    if target.get('type') == 'variable':
        mode = target.get('mode', 'get')
        owner = target.get('owner')
        name = target.get('name', node['title'])
        return f'Var {mode.upper()} {owner + "." if owner else ""}{name}'
    if target.get('type') == 'event':
        return f'Event {target.get("name", node["title"])}'
    if target.get('type') == 'macro':
        return f'Macro {target.get("name", node["title"])}'
    if target.get('type') == 'flow':
        return node['title']
    return node['title']


def describe_value(value: Any) -> str:
    if isinstance(value, list):
        return ', '.join(value)
    return str(value)


def summarize_graph(graph: dict[str, Any], max_nodes: int = 20, max_paths: int = 6) -> str:
    nodes: list[dict[str, Any]] = graph['graph']['nodes']
    node_by_id = {node['id']: node for node in nodes}
    entry_nodes = graph['graph']['entry_exec_nodes']

    lines = [
        f'Blueprint 简化摘要：共 {len(nodes)} 个节点。',
    ]
    if entry_nodes:
        entry_desc = ', '.join(f'{node_id}({node_label(node_by_id[node_id])})' for node_id in entry_nodes if node_id in node_by_id)
        lines.append(f'执行入口：{entry_desc}')
    else:
        lines.append('执行入口：未检测到显式 exec 入口，可能是纯函数图或筛掉了入口节点。')

    # Linear-ish exec path sketch.
    if entry_nodes:
        lines.append('执行路径概览：')
        for root in entry_nodes[:max_paths]:
            visited: set[str] = set()
            current = root
            path_parts: list[str] = []
            hop_count = 0
            while current in node_by_id and current not in visited and hop_count < 10:
                visited.add(current)
                node = node_by_id[current]
                path_parts.append(f'{current}[{node_label(node)}]')
                outs = []
                for ref in node.get('exec_out', []):
                    next_id = ref.split('.', 1)[0]
                    if next_id not in outs:
                        outs.append(next_id)
                if len(outs) != 1:
                    if len(outs) > 1:
                        branch_str = ', '.join(outs)
                        path_parts.append(f'-> {{{branch_str}}}')
                    break
                current = outs[0]
                hop_count += 1
                if current in node_by_id:
                    path_parts.append('->')
            lines.append('- ' + ' '.join(path_parts))

    lines.append('节点细节（截断展示）：')
    for node in nodes[:max_nodes]:
        lines.append(f'- {node["id"]}: {node_label(node)}')
        if node.get('inputs'):
            input_bits = []
            for pin in node['inputs'][:6]:
                bit = f'{pin["name"]}:{pin["type"]}'
                if 'source' in pin:
                    bit += f' <= {describe_value(pin["source"])}'
                elif 'default' in pin:
                    bit += f' = {pin["default"]}'
                input_bits.append(bit)
            lines.append('    inputs: ' + '; '.join(input_bits))
        if node.get('outputs'):
            output_bits = []
            for pin in node['outputs'][:6]:
                bit = f'{pin["name"]}:{pin["type"]}'
                if 'targets' in pin:
                    bit += f' => {describe_value(pin["targets"])}'
                output_bits.append(bit)
            if output_bits:
                lines.append('    outputs: ' + '; '.join(output_bits))
        if node.get('comment'):
            lines.append(f'    comment: {node["comment"]}')

    if len(nodes) > max_nodes:
        lines.append(f'... 其余 {len(nodes) - max_nodes} 个节点已省略。')
    return '\n'.join(lines)


def read_clipboard_text() -> str:
    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover
        raise ParseError(f'当前环境无法读取剪贴板：{exc}') from exc

    root = tk.Tk()
    root.withdraw()
    try:
        text = root.clipboard_get()
    finally:
        root.destroy()
    if not text.strip():
        raise ParseError('剪贴板里没有可用的文本内容。')
    return text


def read_path_text(path: str) -> str:
    target = Path(path)
    last_error: Exception | None = None
    for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030'):
        try:
            return target.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return target.read_text(encoding='utf-8')


def load_input_text(input_path: str | None, use_clipboard: bool) -> str:
    if use_clipboard:
        return read_clipboard_text()
    if input_path and input_path != '-':
        return read_path_text(input_path)
    if input_path == '-' or not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    raise ParseError('请提供输入文件、通过 stdin 传入，或使用 --clipboard 直接读取剪贴板。')


def write_text(path: str | None, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')


def write_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def build_bundle(text: str, include_knot: bool, include_comments: bool, max_summary_nodes: int) -> dict[str, Any]:
    nodes = parse_nodes(text)
    graph = build_graph(nodes, include_knot=include_knot, include_comments=include_comments)
    summary = summarize_graph(graph, max_nodes=max_summary_nodes)
    graph['summary'] = summary
    return graph


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='将 Unreal Blueprint 剪贴板文本压缩成 AI 友好的 JSON/摘要。')
    parser.add_argument('input', nargs='?', help='输入文件路径；传 - 表示从 stdin 读取。')
    parser.add_argument('--clipboard', action='store_true', help='直接从系统剪贴板读取 Blueprint 文本。')
    parser.add_argument('--json-out', help='输出简化 JSON 文件路径。')
    parser.add_argument('--summary-out', help='输出文字摘要文件路径。')
    parser.add_argument('--print-summary', action='store_true', help='把摘要打印到 stdout。')
    parser.add_argument('--include-knot', action='store_true', help='保留 reroute/knot 节点。')
    parser.add_argument('--include-comments', action='store_true', help='保留 comment 节点。')
    parser.add_argument('--max-summary-nodes', type=int, default=20, help='摘要里最多展开多少个节点。默认 20。')
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        text = load_input_text(args.input, args.clipboard)
        bundle = build_bundle(
            text,
            include_knot=args.include_knot,
            include_comments=args.include_comments,
            max_summary_nodes=max(1, args.max_summary_nodes),
        )
    except (OSError, ParseError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    if args.json_out:
        write_json(args.json_out, bundle)
    if args.summary_out:
        write_text(args.summary_out, bundle['summary'])

    if args.print_summary:
        print(bundle['summary'])
    elif not args.json_out and not args.summary_out:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
