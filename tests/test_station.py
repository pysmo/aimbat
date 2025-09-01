import pytest


class TestCliStation:
    def test_sac_data(self, test_data_string, db_url, capsys) -> None:  # type: ignore
        """Test AIMBAT cli with station subcommand."""

        from aimbat.app import app

        app("snapshot")
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])

        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)

        with pytest.raises(RuntimeError):
            app(["station", "list", "--db-url", db_url])

        app(["station", "list", "--all", "--db-url", db_url])
        assert "BAK - CI" in capsys.readouterr().out

        app(["event", "activate", "1", "--db-url", db_url])

        app(["station", "list", "--db-url", db_url])
        assert "BAK - CI" in capsys.readouterr().out
