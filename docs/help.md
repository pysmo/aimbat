# Getting help

## Built-in help

Every command and command group accepts `--help`:

```bash
aimbat --help              # top-level commands
aimbat data --help         # the data group
aimbat data add --help     # one command's options
```

In the TUI, press `?` for the context-aware list of key bindings.

## Documentation

This site covers installation, the full workflow, and the Python API. Search it
before assuming something is undocumented.

## Reporting a problem

Bugs and questions go to the [issue tracker][issues]. Search the open issues
first. A new report should include:

- the AIMBAT version (`#!bash aimbat --version`),
- the command that was run and what happened,
- the output with `--debug` added, or an `AIMBAT_LOGFILE` capture,
- a data source that reproduces it, if one can be shared.

See [Aimbat Defaults](usage/defaults.md) for the logging settings.

[issues]: https://github.com/pysmo/aimbat/issues
