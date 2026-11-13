"""Tab completion for the `aimbat` command in bash, zsh, fish or PowerShell.

`install` writes the completion script to the standard location for the
shell. `show` prints it instead, for placing it manually. Re-run `install`
after upgrading AIMBAT.

The interactive `aimbat shell` has its own completion and needs no setup.
"""

from pathlib import Path
from typing import Annotated, Literal, assert_never

from cyclopts import App, Parameter

from aimbat._cli.common import ConfirmParameters, confirm_or_abort, handle_issues

__all__ = ["completion_cli_install", "completion_cli_show"]

type Shell = Literal["bash", "zsh", "fish", "powershell"]

_PROG_NAME = "aimbat"

app = App(name="completion", help=__doc__, help_format="markdown")

ShellParameter = Annotated[
    Shell | None,
    Parameter(help="Shell to generate completion for. Detected if omitted."),
]


def _generate_script(shell: Shell) -> str:
    """Return the completion script, stamped with the AIMBAT version."""
    # `import aimbat.app` rather than `from aimbat.app import app`: the latter
    # makes mypy resolve `aimbat._cli.utils` to this package instead of the
    # re-exported `App` in `aimbat.app`.
    import aimbat.app

    script = aimbat.app.app.generate_completion(prog_name=_PROG_NAME, shell=shell)
    stamp = f"# Generated for {_PROG_NAME} {aimbat.app.__version__}\n"
    if shell != "zsh":
        return stamp + script
    # zsh only autoloads the file if `#compdef` stays on the first line.
    first, sep, rest = script.partition("\n")
    # cyclopts only defines this function, which zsh then calls only if the
    # file has the same name. Calling it here makes any `_name` file work.
    call = f'\n_cyclopts_{_PROG_NAME} "$@"\n'
    return first + sep + stamp + rest + call


def _omz_completions_dir() -> Path | None:
    """Return oh-my-zsh's custom completions directory, or None without oh-my-zsh."""
    import os

    if (custom := os.environ.get("ZSH_CUSTOM")) and Path(custom).is_dir():
        return Path(custom) / "completions"
    if (omz := os.environ.get("ZSH")) and Path(omz).is_dir():
        return Path(omz) / "custom" / "completions"
    return None


def _zshrc() -> Path:
    """Return the zsh startup file, honouring `$ZDOTDIR`."""
    import os

    return Path(os.environ.get("ZDOTDIR") or Path.home()) / ".zshrc"


def _zsh_fpath_line(directory: Path) -> str:
    import shlex

    return f"fpath=({shlex.quote(str(directory))} $fpath)"


def _calls_compinit(content: str) -> bool:
    """Return whether zsh startup code runs `compinit`, not just autoloads it."""
    import re

    call = re.compile(r"(?:^|[;&|{]|\bthen|\bdo|\belse)\s*compinit\b")
    return any(
        call.search(line.strip())
        for line in content.splitlines()
        if not line.lstrip().startswith("#")
    )


def _add_to_zshrc(script: Path) -> bool:
    """Add `script`'s directory to `fpath` in the zsh startup file.

    Also starts the completion system if the file never calls `compinit`.

    Returns:
        False if the startup file already had the `fpath` line.
    """
    rc = _zshrc()
    content = rc.read_text() if rc.exists() else ""
    fpath_line = _zsh_fpath_line(script.parent)
    if fpath_line in content:
        return False
    # Prepended so it precedes any compinit call, including oh-my-zsh's.
    new = f"# {_PROG_NAME} completions\n{fpath_line}\n{content}"
    if not _calls_compinit(content) and _omz_completions_dir() is None:
        if not new.endswith("\n"):
            new += "\n"
        new += "autoload -Uz compinit && compinit\n"
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text(new)
    return True


def _powershell_quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _default_path(shell: Shell) -> Path:
    """Return where `shell` looks for the user's `aimbat` completion script.

    Creates no directories.
    """
    import os

    match shell:
        case "bash":
            # bash-completion's lookup for user completions. cyclopts ignores
            # both variables. MSYS hands native programs `;`-separated lists.
            user_dirs = [
                d
                for d in os.environ.get("BASH_COMPLETION_USER_DIR", "").split(
                    os.pathsep
                )
                if d
            ]
            if user_dirs:
                base = Path(user_dirs[0])
            else:
                data_home = (
                    os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share"
                )
                base = Path(data_home) / "bash-completion"
            return base / "completions" / _PROG_NAME
        case "fish":
            config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
            return Path(config_home) / "fish" / "completions" / f"{_PROG_NAME}.fish"
        case "zsh":
            # zsh has no standard user directory. Same choice as cyclopts.
            directory = _omz_completions_dir() or Path.home() / ".zsh" / "completions"
            return directory / f"_{_PROG_NAME}"
        case "powershell":
            from cyclopts.completion.install import powershell_profile

            return powershell_profile().parent / "Completions" / f"{_PROG_NAME}.ps1"
    assert_never(shell)


def _resolve_shell(shell: Shell | None) -> Shell:
    from cyclopts.completion import ShellDetectionError, detect_shell

    if shell is not None:
        return shell
    try:
        return detect_shell()
    except ShellDetectionError as e:
        raise RuntimeError(
            "Could not detect the shell. Specify it with --shell."
        ) from e


@app.command(name="install")
@handle_issues
def completion_cli_install(
    *,
    shell: ShellParameter = None,
    output: Annotated[
        Path | None,
        Parameter(
            help="Write the script here instead of the shell's default location."
        ),
    ] = None,
    add_to_startup: Annotated[
        bool,
        Parameter(
            help="Add a line loading the script to the shell's startup file"
            + " (`~/.bashrc`, `~/.zshrc` or PowerShell profile). Not needed for fish."
        ),
    ] = False,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Install tab completion for the `aimbat` command.

    Shows where the script will be written and asks for confirmation first.
    """
    import shlex

    from cyclopts.completion import add_to_rc_file
    from rich.markup import escape

    resolved = _resolve_shell(shell)
    path = (output or _default_path(resolved)).absolute()
    if resolved == "zsh" and not path.name.startswith("_"):
        raise ValueError(
            "zsh only loads completion files whose names start with an"
            + f" underscore (e.g. _{_PROG_NAME})."
        )

    omz = _omz_completions_dir() if resolved == "zsh" else None
    # oh-my-zsh already puts its custom completions directory on fpath.
    on_omz_fpath = omz is not None and path.parent == omz
    # Where bash-completion or fish find the script without a loader line.
    autoloaded = (
        resolved in ("bash", "fish") and path.parent == _default_path(resolved).parent
    )
    if add_to_startup and resolved == "fish" and not autoloaded:
        raise ValueError(
            "--add-to-startup is not supported for fish with a custom --output"
            + " location. Omit --output, or source the script from config.fish."
        )

    startup: str | None = None
    if add_to_startup:
        match resolved:
            case "bash":
                startup = "~/.bashrc"
            case "zsh" if not on_omz_fpath:
                startup = str(_zshrc())
            case "powershell":
                startup = "the PowerShell profile"

    action = "Overwrite" if path.exists() else "Write"
    message = f"{action} the {resolved} completion script at {escape(str(path))}"
    if startup is not None:
        message += f" and add a loader line to {escape(startup)}"
    confirm_or_abort(message + "?", yes=confirm.yes)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_generate_script(resolved))
    print(f"Completion script for {resolved} written to {path}")

    if startup is not None:
        if resolved == "zsh":
            added = _add_to_zshrc(path)
        else:
            assert resolved in ("bash", "powershell")
            added = add_to_rc_file(path, _PROG_NAME, resolved)
        if added:
            print(f"Loader line added to {startup}.")
        else:
            print(f"{startup} already loads the script and was left unchanged.")
        print("Completion takes effect in a new shell session.")
        return

    match resolved:
        case "zsh" if on_omz_fpath:
            print("\nLoaded automatically by oh-my-zsh.")
        case "zsh" if omz is not None:
            print(f"\nAdd this line to {_zshrc()}, before oh-my-zsh is sourced:")
            print(f"    {_zsh_fpath_line(path.parent)}")
        case "zsh":
            print(
                f"\nAdd these lines to {_zshrc()}, before any existing compinit call:"
            )
            print(f"    {_zsh_fpath_line(path.parent)}")
            print("    autoload -Uz compinit && compinit")
        case "bash":
            if autoloaded:
                print(
                    "\nLoaded automatically by bash-completion (v2.8+). Without"
                    + " bash-completion, add this line to ~/.bashrc:"
                )
            else:
                print("\nAdd this line to ~/.bashrc:")
            quoted = shlex.quote(str(path))
            print(f"    [ -f {quoted} ] && . {quoted}")
        case "fish" if autoloaded:
            print("\nLoaded automatically by fish.")
        case "fish":
            print("\nAdd this line to ~/.config/fish/config.fish:")
            print(f"    source {shlex.quote(str(path))}")
        case "powershell":
            print("\nAdd this line to the PowerShell profile ($PROFILE):")
            print(f"    . {_powershell_quote(path)}")
    print("Completion takes effect in a new shell session.")


@app.command(name="show")
@handle_issues
def completion_cli_show(*, shell: ShellParameter = None) -> None:
    """Print the completion script for the `aimbat` command.

    For zsh, save it in a directory on `$fpath` under a name starting with
    an underscore (e.g. `_aimbat`).
    """
    import sys

    sys.stdout.write(_generate_script(_resolve_shell(shell)))
