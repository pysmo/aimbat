from aimbat.cli.common import GlobalParameters


def cli_settings_list(
    *,
    pretty: bool = True,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print a table with default settings used in AIMBAT.

    These defaults control the default behavior of AIMBAT within a project.
    They can be changed using environment variables of the same name, or by
    adding a `.env` file to the current working directory.

    Parameters:
        pretty: Print the table in a pretty format.
    """
    from aimbat.config import print_settings_table

    global_parameters = global_parameters or GlobalParameters()

    print_settings_table(pretty)
