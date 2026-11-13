"""Functional tests for the `utils completion` CLI commands.

`HOME` is patched to a temporary directory, and variables that move the
default install locations are cleared, so files on the real system are never
touched. Paths are passed to `cli` as token lists, which keeps Windows
backslashes intact.
"""

import os
import shlex
from collections.abc import Callable
from pathlib import Path

import cyclopts.completion
import pytest
from cyclopts.completion import ShellDetectionError

from aimbat import settings

_INSTALL = ["utils", "completion", "install"]


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points `HOME` at a temporary directory and clears location overrides.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The temporary home directory.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # `Path.home()` on Windows
    for var in (
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "BASH_COMPLETION_USER_DIR",
        "ZSH_CUSTOM",
        "ZSH",
        "ZDOTDIR",
    ):
        monkeypatch.delenv(var, raising=False)
    return home


class TestCompletionShow:
    """Tests for `utils completion show`."""

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
    def test_show_covers_nested_commands(
        self,
        shell: str,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies the script names the program and reaches nested choices.

        Args:
            shell: Shell to generate the script for.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"utils completion show --shell {shell}")
        out = capsys.readouterr().out
        assert "aimbat" in out
        assert "mccc-damp" in out, "event parameter names should be completed"
        assert "json-station" in out, "data add --type choices should be completed"

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
    def test_show_stamps_aimbat_version(
        self,
        shell: str,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies the script records the AIMBAT version that generated it.

        Args:
            shell: Shell to generate the script for.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        from aimbat.app import __version__

        cli(f"utils completion show --shell {shell}")
        lines = capsys.readouterr().out.splitlines()
        assert f"# Generated for aimbat {__version__}" in lines[:2]
        if shell == "zsh":
            assert lines[0].startswith("#compdef"), "zsh needs #compdef first"

    def test_zsh_script_calls_its_completion_function(
        self,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies the zsh script defines and then calls its function.

        Without the call, zsh only runs the function when the file is named
        exactly after it, so a file saved as `_aimbat` would complete nothing.

        Args:
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("utils completion show --shell zsh")
        out = capsys.readouterr().out
        assert "_cyclopts_aimbat() {" in out
        assert out.rstrip().endswith('_cyclopts_aimbat "$@"')

    def test_show_uses_detected_shell(
        self,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies the detected shell is used when `--shell` is omitted.

        Args:
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        monkeypatch.setattr(cyclopts.completion, "detect_shell", lambda: "fish")
        cli("utils completion show")
        assert "complete -c aimbat" in capsys.readouterr().out

    def test_show_fails_when_shell_undetectable(
        self,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies a clear error when the shell can't be detected.

        Args:
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """

        def _fail() -> str:
            raise ShellDetectionError("no shell")

        monkeypatch.setattr(cyclopts.completion, "detect_shell", _fail)
        # At INFO, handle_issues reports the error and exits instead of re-raising.
        monkeypatch.setattr(settings, "log_level", "INFO")
        with pytest.raises(SystemExit) as exc_info:
            cli("utils completion show")
        assert exc_info.value.code == 1
        assert "--shell" in capsys.readouterr().err


class TestCompletionInstall:
    """Tests for `utils completion install`."""

    def test_install_to_output_matches_show(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies `--output` receives the same script that `show` prints.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        target = tmp_path / "aimbat.bash"
        cli([*_INSTALL, "--yes", "--shell", "bash", "--output", str(target)])
        capsys.readouterr()
        cli("utils completion show --shell bash")
        assert target.read_text() == capsys.readouterr().out

    def test_install_default_location_leaves_startup_files_alone(
        self,
        home: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies the default install writes the script but no rc file.

        Args:
            home: The temporary home directory.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("utils completion install --yes --shell zsh")
        script = home / ".zsh" / "completions" / "_aimbat"
        assert script.is_file()
        assert not (home / ".zshrc").exists()
        fpath_line = f"fpath=({shlex.quote(str(script.parent))} $fpath)"
        assert fpath_line in capsys.readouterr().out

    def test_add_to_startup_edits_bashrc_once(
        self,
        home: Path,
        cli: Callable[[str | list[str]], None],
    ) -> None:
        """Verifies `--add-to-startup` adds one loader line, even when re-run.

        Args:
            home: The temporary home directory.
            cli: The in-process CLI callable.
        """
        cli("utils completion install --yes --shell bash --add-to-startup")
        cli("utils completion install --yes --shell bash --add-to-startup")
        script = (
            home / ".local" / "share" / "bash-completion" / "completions" / "aimbat"
        )
        bashrc = (home / ".bashrc").read_text()
        assert bashrc.count("# Load aimbat completion") == 1
        assert f'. "{script}"' in bashrc

    @pytest.mark.parametrize(
        ("shell", "env", "expected"),
        [
            ("bash", {}, ".local/share/bash-completion/completions/aimbat"),
            (
                "bash",
                {"XDG_DATA_HOME": "{tmp}/data"},
                "data/bash-completion/completions/aimbat",
            ),
            (
                "bash",
                {
                    "XDG_DATA_HOME": "{tmp}/data",
                    "BASH_COMPLETION_USER_DIR": "{tmp}/bc{sep}{tmp}/other",
                },
                "bc/completions/aimbat",
            ),
            ("fish", {}, ".config/fish/completions/aimbat.fish"),
            (
                "fish",
                {"XDG_CONFIG_HOME": "{tmp}/cfg"},
                "cfg/fish/completions/aimbat.fish",
            ),
        ],
    )
    def test_install_follows_shell_location_conventions(
        self,
        shell: str,
        env: dict[str, str],
        expected: str,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies bash and fish installs honour the shells' own variables.

        `BASH_COMPLETION_USER_DIR` takes precedence over `XDG_DATA_HOME`, and
        only its first entry is used.

        Args:
            shell: Shell to install for.
            env: Environment variables to set. `{tmp}` is replaced by `tmp_path`
                and `{sep}` by the path list separator.
            expected: Expected script path, relative to `HOME` when `env` is
                empty and to `tmp_path` otherwise.
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            monkeypatch: The pytest monkeypatch fixture.
        """
        for var, value in env.items():
            monkeypatch.setenv(var, value.format(tmp=tmp_path, sep=os.pathsep))
        cli(f"utils completion install --yes --shell {shell}")
        assert ((tmp_path if env else home) / expected).is_file()

    def test_add_to_startup_is_a_no_op_for_fish(
        self,
        home: Path,
        cli: Callable[[str | list[str]], None],
    ) -> None:
        """Verifies fish needs no startup file, so none is written.

        Args:
            home: The temporary home directory.
            cli: The in-process CLI callable.
        """
        cli("utils completion install --yes --shell fish --add-to-startup")
        assert (home / ".config" / "fish" / "completions" / "aimbat.fish").is_file()
        assert not (home / ".config" / "fish" / "config.fish").exists()

    def test_add_to_startup_starts_zsh_completion_once(
        self,
        home: Path,
        cli: Callable[[str | list[str]], None],
    ) -> None:
        """Verifies `.zshrc` gets the fpath line first and one compinit call.

        Args:
            home: The temporary home directory.
            cli: The in-process CLI callable.
        """
        cli("utils completion install --yes --shell zsh --add-to-startup")
        cli("utils completion install --yes --shell zsh --add-to-startup")
        lines = (home / ".zshrc").read_text().splitlines()
        fpath_line = f"fpath=({shlex.quote(str(home / '.zsh' / 'completions'))} $fpath)"
        assert lines[:2] == ["# aimbat completions", fpath_line]
        assert lines.count(fpath_line) == 1
        assert lines.count("autoload -Uz compinit && compinit") == 1

    def test_add_to_startup_keeps_existing_zsh_compinit(
        self,
        home: Path,
        cli: Callable[[str | list[str]], None],
    ) -> None:
        """Verifies no second compinit call is added to a `.zshrc` with one.

        Args:
            home: The temporary home directory.
            cli: The in-process CLI callable.
        """
        zshrc = home / ".zshrc"
        zshrc.write_text("autoload -U compinit\ncompinit -i\n")
        cli("utils completion install --yes --shell zsh --add-to-startup")
        content = zshrc.read_text()
        assert content.startswith("# aimbat completions\nfpath=(")
        assert content.endswith("autoload -U compinit\ncompinit -i\n")

    @pytest.mark.parametrize(
        ("zshrc", "adds_compinit"),
        [
            ("# compinit\n", True),
            ("autoload -Uz compinit\n", True),
            ("autoload -U compinit; compinit -i\n", False),
            ("autoload -Uz compinit && compinit\n", False),
            ("  compinit\n", False),
        ],
    )
    def test_add_to_startup_detects_compinit_calls(
        self,
        zshrc: str,
        adds_compinit: bool,
        home: Path,
        cli: Callable[[str | list[str]], None],
    ) -> None:
        """Verifies comments and bare autoloads don't count as a compinit call.

        Args:
            zshrc: Existing `.zshrc` contents.
            adds_compinit: Whether a compinit call is expected to be added.
            home: The temporary home directory.
            cli: The in-process CLI callable.
        """
        (home / ".zshrc").write_text(zshrc)
        cli("utils completion install --yes --shell zsh --add-to-startup")
        line = "autoload -Uz compinit && compinit"
        content = (home / ".zshrc").read_text()
        assert content.count(line) == zshrc.count(line) + adds_compinit

    @pytest.mark.parametrize("shell", ["bash", "fish"])
    def test_custom_location_prints_quoted_loader(
        self,
        shell: str,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a script outside the shell's lookup path isn't called automatic.

        Args:
            shell: Shell to install for.
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        target = tmp_path / "$dir" / f"aimbat.{shell}"
        cli([*_INSTALL, "--yes", "--shell", shell, "--output", str(target)])
        out = capsys.readouterr().out
        quoted = shlex.quote(str(target))
        assert "automatically" not in out
        assert quoted.startswith("'")
        assert quoted in out

    def test_fish_custom_location_refuses_add_to_startup(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies fish `--add-to-startup` with `--output` fails before writing.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        monkeypatch.setattr(settings, "log_level", "INFO")
        target = tmp_path / "aimbat.fish"
        with pytest.raises(SystemExit) as exc_info:
            cli(
                [*_INSTALL, "--yes", "--shell", "fish", "--output", str(target)]
                + ["--add-to-startup"]
            )
        assert exc_info.value.code == 1
        assert "--add-to-startup" in capsys.readouterr().err
        assert not target.exists()

    def test_add_to_startup_honours_zdotdir(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies the zsh startup file is looked up in `$ZDOTDIR`.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            monkeypatch: The pytest monkeypatch fixture.
        """
        zdotdir = tmp_path / "zdot"
        monkeypatch.setenv("ZDOTDIR", str(zdotdir))
        cli("utils completion install --yes --shell zsh --add-to-startup")
        assert (zdotdir / ".zshrc").is_file()
        assert not (home / ".zshrc").exists()

    def test_oh_my_zsh_needs_no_startup_change(
        self,
        home: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies the oh-my-zsh completions directory is used as is.

        Args:
            home: The temporary home directory.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        omz = home / ".oh-my-zsh"
        omz.mkdir()
        monkeypatch.setenv("ZSH", str(omz))
        cli("utils completion install --yes --shell zsh --add-to-startup")
        assert (omz / "custom" / "completions" / "_aimbat").is_file()
        assert not (home / ".zshrc").exists()
        assert "Loaded automatically by oh-my-zsh" in capsys.readouterr().out

    def test_oh_my_zsh_with_output_elsewhere_adds_fpath_only(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies oh-my-zsh users get the fpath line but no extra compinit.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            monkeypatch: The pytest monkeypatch fixture.
        """
        omz = home / ".oh-my-zsh"
        omz.mkdir()
        monkeypatch.setenv("ZSH", str(omz))
        target = tmp_path / "comp" / "_aimbat"
        cli(
            [*_INSTALL, "--yes", "--shell", "zsh", "--output", str(target)]
            + ["--add-to-startup"]
        )
        content = (home / ".zshrc").read_text()
        assert f"fpath=({shlex.quote(str(target.parent))} $fpath)" in content
        assert "compinit" not in content

    def test_zsh_output_without_underscore_is_refused(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies a zsh script name zsh would ignore is rejected.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        monkeypatch.setattr(settings, "log_level", "INFO")
        target = tmp_path / "aimbat.zsh"
        with pytest.raises(SystemExit) as exc_info:
            cli([*_INSTALL, "--yes", "--shell", "zsh", "--output", str(target)])
        assert exc_info.value.code == 1
        assert "underscore" in capsys.readouterr().err
        assert not target.exists()

    def test_printed_loader_lines_are_quoted(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies paths with spaces or quotes survive being pasted.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        zsh_target = tmp_path / "my comps" / "_aimbat"
        cli([*_INSTALL, "--yes", "--shell", "zsh", "--output", str(zsh_target)])
        quoted = shlex.quote(str(zsh_target.parent))
        assert quoted.startswith("'")
        assert f"fpath=({quoted} $fpath)" in capsys.readouterr().out

        ps_target = tmp_path / "it's" / "aimbat.ps1"
        cli([*_INSTALL, "--yes", "--shell", "powershell", "--output", str(ps_target)])
        escaped = str(ps_target).replace("'", "''")
        assert f". '{escaped}'" in capsys.readouterr().out

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_declining_writes_nothing(
        self,
        shell: str,
        home: Path,
        cli: Callable[[str | list[str]], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies a declined prompt names the path and leaves no trace.

        Args:
            shell: Shell to install for.
            home: The temporary home directory.
            cli: The in-process CLI callable.
            monkeypatch: The pytest monkeypatch fixture.
        """
        from rich.prompt import Confirm

        asked: list[str] = []

        def _decline(message: str, **_: object) -> bool:
            asked.append(message)
            return False

        monkeypatch.setattr(Confirm, "ask", _decline)
        cli(f"utils completion install --shell {shell} --add-to-startup")
        assert len(asked) == 1
        assert str(home) in asked[0]
        assert list(home.iterdir()) == [], "no files or directories created"

    def test_prompt_says_overwrite_for_existing_script(
        self,
        home: Path,
        tmp_path: Path,
        cli: Callable[[str | list[str]], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies re-installing over an existing script asks to overwrite it.

        Args:
            home: The temporary home directory.
            tmp_path: The pytest tmp_path fixture.
            cli: The in-process CLI callable.
            monkeypatch: The pytest monkeypatch fixture.
        """
        from rich.prompt import Confirm

        asked: list[str] = []

        def _accept(message: str, **_: object) -> bool:
            asked.append(message)
            return True

        target = tmp_path / "aimbat.bash"
        monkeypatch.setattr(Confirm, "ask", _accept)
        cli([*_INSTALL, "--shell", "bash", "--output", str(target)])
        cli([*_INSTALL, "--shell", "bash", "--output", str(target)])
        assert asked[0].startswith("Write ")
        assert asked[1].startswith("Overwrite ")
        assert target.is_file()
