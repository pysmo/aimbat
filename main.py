"""zensical `macros` plugin entry point for the documentation build.

Exposes AIMBAT `Settings` default values to Markdown pages as Jinja
variables, so documentation never has to hand-type a value that could
drift from `src/aimbat/_config.py`.
"""

from zensical.extensions.macros import MacroEnv

from aimbat._config import generate_settings_table_markdown, get_default_settings


def _format_seconds(seconds: float) -> str:
    return f"{seconds:g} s"


def define_env(env: MacroEnv) -> None:
    """Register macro variables for use in documentation pages."""
    settings = get_default_settings()
    env.variables["event_duplicate_tolerance"] = _format_seconds(
        settings.event_duplicate_tolerance.total_seconds()
    )
    env.variables["event_duplicate_raise_tolerance"] = _format_seconds(
        settings.event_duplicate_raise_tolerance.total_seconds()
    )
    env.variables["settings_table"] = generate_settings_table_markdown()
