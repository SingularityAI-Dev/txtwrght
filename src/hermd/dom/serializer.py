"""FlatDomTree JSON -> indexed text for the LLM.

Port of page-agent's flatTreeToString (packages/page-controller/src/dom/index.ts,
MIT), which corresponds to browser-use's clickable_elements_to_string. The output
format is the prompt contract: one line per element, tab depth nesting, [n] index
prefix (*[n] when new since the previous snapshot), whitelisted attributes with
values capped at 20 chars, plain text lines for visible non-interactive text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_INCLUDE_ATTRIBUTES = [
    "title",
    "type",
    "checked",
    "name",
    "role",
    "value",
    "placeholder",
    "data-date-format",
    "alt",
    "aria-label",
    "aria-expanded",
    "data-state",
    "aria-checked",
    # @edit (page-agent) added for better form handling
    "id",
    "for",
    # for jump check
    "target",
    # absolute position dropdown menu
    "aria-haspopup",
    "aria-controls",
    "aria-owns",
    # content editable
    "contenteditable",
]

SEMANTIC_TAGS = {"nav", "menu", "header", "footer", "aside", "dialog"}

_glob_regex_cache: dict[str, re.Pattern[str]] = {}


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    regex = _glob_regex_cache.get(pattern)
    if regex is None:
        escaped = re.sub(r"[.+^${}()|[\]\\]", lambda m: "\\" + m.group(0), pattern)
        regex = re.compile("^" + escaped.replace("*", ".*") + "$")
        _glob_regex_cache[pattern] = regex
    return regex


def _match_attributes(attrs: dict[str, str], patterns: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pattern in patterns:
        if "*" in pattern:
            regex = _glob_to_regex(pattern)
            for key, value in attrs.items():
                if regex.match(key) and value and value.strip():
                    result[key] = value.strip()
        else:
            value = attrs.get(pattern)
            if value and value.strip():
                result[pattern] = value.strip()
    return result


def _cap_text_length(text: str, max_length: int) -> str:
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


@dataclass
class _TreeNode:
    type: str  # "text" | "element"
    parent: "_TreeNode | None" = None
    children: list["_TreeNode"] = field(default_factory=list)
    is_visible: bool = False
    # text node
    text: str | None = None
    # element node
    tag_name: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    is_interactive: bool = False
    is_top_element: bool = False
    is_new: bool = False
    highlight_index: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _build_tree_node(flat_map: dict[str, Any], node_id: str) -> _TreeNode | None:
    node = flat_map.get(node_id)
    if node is None:
        return None

    if node.get("type") == "TEXT_NODE":
        return _TreeNode(
            type="text",
            text=node.get("text"),
            is_visible=bool(node.get("isVisible")),
        )

    children: list[_TreeNode] = []
    for child_id in node.get("children") or []:
        child = _build_tree_node(flat_map, child_id)
        if child is not None:
            children.append(child)

    tree_node = _TreeNode(
        type="element",
        tag_name=node.get("tagName"),
        attributes={k: v for k, v in (node.get("attributes") or {}).items() if v is not None},
        is_visible=bool(node.get("isVisible")),
        is_interactive=bool(node.get("isInteractive")),
        is_top_element=bool(node.get("isTopElement")),
        is_new=bool(node.get("isNew")),
        highlight_index=node.get("highlightIndex"),
        extra=node.get("extra") or {},
    )
    tree_node.children = children
    for child in children:
        child.parent = tree_node
    return tree_node


def get_all_text_till_next_clickable_element(node: _TreeNode, max_depth: int = -1) -> str:
    text_parts: list[str] = []

    def collect(current: _TreeNode, depth: int) -> None:
        if max_depth != -1 and depth > max_depth:
            return
        if current.type == "element" and current is not node and current.highlight_index is not None:
            return
        if current.type == "text" and current.text:
            text_parts.append(current.text)
        elif current.type == "element":
            for child in current.children:
                collect(child, depth + 1)

    collect(node, 0)
    return "\n".join(text_parts).strip()


def _has_parent_with_highlight_index(node: _TreeNode) -> bool:
    current = node.parent
    while current is not None:
        if current.type == "element" and current.highlight_index is not None:
            return True
        current = current.parent
    return False


def flat_tree_to_string(
    flat_tree: dict[str, Any],
    include_attributes: list[str] | None = None,
    keep_semantic_tags: bool = False,
) -> str:
    include_attrs = list(include_attributes or []) + DEFAULT_INCLUDE_ATTRIBUTES

    root = _build_tree_node(flat_tree["map"], flat_tree["rootId"])
    if root is None:
        return ""

    result: list[str] = []

    def process(node: _TreeNode, depth: int) -> None:
        next_depth = depth
        depth_str = "\t" * depth

        if node.type == "element":
            is_semantic = keep_semantic_tags and node.tag_name in SEMANTIC_TAGS

            if node.highlight_index is not None:
                next_depth += 1

                text = get_all_text_till_next_clickable_element(node)
                attributes_html_str = ""

                if include_attrs and node.attributes:
                    attrs = _match_attributes(node.attributes, include_attrs)

                    # Remove duplicate values (for attributes longer than 5 chars)
                    keys = list(attrs.keys())
                    if len(keys) > 1:
                        keys_to_remove: set[str] = set()
                        seen_values: dict[str, str] = {}
                        for key in keys:
                            value = attrs[key]
                            if len(value) > 5:
                                if value in seen_values:
                                    keys_to_remove.add(key)
                                else:
                                    seen_values[value] = key
                        for key in keys_to_remove:
                            del attrs[key]

                    # Remove role if it matches tagName
                    if attrs.get("role") == node.tag_name:
                        del attrs["role"]

                    # Remove attributes that duplicate text content
                    for attr in ("aria-label", "placeholder", "title"):
                        if attrs.get(attr) and attrs[attr].lower().strip() == text.lower().strip():
                            del attrs[attr]

                    if attrs:
                        attributes_html_str = " ".join(
                            f"{key}={_cap_text_length(value, 20)}" for key, value in attrs.items()
                        )

                indicator = f"*[{node.highlight_index}]" if node.is_new else f"[{node.highlight_index}]"
                line = f"{depth_str}{indicator}<{node.tag_name or ''}"

                if attributes_html_str:
                    line += f" {attributes_html_str}"

                if node.extra.get("scrollable"):
                    scroll_data = node.extra.get("scrollData") or {}
                    scroll_data_text = ""
                    if scroll_data.get("left"):
                        scroll_data_text += f"left={scroll_data['left']}, "
                    if scroll_data.get("top"):
                        scroll_data_text += f"top={scroll_data['top']}, "
                    if scroll_data.get("right"):
                        scroll_data_text += f"right={scroll_data['right']}, "
                    if scroll_data.get("bottom"):
                        scroll_data_text += f"bottom={scroll_data['bottom']}"
                    line += f' data-scrollable="{scroll_data_text}"'

                if text:
                    trimmed = text.strip()
                    if not attributes_html_str:
                        line += " "
                    line += f">{trimmed}"
                elif not attributes_html_str:
                    line += " "

                line += " />"
                result.append(line)

            # Semantic tags are kept for context even when not interactive
            emit_semantic = is_semantic and node.highlight_index is None
            mark = len(result) if emit_semantic else -1

            if emit_semantic:
                result.append(f"{depth_str}<{node.tag_name}>")
                next_depth += 1

            for child in node.children:
                process(child, next_depth)

            if emit_semantic:
                if len(result) == mark + 1:
                    result.pop()  # empty tag
                else:
                    result.append(f"{depth_str}</{node.tag_name}>")

        elif node.type == "text":
            if _has_parent_with_highlight_index(node):
                return
            if (
                node.parent is not None
                and node.parent.type == "element"
                and node.parent.is_visible
                and node.parent.is_top_element
            ):
                result.append(f"{depth_str}{node.text or ''}")

    process(root, 0)
    return "\n".join(result)
