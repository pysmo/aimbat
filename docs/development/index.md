# Development

This chapter explains how AIMBAT is put together and the rules its code follows.
A script that reads or changes a project through the
[Python API](../usage/api-basics.md) is bound by the same rules, so the chapter
also serves advanced users.

For scripts, [Architecture](architecture.md) describes the choice between
[`aimbat.actions`][aimbat.actions] and [`aimbat.core`][aimbat.core], and how
transactions and caches behave. [Database models](database-models.md) describes
the tables that a query reads, and [Quality validity](quality-validity.md)
explains when a stored quality metric is reported as absent.

AIMBAT shares its tooling, code standards and contribution workflow with pysmo.
These are described in
[pysmo's Development chapter](https://docs.pysmo.org/development/). The AIMBAT
repository is [pysmo/aimbat](https://github.com/pysmo/aimbat), and `make help`
lists its make targets.

## Contributors

AIMBAT is built by
[its contributors](https://github.com/pysmo/aimbat/graphs/contributors).
Xiaoting Lou is the primary author of AIMBAT version 1, which also received
early contributions from Lay Kuan Loh and Arnav Sankaran.
