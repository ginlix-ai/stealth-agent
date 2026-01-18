"""Theme system for terminal dark/light mode support with selectable palettes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml

try:
    import darkdetect
except ModuleNotFoundError:  # pragma: no cover
    darkdetect = None


class ThemeMode(Enum):
    """Available theme modes."""

    AUTO = "auto"
    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class ColorPalette:
    """Color palette for a theme."""

    primary: str
    dim: str
    user: str
    agent: str
    thinking: str
    tool: str


# ═══════════════════════════════════════════════════════════════════════════════
# COLOR PALETTES - 8 themes with dark and light variants
# ═══════════════════════════════════════════════════════════════════════════════

PALETTES: dict[str, dict[str, ColorPalette]] = {
    # ─── Basic Colors ───
    "emerald": {
        "dark": ColorPalette(
            primary="#10b981",
            dim="#6b7280",
            user="#ffffff",
            agent="#10b981",
            thinking="#34d399",
            tool="#fbbf24",
        ),
        "light": ColorPalette(
            primary="#047857",
            dim="#4b5563",
            user="#1f2937",
            agent="#047857",
            thinking="#059669",
            tool="#b45309",
        ),
    },
    "cyan": {
        "dark": ColorPalette(
            primary="#06b6d4",
            dim="#6b7280",
            user="#ffffff",
            agent="#06b6d4",
            thinking="#22d3ee",
            tool="#f59e0b",
        ),
        "light": ColorPalette(
            primary="#0891b2",
            dim="#4b5563",
            user="#1f2937",
            agent="#0891b2",
            thinking="#0e7490",
            tool="#b45309",
        ),
    },
    "amber": {
        "dark": ColorPalette(
            primary="#f59e0b",
            dim="#6b7280",
            user="#ffffff",
            agent="#f59e0b",
            thinking="#fbbf24",
            tool="#06b6d4",
        ),
        "light": ColorPalette(
            primary="#d97706",
            dim="#4b5563",
            user="#1f2937",
            agent="#d97706",
            thinking="#b45309",
            tool="#0891b2",
        ),
    },
    "teal": {
        "dark": ColorPalette(
            primary="#14b8a6",
            dim="#6b7280",
            user="#ffffff",
            agent="#14b8a6",
            thinking="#2dd4bf",
            tool="#fb923c",
        ),
        "light": ColorPalette(
            primary="#0d9488",
            dim="#4b5563",
            user="#1f2937",
            agent="#0d9488",
            thinking="#0f766e",
            tool="#c2410c",
        ),
    },
    # ─── Popular Terminal Themes ───
    "nord": {
        "dark": ColorPalette(
            primary="#88c0d0",  # Frost
            dim="#4c566a",  # Polar Night
            user="#eceff4",  # Snow Storm
            agent="#88c0d0",
            thinking="#81a1c1",  # Frost
            tool="#ebcb8b",  # Aurora Yellow
        ),
        "light": ColorPalette(
            primary="#5e81ac",  # Nord10
            dim="#4c566a",
            user="#2e3440",  # Polar Night
            agent="#5e81ac",
            thinking="#6a8caf",
            tool="#bf9157",
        ),
    },
    "gruvbox": {
        "dark": ColorPalette(
            primary="#fabd2f",  # Yellow
            dim="#928374",  # Gray
            user="#ebdbb2",  # Light
            agent="#fabd2f",
            thinking="#fe8019",  # Orange
            tool="#8ec07c",  # Aqua
        ),
        "light": ColorPalette(
            primary="#b57614",  # Dark yellow
            dim="#7c6f64",
            user="#3c3836",
            agent="#b57614",
            thinking="#af3a03",  # Dark orange
            tool="#427b58",  # Dark aqua
        ),
    },
    "catppuccin": {
        "dark": ColorPalette(
            primary="#cba6f7",  # Mauve (Mocha)
            dim="#6c7086",  # Overlay0
            user="#cdd6f4",  # Text
            agent="#cba6f7",
            thinking="#f5c2e7",  # Pink
            tool="#f9e2af",  # Yellow
        ),
        "light": ColorPalette(
            primary="#8839ef",  # Mauve (Latte)
            dim="#6c6f85",  # Overlay0
            user="#4c4f69",  # Text
            agent="#8839ef",
            thinking="#ea76cb",  # Pink
            tool="#df8e1d",  # Yellow
        ),
    },
    "tokyo_night": {
        "dark": ColorPalette(
            primary="#7aa2f7",  # Blue
            dim="#565f89",  # Comment
            user="#c0caf5",  # Foreground
            agent="#7aa2f7",
            thinking="#bb9af7",  # Purple
            tool="#e0af68",  # Yellow
        ),
        "light": ColorPalette(
            primary="#2e7de9",  # Blue (Day)
            dim="#6172b0",
            user="#3760bf",
            agent="#2e7de9",
            thinking="#9854f1",  # Purple
            tool="#8c6c3e",
        ),
    },
}

# Available palette names for validation
AVAILABLE_PALETTES = list(PALETTES.keys())
DEFAULT_PALETTE_DARK = "nord"
DEFAULT_PALETTE_LIGHT = "tokyo_night"


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG FILE LOADING
# ═══════════════════════════════════════════════════════════════════════════════


def _find_project_root(start_path: Path | None = None) -> Path | None:
    """Find git repository root by walking up from start_path."""
    current = (start_path or Path.cwd()).resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _get_config_search_paths() -> list[Path]:
    """Get ordered list of config search paths.

    Search order:
    1. Current working directory
    2. Project root (git repo root) if different from cwd
    3. ~/.ptc-agent/
    """
    cwd = Path.cwd()
    paths = [cwd]

    project_root = _find_project_root(cwd)
    if project_root and project_root != cwd:
        paths.append(project_root)

    paths.append(Path.home() / ".ptc-agent")
    return paths


def _load_cli_config() -> dict[str, Any]:
    """Load CLI config from config.yaml.

    Searches for config.yaml in standard locations and returns
    the 'cli' section if found.

    Returns:
        CLI config dict with 'palette' and 'theme' keys, or empty dict
    """
    # Check env var override for config path
    env_config_path = os.environ.get("PTC_CONFIG_FILE")
    if env_config_path:
        config_path = Path(env_config_path)
        if config_path.exists():
            return _read_cli_section(config_path)

    # Search standard paths
    for search_path in _get_config_search_paths():
        config_path = search_path / "config.yaml"
        if config_path.exists():
            return _read_cli_section(config_path)

    return {}


def _read_cli_section(config_path: Path) -> dict[str, Any]:
    """Read the 'cli' section from a config file.

    Args:
        config_path: Path to config.yaml

    Returns:
        CLI config dict, or empty dict if not found or error
    """
    try:
        with config_path.open() as f:
            config_data = yaml.safe_load(f)
        if config_data and "cli" in config_data:
            return config_data["cli"]
    except Exception:  # noqa: BLE001, S110
        pass
    return {}


# Cached CLI config (loaded once)
_cli_config: dict[str, Any] | None = None


def _get_cli_config() -> dict[str, Any]:
    """Get cached CLI config, loading from file if needed."""
    global _cli_config  # noqa: PLW0603
    if _cli_config is None:
        _cli_config = _load_cli_config()
    return _cli_config


def _reset_cli_config() -> None:
    """Reset cached CLI config (useful for testing)."""
    global _cli_config  # noqa: PLW0603
    _cli_config = None


class ThemeManager:
    """Manages theme detection and color palettes.

    Singleton class that handles:
    - Palette selection via PTC_PALETTE environment variable or config file
    - Auto-detection of terminal background (dark vs light)
    - Manual theme override via PTC_THEME environment variable or config file
    - NO_COLOR support for accessibility
    - Syntax highlighting theme selection

    Configuration priority (highest to lowest):
    1. Environment variables (PTC_PALETTE, PTC_THEME)
    2. Config file (config.yaml → cli.palette, cli.theme)
    3. Defaults (emerald, auto)
    """

    _instance: ThemeManager | None = None

    # Syntax highlighting themes (from Pygments)
    SYNTAX_THEMES = {
        "dark": "monokai",
        "light": "default",
    }

    # Toolbar styles for prompt-toolkit
    TOOLBAR_STYLES = {
        "dark": {
            "bottom-toolbar": "noreverse",
            "toolbar-cyan": "bg:#06b6d4 #000000",
            "toolbar-dim": "bg:#374151 #ffffff",
            "toolbar-exit": "bg:#2563eb #ffffff",
            "toolbar-yellow": "bg:#f59e0b #000000",  # For soft-interrupt status
        },
        "light": {
            "bottom-toolbar": "noreverse",
            "toolbar-cyan": "bg:#0891b2 #ffffff",
            "toolbar-dim": "bg:#d1d5db #1f2937",
            "toolbar-exit": "bg:#1d4ed8 #ffffff",
            "toolbar-yellow": "bg:#d97706 #ffffff",  # For soft-interrupt status
        },
    }

    def __init__(self) -> None:
        """Initialize theme manager with environment detection."""
        self._mode = self._get_configured_mode()
        self._detected_background: Literal["dark", "light"] | None = None
        self._colors_disabled = self._check_no_color()
        # Palette must be determined after mode (default depends on dark/light)
        self._palette_name = self._get_configured_palette()

    @classmethod
    def get_instance(cls) -> ThemeManager:
        """Get singleton instance of ThemeManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def _check_no_color(self) -> bool:
        """Check if NO_COLOR environment variable is set."""
        return os.environ.get("NO_COLOR", "") != ""

    def _get_configured_palette(self) -> str:
        """Get palette name from environment variable or config file.

        Priority: PTC_PALETTE env var > config file > default
        Default: Nord for dark mode, Tokyo Night for light mode
        """
        # 1. Check environment variable
        env_palette = os.environ.get("PTC_PALETTE")
        if env_palette:
            palette = env_palette.lower()
            if palette in AVAILABLE_PALETTES:
                return palette

        # 2. Check config file
        cli_config = _get_cli_config()
        if config_palette := cli_config.get("palette"):
            palette = str(config_palette).lower()
            if palette in AVAILABLE_PALETTES:
                return palette

        # 3. Default based on theme mode
        return DEFAULT_PALETTE_DARK if self.is_dark else DEFAULT_PALETTE_LIGHT

    def _get_configured_mode(self) -> ThemeMode:
        """Get theme mode from environment variable or config file.

        Priority: PTC_THEME env var > config file > default (auto)
        """
        # 1. Check environment variable
        env_theme = os.environ.get("PTC_THEME")
        if env_theme:
            mode = env_theme.lower()
            if mode == "light":
                return ThemeMode.LIGHT
            if mode == "dark":
                return ThemeMode.DARK
            return ThemeMode.AUTO

        # 2. Check config file
        cli_config = _get_cli_config()
        if config_theme := cli_config.get("theme"):
            mode = str(config_theme).lower()
            if mode == "light":
                return ThemeMode.LIGHT
            if mode == "dark":
                return ThemeMode.DARK

        # 3. Default
        return ThemeMode.AUTO

    def _detect_terminal_background(self) -> Literal["dark", "light"]:
        """Detect terminal background color using multiple strategies."""
        # Strategy 1: Check COLORFGBG environment variable
        colorfgbg = os.environ.get("COLORFGBG", "")
        min_colorfgbg_parts = 2
        if colorfgbg:
            parts = colorfgbg.split(";")
            if len(parts) >= min_colorfgbg_parts:
                try:
                    bg = int(parts[-1])
                    if bg in (0, 1, 2, 3, 4, 5, 6, 8):
                        return "dark"
                    if bg in (7, 15):
                        return "light"
                except ValueError:
                    pass

        # Strategy 2: Use darkdetect for macOS system appearance
        if darkdetect is not None:
            try:
                if darkdetect.isDark() is False:
                    return "light"
            except Exception:  # noqa: BLE001, S110
                pass

        return "dark"

    @property
    def palette_name(self) -> str:
        """Get the current palette name."""
        return self._palette_name

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark mode."""
        if self._mode == ThemeMode.LIGHT:
            return False
        if self._mode == ThemeMode.DARK:
            return True
        if self._detected_background is None:
            self._detected_background = self._detect_terminal_background()
        return self._detected_background == "dark"

    @property
    def colors_disabled(self) -> bool:
        """Check if colors should be disabled (NO_COLOR is set)."""
        return self._colors_disabled

    @property
    def palette(self) -> ColorPalette:
        """Get current color palette based on selected palette and theme mode."""
        mode_key = "dark" if self.is_dark else "light"
        return PALETTES[self._palette_name][mode_key]

    @property
    def syntax_theme(self) -> str:
        """Get syntax highlighting theme name for Rich/Pygments."""
        return self.SYNTAX_THEMES["dark" if self.is_dark else "light"]

    @property
    def toolbar_styles(self) -> dict[str, str]:
        """Get toolbar styles for prompt-toolkit."""
        return self.TOOLBAR_STYLES["dark" if self.is_dark else "light"]

    def get_colors_dict(self) -> dict[str, str]:
        """Get colors as dictionary (backward compatible with COLORS dict)."""
        if self._colors_disabled:
            return {
                "primary": "",
                "dim": "",
                "user": "",
                "agent": "",
                "thinking": "",
                "tool": "",
            }
        p = self.palette
        return {
            "primary": p.primary,
            "dim": p.dim,
            "user": p.user,
            "agent": p.agent,
            "thinking": p.thinking,
            "tool": p.tool,
        }


# Convenience functions for global access


def get_theme() -> ThemeManager:
    """Get the global theme manager instance."""
    return ThemeManager.get_instance()


def get_colors() -> dict[str, str]:
    """Get current colors dictionary."""
    return get_theme().get_colors_dict()


def get_syntax_theme() -> str:
    """Get current syntax highlighting theme name."""
    return get_theme().syntax_theme


def get_toolbar_styles() -> dict[str, str]:
    """Get current toolbar styles for prompt-toolkit."""
    return get_theme().toolbar_styles


def get_available_palettes() -> list[str]:
    """Get list of available palette names."""
    return AVAILABLE_PALETTES.copy()
