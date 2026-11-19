"""Tab completion for `aimbat shell`, including choices and record IDs."""

import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cyclopts import App, Argument
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    NestedCompleter,
)
from prompt_toolkit.document import Document

from .common import PhaseNameConverter, UuidConverter, describe_records

if TYPE_CHECKING:
    from aimbat.models import AimbatTypes

__all__ = ["ShellCompleter"]

# What an argument's value is completed from: an ID lookup, the names of
# phases, or fixed choices.
type _Values = UuidConverter | PhaseNameConverter | tuple[str, ...]


@dataclass(frozen=True)
class _IdChoice:
    short: str
    clean: str
    meta: str


@dataclass(frozen=True)
class _Word:
    """The word under the cursor, as typed and as the command will read it."""

    value: str  # Unquoted, without a leading `--option=`.
    length: int  # Characters it spans on the line, quotes included.
    quote: str = ""  # An opening quote not yet closed.
    lead: str = ""  # `--option=` typed before the value.

    def completion(self, candidate: str, meta: str | None = None) -> Completion:
        """Replace the word with `candidate`, closing any open quote."""
        return Completion(
            self.lead + self.quote + candidate + self.quote,
            start_position=-self.length,
            display=candidate,
            display_meta=meta,
        )


class ShellCompleter(Completer):
    """Completes commands and options, and the values of arguments.

    Values are completed for arguments with fixed choices (e.g. a parameter
    name) and for arguments that take a record ID.

    IDs are read from the project database and cached until `invalidate` is
    called, which the shell does after every command. Records written
    elsewhere (the TUI, another process) appear after the next command.
    """

    def __init__(
        self,
        app: App,
        nested: NestedCompleter,
        shell_only: dict[tuple[str, ...], UuidConverter | PhaseNameConverter]
        | None = None,
    ) -> None:
        """Create the completer.

        Args:
            app: The AIMBAT cyclopts app, used to find which arguments take IDs.
            nested: Completer for the subcommands of command groups.
            shell_only: The argument (an ID or a phase name) of commands that
                exist only in the shell, keyed by command path (e.g.
                `("event", "switch")`).
        """
        self._app = app
        self._nested = nested
        self._shell_only = shell_only or {}
        self._cache: dict[type, list[_IdChoice]] = {}
        self._phase_cache: dict[str | None, list[str]] = {}

    def invalidate(self) -> None:
        """Forget cached IDs and names, so the next completion reads them again."""
        self._cache.clear()
        self._phase_cache.clear()

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        """Yield completions for the text before the cursor."""
        # Private in cyclopts, but it is the parser the CLI itself uses, so the
        # shell's slots can't drift from the CLI's. Tests cover every use.
        from cyclopts.completion._engine import resolve_slot
        from cyclopts.completion._readline import split_line

        text = document.text_before_cursor
        if (split := split_line(text)) is None:
            return  # e.g. a trailing backslash.
        words, quote = split
        word = _Word(words[-1], len(text) - _word_start(text), quote)

        for path, converter in self._shell_only.items():
            if tuple(words[:-1]) == path and not words[-1].startswith("-"):
                yield from self._value_completions(converter, word)
                return

        # cyclopts' completion engine parses the line as the CLI would, so the
        # argument under the cursor matches what the command will receive.
        slot = resolve_slot(self._app, words)
        if slot is None:
            return
        if slot.command_app.default_command is None:
            # A command group: complete its subcommands, including shell-only ones.
            yield from self._nested.get_completions(document, complete_event)
            return

        word = _Word(slot.incomplete, word.length, quote, slot.prefix)
        typed = slot.unused  # The words after the command.
        after_dash = "--" in typed  # Only positional values follow `--`.
        names = {name for arg in slot.arguments for name in arg.names}
        if not after_dash and typed and typed[-1].startswith("-"):
            if typed[-1] not in names:
                return  # An unknown option might take a value. Don't guess.

        active = slot.active
        if active is not None and not slot.option_name:
            if (values := _values(active)) is not None:
                yield from self._value_completions(
                    values, word, event=_typed_event(slot.arguments)
                )
            if slot.prefix or (typed and typed[-1] in active.names):
                return  # The word is an option's value, so no options follow.
        if after_dash or (slot.incomplete and not slot.incomplete.startswith("-")):
            return
        hidden = set(slot.command_app.help_flags) | set(slot.command_app.version_flags)
        for arg in slot.arguments:
            if not arg.show or arg.tokens:
                continue
            for name in arg.names:
                if name.startswith("-") and name not in hidden:
                    if name.startswith(slot.incomplete):
                        yield word.completion(name)

    def _value_completions(
        self, values: _Values, word: _Word, event: str | None = None
    ) -> Iterator[Completion]:
        if isinstance(values, PhaseNameConverter):
            values = tuple(self._phase_names(event))
        if isinstance(values, tuple):
            for name in values:
                if name.startswith(word.value):
                    yield word.completion(name)
            return
        converter = values
        typed = word.value.replace("-", "").lower()
        if converter.allow_all and "all".startswith(word.value.lower()):
            yield word.completion("all")
        for choice in self._choices(converter.model_class):
            if choice.clean.startswith(typed):
                yield word.completion(choice.short, choice.meta)

    def _choices(self, model_class: "type[AimbatTypes]") -> list[_IdChoice]:
        if model_class not in self._cache:
            try:
                self._cache[model_class] = _read_choices(model_class)
            except Exception as e:
                # No project, or one the shell can't read: offer no IDs rather
                # than break the prompt. Cached, so it is logged once per command.
                from aimbat.logger import logger

                logger.debug(f"No {model_class.__name__} IDs to complete: {e}")
                self._cache[model_class] = []
        return self._cache[model_class]

    def _phase_names(self, event: str | None) -> list[str]:
        if event not in self._phase_cache:
            try:
                self._phase_cache[event] = _read_phase_names(event)
            except Exception as e:
                from aimbat.logger import logger

                logger.debug(f"No phase names to complete: {e}")
                self._phase_cache[event] = []
        return self._phase_cache[event]


def _word_start(text: str) -> int:
    """Return where the last word of `text` starts, counting its quotes."""
    start, quote, escaped = 0, "", False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char.isspace():
            start = i + 1
    return start


def _values(arg: Argument) -> _Values | None:
    """Return what `arg`'s value is completed from, if anything."""
    converter = arg.parameter.converter
    if isinstance(converter, (UuidConverter, PhaseNameConverter)):
        return converter
    # `force`: choices hidden from help (`show_choices=False`) still complete.
    return arg.get_choices(force=True) or None


def _read_choices(model_class: "type[AimbatTypes]") -> list[_IdChoice]:
    """Read the IDs of `model_class` records, shortened as in AIMBAT's tables."""
    from sqlmodel import Session

    from aimbat.db import engine

    with Session(engine) as session:
        return [
            _IdChoice(short, str(record_id).replace("-", ""), meta)
            for record_id, short, meta in describe_records(
                session, model_class, event_id=_shell_event_id()
            )
        ]


def _typed_event(arguments: Iterable[Argument]) -> str | None:
    """Return the event typed on the line (an ID, a prefix or "all"), if any."""
    from aimbat.models import AimbatEvent

    for arg in arguments:
        converter = arg.parameter.converter
        if (
            isinstance(converter, UuidConverter)
            and converter.model_class is AimbatEvent
            and arg.tokens
        ):
            return arg.tokens[-1].value
    return None


def _read_phase_names(event: str | None) -> list[str]:
    """Read the phase names of an event, or of every event, sorted.

    `event` is as typed on the line. Without it the shell's event context
    is used, and every event's phases without that.
    """
    from sqlmodel import Session, col, select

    from aimbat.db import engine
    from aimbat.models import AimbatEvent, AimbatPhase
    from aimbat.utils import string_to_uuid

    with Session(engine) as session:
        event_id: uuid.UUID | None
        if event is None:
            event_id = _shell_event_id()
        elif event.lower() == "all":
            event_id = None
        else:
            try:
                event_id = uuid.UUID(event)
            except ValueError:
                event_id = string_to_uuid(session, event, AimbatEvent)
        statement = select(AimbatPhase.name).distinct()
        if event_id is not None:
            statement = statement.where(col(AimbatPhase.event_id) == event_id)
        return sorted(session.exec(statement).all())


def _shell_event_id() -> uuid.UUID | None:
    """Return the shell's event context (see `event switch`), if one is set.

    An `--event` typed on the line is not considered: no command that takes a
    seismogram or snapshot ID also takes one.
    """
    import os

    try:
        return uuid.UUID(os.environ.get("DEFAULT_EVENT_ID", ""))
    except ValueError:
        return None
