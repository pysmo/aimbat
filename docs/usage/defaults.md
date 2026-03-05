# AIMBAT defaults

AIMBAT behaviour can be customised via the following settings.
Each setting can be overridden on a per-project basis (in order of precedence):

- Environment variables of the form `AIMBAT_<SETTING_NAME>` (e.g. `AIMBAT_LOG_LEVEL=DEBUG`).
- A `.env`[^1] file in the current working directory (e.g. `AIMBAT_LOG_LEVEL=DEBUG`).

[^1]: Literally a file called `.env` (not `<SOMETHING>.env`).

--8<-- "docs/usage/defaults-table.md"

!!! tip
    To view the settings currently in use, run `aimbat utils settings`.
