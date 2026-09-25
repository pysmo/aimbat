"""Helpers for displaying exceptions to users."""

__all__ = ["exception_message"]


def exception_message(exc: BaseException) -> str:
    """Return an exception's message together with any notes attached to it.

    Code that knows context the raising site does not - which data source was
    being read, say - attaches it with `BaseException.add_note` instead of
    re-raising a different exception type. Notes only show up in a traceback,
    so anything that reports an exception without one has to add them back.

    Args:
        exc: The exception to describe.

    Returns:
        The exception's message, followed by one line per note.
    """
    return "\n".join([str(exc), *getattr(exc, "__notes__", [])])
