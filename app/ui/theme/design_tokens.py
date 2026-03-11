from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColorRoles:
    primary: str = "#3559C7"
    on_primary: str = "#FFFFFF"
    primary_container: str = "#E4EBFF"
    on_primary_container: str = "#1B2D68"

    background: str = "#F3F5FA"
    surface: str = "#FFFFFF"
    surface_variant: str = "#F7F8FC"
    surface_container: str = "#EEF1F6"
    surface_container_high: str = "#E7EBF3"
    sidebar_surface: str = "#F7F8FB"

    page_surface: str = "#FFFFFF"
    page_edge: str = "#D7DDEA"

    outline: str = "#D7DDEA"
    outline_variant: str = "#E7EBF3"

    text_primary: str = "#172033"
    text_secondary: str = "#5F6B82"
    text_tertiary: str = "#7B869B"

    hover: str = "#EEF3FF"
    pressed: str = "#E1E8FF"
    selected: str = "#DCE6FF"
    disabled: str = "#B7C0D2"

    success: str = "#1E6F4E"
    warning: str = "#A25D17"
    error: str = "#BA1A1A"
    on_error: str = "#FFFFFF"


@dataclass(frozen=True, slots=True)
class ShapeTokens:
    sm: int = 8
    md: int = 14
    lg: int = 20
    xl: int = 28


@dataclass(frozen=True, slots=True)
class ElevationTokens:
    top_bar_blur: int = 24
    card_blur: int = 28
    dialog_blur: int = 34
    floating_blur: int = 40
    y_offset_small: int = 2
    y_offset_medium: int = 5
    y_offset_large: int = 8
    alpha_light: int = 28
    alpha_medium: int = 38
    alpha_heavy: int = 52


@dataclass(frozen=True, slots=True)
class SpacingTokens:
    s4: int = 4
    s8: int = 8
    s12: int = 12
    s16: int = 16
    s20: int = 20
    s24: int = 24
    s32: int = 32


@dataclass(frozen=True, slots=True)
class TypographyTokens:
    display: int = 24
    title: int = 19
    subtitle: int = 16
    body: int = 14
    supporting: int = 12
    label: int = 11
    doc_title: int = 28
    doc_body: int = 16
    doc_small: int = 13


@dataclass(frozen=True, slots=True)
class StateTokens:
    hover_opacity: float = 0.10
    pressed_opacity: float = 0.16
    selected_opacity: float = 0.20
    focused_width: int = 2


@dataclass(frozen=True, slots=True)
class DesignTokens:
    colors: ColorRoles = ColorRoles()
    shape: ShapeTokens = ShapeTokens()
    elevation: ElevationTokens = ElevationTokens()
    spacing: SpacingTokens = SpacingTokens()
    typography: TypographyTokens = TypographyTokens()
    states: StateTokens = StateTokens()


def material3_light_tokens() -> DesignTokens:
    return DesignTokens()
