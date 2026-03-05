# Python API

If none of the above interfaces suit your needs, or you want to write custom
scripts, you can use the AIMBAT Python API. This is the most powerful way to
interact with your projects.

## Core Concepts

The API is built on three main components:

1. **Models**: [SQLModel](https://sqlmodel.tiangolo.com) classes that represent
    the database schema (`aimbat.models`) as Python objects.
2. **Core Functions**: High-level operations that manipulate those models
    (`aimbat.core`).
3. **Database Session**: A SQLAlchemy session used to track changes and
    interact with the project database.
