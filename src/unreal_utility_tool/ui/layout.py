from __future__ import annotations

from dataclasses import dataclass

from ..theme import CARD_TITLE_FONT, TITLE_FONT


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    mode: str
    outer_pad_x: int
    header_pady: tuple[int, int]
    title_font: tuple[str, int, str]
    header_button_padx: int
    header_button_pady: int
    search_ipady: int
    controls_bottom: int
    footer_pady: int
    card_padx: int
    card_pady: int
    card_gap: int
    collapsed_card_height: int
    card_title_font: tuple[str, int, str]
    card_title_reserved_width: int
    copy_button_padx: int
    copy_button_pady: int
    icon_button_pady: int
    param_gap: int
    param_label_wrap_extra: int
    param_entry_minsize: int
    param_two_column: bool


COMPACT_LAYOUT = LayoutSpec(
    mode="compact",
    outer_pad_x=8,
    header_pady=(5, 4),
    title_font=("Segoe UI", 11, "bold"),
    header_button_padx=7,
    header_button_pady=3,
    search_ipady=1,
    controls_bottom=5,
    footer_pady=4,
    card_padx=7,
    card_pady=4,
    card_gap=4,
    collapsed_card_height=36,
    card_title_font=("Segoe UI", 8, "bold"),
    card_title_reserved_width=118,
    copy_button_padx=7,
    copy_button_pady=2,
    icon_button_pady=1,
    param_gap=4,
    param_label_wrap_extra=40,
    param_entry_minsize=120,
    param_two_column=False,
)

NORMAL_LAYOUT = LayoutSpec(
    mode="normal",
    outer_pad_x=10,
    header_pady=(6, 5),
    title_font=("Segoe UI", 12, "bold"),
    header_button_padx=9,
    header_button_pady=4,
    search_ipady=2,
    controls_bottom=6,
    footer_pady=5,
    card_padx=8,
    card_pady=5,
    card_gap=5,
    collapsed_card_height=40,
    card_title_font=("Segoe UI", 9, "bold"),
    card_title_reserved_width=134,
    copy_button_padx=10,
    copy_button_pady=3,
    icon_button_pady=2,
    param_gap=5,
    param_label_wrap_extra=58,
    param_entry_minsize=150,
    param_two_column=True,
)

WIDE_LAYOUT = LayoutSpec(
    mode="wide",
    outer_pad_x=14,
    header_pady=(8, 6),
    title_font=("Segoe UI", 14, "bold"),
    header_button_padx=11,
    header_button_pady=5,
    search_ipady=3,
    controls_bottom=7,
    footer_pady=6,
    card_padx=10,
    card_pady=6,
    card_gap=6,
    collapsed_card_height=44,
    card_title_font=CARD_TITLE_FONT,
    card_title_reserved_width=148,
    copy_button_padx=13,
    copy_button_pady=4,
    icon_button_pady=3,
    param_gap=5,
    param_label_wrap_extra=78,
    param_entry_minsize=180,
    param_two_column=True,
)


def _layout_spec_for_width(width: int) -> LayoutSpec:
    if width < 440:
        return COMPACT_LAYOUT
    if width < 900:
        return NORMAL_LAYOUT
    return WIDE_LAYOUT
