"""Tab completion for `aimbat shell`, including choices and record IDs."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cyclopts import App, Argument
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    NestedCompleter,
)
from prompt_toolkit.document import Document

from .common import UuidConverter

if TYPE_CHECKING:
    from sqlmodel import Session

__all__ = ["ShellCompleter"]

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# What an argument's value is completed from: an ID lookup or fixed choices.
type _Values = UuidConverter | tuple[str, ...]


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
        shell_only: dict[tuple[str, ...], UuidConverter] | None = None,
    ) -> None:
        """Create the completer.

        Args:
            app: The AIMBAT cyclopts app, used to find which arguments take IDs.
            nested: Completer for the subcommands of command groups.
            shell_only: The ID argument of commands that exist only in the
                shell, keyed by command path (e.g. `("event", "switch")`).
        """
        self._app = app
        self._nested = nested
        self._shell_only = shell_only or {}
        self._cache: dict[type, list[_IdChoice]] = {}

    def invalidate(self) -> None:
        """Forget cached IDs, so the next completion reads them again."""
        self._cache.clear()

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
                yield from self._value_completions(values, word)
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

    def _value_completions(self, values: _Values, word: _Word) -> Iterator[Completion]:
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

    def _choices(self, model_class: type) -> list[_IdChoice]:
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
    if isinstance(converter, UuidConverter):
        return converter
    # `force`: choices hidden from help (`show_choices=False`) still complete.
    return arg.get_choices(force=True) or None


def _read_choices(model_class: type) -> list[_IdChoice]:
    """Read the IDs of `model_class` records, shortened as in AIMBAT's tables."""
    from sqlmodel import Session

    from aimbat.db import engine

    with Session(engine) as session:
        return [
            _IdChoice(short, str(record_id).replace("-", ""), meta)
            for record_id, short, meta in _describe(session, model_class)
        ]


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


def _describe(
    session: "Session", model_class: type
) -> Iterator[tuple[uuid.UUID, str, str]]:
    """Yield each record's ID, short ID and a description for the menu.

    Seismograms and snapshots are limited to the shell's event, if set.
    """
    from sqlmodel import col, select

    from aimbat.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatSnapshot,
        AimbatStation,
    )
    from aimbat.utils import uuid_shortener

    def short(record: Any) -> str:
        return uuid_shortener(session, record)

    event_id = _shell_event_id()
    if model_class is AimbatEvent:
        events = select(AimbatEvent).order_by(col(AimbatEvent.time))
        for event in session.exec(events):
            yield event.id, short(event), f"{event.time:{_TIME_FORMAT}}"
    elif model_class is AimbatStation:
        stations = select(AimbatStation).order_by(
            col(AimbatStation.network), col(AimbatStation.name)
        )
        for station in session.exec(stations):
            yield station.id, short(station), f"{station.network}.{station.name}"
    elif model_class is AimbatSeismogram:
        seismograms = (
            select(AimbatSeismogram, AimbatStation, AimbatEvent)
            .join(AimbatStation)
            .join(AimbatEvent)
            .order_by(col(AimbatStation.network), col(AimbatStation.name))
        )
        if event_id is not None:
            seismograms = seismograms.where(AimbatSeismogram.event_id == event_id)
        for seismogram, station, event in session.exec(seismograms):
            meta = f"{station.network}.{station.name} {event.time:{_TIME_FORMAT}}"
            yield seismogram.id, short(seismogram), meta
    elif model_class is AimbatSnapshot:
        snapshots = select(AimbatSnapshot).order_by(col(AimbatSnapshot.time))
        if event_id is not None:
            snapshots = snapshots.where(AimbatSnapshot.event_id == event_id)
        for snapshot in session.exec(snapshots):
            meta = f"{snapshot.time:{_TIME_FORMAT}} {snapshot.comment or ''}"
            yield snapshot.id, short(snapshot), meta.strip()
    else:
        records: Any = session.exec(select(model_class))
        for record in records:
            yield record.id, short(record), ""
