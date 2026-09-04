"""Golden tests pinning the serialization format, the prompt contract.

If any of these break, what the LLM sees has changed; that is a breaking change
and must be deliberate.
"""

from txtwrght.dom.serializer import flat_tree_to_string


def tree(root_children, extra_nodes=None):
    nodes = {
        "0": {
            "tagName": "body",
            "attributes": {},
            "children": root_children,
            "isVisible": True,
            "isTopElement": True,
        }
    }
    nodes.update(extra_nodes or {})
    return {"rootId": "0", "map": nodes}


def test_interactive_element_with_text_no_attrs():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "button",
                "attributes": {"class": "fancy"},  # class is not whitelisted
                "children": ["2"],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 0,
            },
            "2": {"type": "TEXT_NODE", "text": "OK", "isVisible": True},
        },
    )
    assert flat_tree_to_string(t) == "[0]<button >OK />"


def test_new_element_gets_star_prefix():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "a",
                "attributes": {"href": "#x"},
                "children": [],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "isNew": True,
                "highlightIndex": 3,
            },
        },
    )
    assert flat_tree_to_string(t) == "*[3]<a  />"


def test_whitelisted_attributes_and_20_char_cap():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "input",
                "attributes": {
                    "type": "text",
                    "placeholder": "This placeholder is far too long to keep",
                    "class": "ignored",
                },
                "children": [],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 0,
            },
        },
    )
    out = flat_tree_to_string(t)
    assert out == "[0]<input type=text placeholder=This placeholder is ... />"


def test_role_matching_tagname_is_dropped():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "button",
                "attributes": {"role": "button", "name": "go"},
                "children": [],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 0,
            },
        },
    )
    assert flat_tree_to_string(t) == "[0]<button name=go />"


def test_attr_duplicating_text_is_dropped():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "a",
                "attributes": {"aria-label": "Read the docs"},
                "children": ["2"],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 1,
            },
            "2": {"type": "TEXT_NODE", "text": "Read the docs", "isVisible": True},
        },
    )
    assert flat_tree_to_string(t) == "[1]<a >Read the docs />"


def test_nesting_depth_uses_tabs():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "div",
                "attributes": {},
                "children": ["2"],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 0,
            },
            "2": {
                "tagName": "button",
                "attributes": {},
                "children": ["3"],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 1,
            },
            "3": {"type": "TEXT_NODE", "text": "Inner", "isVisible": True},
        },
    )
    # Outer element's text swallows text up to the next clickable, so the outer
    # line has no text; the inner button is indented one tab deeper.
    assert flat_tree_to_string(t) == "[0]<div  />\n\t[1]<button >Inner />"


def test_plain_text_under_visible_top_parent_is_emitted():
    t = tree(
        ["1", "2"],
        {
            "1": {"type": "TEXT_NODE", "text": "Welcome here", "isVisible": True},
            "2": {
                "tagName": "button",
                "attributes": {},
                "children": [],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 0,
            },
        },
    )
    assert flat_tree_to_string(t) == "Welcome here\n[0]<button  />"


def test_scrollable_container_annotation():
    t = tree(
        ["1"],
        {
            "1": {
                "tagName": "div",
                "attributes": {},
                "children": [],
                "isVisible": True,
                "isTopElement": True,
                "isInteractive": True,
                "highlightIndex": 0,
                "extra": {"scrollable": True, "scrollData": {"top": 0, "bottom": 1300}},
            },
        },
    )
    # Upstream pads with a space whenever the whitelisted-attribute string is
    # empty, even after a data-scrollable annotation; hence the double space.
    assert flat_tree_to_string(t) == '[0]<div data-scrollable="bottom=1300"  />'
