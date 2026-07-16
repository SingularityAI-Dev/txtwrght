"""BrowserState: one observed page state, rendered for LLM consumption.

The render() format mirrors page-agent's PageController.getBrowserState header
and footer exactly; the content between them comes from serializer.flat_tree_to_string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BrowserState:
    url: str
    title: str
    content: str
    page_info: dict[str, Any]
    tree: dict[str, Any]
    viewport_expansion: int
    selector_count: int

    def render(self) -> str:
        pi = self.page_info
        title_line = f"Current Page: [{self.title}]({self.url})"
        page_info_line = (
            f"Page info: {pi['viewport_width']}x{pi['viewport_height']}px viewport, "
            f"{pi['page_width']}x{pi['page_height']}px total page size, "
            f"{pi['pages_above']:.1f} pages above, {pi['pages_below']:.1f} pages below, "
            f"{pi['total_pages']:.1f} total pages, "
            f"at {pi['current_page_position'] * 100:.0f}% of page"
        )

        full_page = self.viewport_expansion == -1
        elements_label = (
            "Interactive elements from top layer of the current page (full page):"
            if full_page
            else "Interactive elements from top layer of the current page inside the viewport:"
        )

        has_content_above = pi["pixels_above"] > 4
        if has_content_above and not full_page:
            scroll_hint_above = (
                f"... {pi['pixels_above']} pixels above ({pi['pages_above']:.1f} pages) "
                "- scroll to see more ..."
            )
        else:
            scroll_hint_above = "[Start of page]"

        has_content_below = pi["pixels_below"] > 4
        if has_content_below and not full_page:
            footer = (
                f"... {pi['pixels_below']} pixels below ({pi['pages_below']:.1f} pages) "
                "- scroll to see more ..."
            )
        else:
            footer = "[End of page]"

        header = f"{title_line}\n{page_info_line}\n\n{elements_label}\n\n{scroll_hint_above}"
        return f"{header}\n{self.content}\n{footer}"
