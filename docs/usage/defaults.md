---
hide:
  - toc
---

# AIMBAT defaults

AIMBAT behaviour can be customised via the following settings. Each setting can
be overridden on a per-project basis (in order of precedence):

- Environment variables of the form `AIMBAT_<SETTING_NAME>` (e.g.
    `AIMBAT_LOG_LEVEL=DEBUG`).
- A `.env`[^1] file in the current working directory (e.g.
    `AIMBAT_LOG_LEVEL=DEBUG`).

{{ settings_table }}

!!! tip "Viewing the settings in effect"

    `aimbat utils settings` shows the settings currently in use; `--no-pretty`
    prints them as `KEY="value"` pairs ready to paste into `.env`.

[^1]: Literally a file called `.env` (not `<SOMETHING>.env`).
