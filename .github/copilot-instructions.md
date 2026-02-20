# GitHub Copilot Instructions for AIMBAT

## Code Style and Standards

### General Principles

- Write clean, readable, and maintainable code
- Write self-documenting code with clear variable and function names
- Suggest improvements to code style, efficiency, and readability in pull
  request reviews

### PEP 8 Compliance

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide for all Python code
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters (Black default)
- Use blank lines to separate functions and classes
- Imports should be grouped: standard library, third-party, local

### Code Formatting

- All code must pass **Black** formatting
  - Target Python versions: 3.12, 3.13, 3.14
  - Line length: 88 characters
  - Run `black .` before committing

- All code must pass **Ruff** linting
  - Configuration in `pyproject.toml`
  - Run `ruff check .` before committing
  - Fix issues with `ruff check --fix .`

### Language

- Use **British English** spelling in all:
  - Comments
  - Docstrings
  - Variable names
  - Documentation
  - Error messages
- Examples:
  - `colour` not `color`
  - `normalise` not `normalize`
  - `initialise` not `initialize`
  - `behaviour` not `behavior`
  - `centre` not `center`

### Documentation Style

#### Docstrings

- Use **Google Style** docstrings for all public functions, classes, and methods
- Don't add the args and return types in the docstring if they are already specified in the type hints.
- Format:

  ```python
  def function_name(param1: type1, param2: type2) -> return_type:
      """Brief one-line description.

      Longer description if needed, explaining the purpose and behaviour
      of the function in more detail.

      Args:
          param1: Description of param1.
          param2: Description of param2.
              Multi-line descriptions should be indented.

      Returns:
          Description of the return value.

      Raises:
          ErrorType: Description of when this error is raised.

      Examples:
          >>> function_name(value1, value2)
          expected_output
      """
  ```

#### Type Hints

- Use type hints for all function parameters and return values
- Use modern Python type syntax (Python 3.12+):
  - `list[str]` not `List[str]`
  - `dict[str, int]` not `Dict[str, int]`
  - `type1 | type2` not `Union[type1, type2]`
  - `type | None` not `Optional[type]`

### Testing

- Write tests for all new functionality
- Use pytest framework
- Tests should be in the `tests/` directory
- Use descriptive test names: `test_function_does_expected_behaviour`
- Try to mirror the directory structure of `src/aimbat/` in `tests/`

### Commit Messages

- Use clear, descriptive commit messages
- Follow conventional commits format when appropriate
- Use British English spelling

## Review Priorities

- Take the above Code Style and Standards into account when reviewing pull requests
- Suggest improvements to code style, efficiency, documentation, and testing
- Suggest improvements to variable names, function names, and overall code readability
- Suggest newer syntax features where appropriate
- Check spelling
- Check if docstrings in existing code follow Google style and suggest improvements if needed

## Project-Specific Guidelines

### Seismology Domain

- Follow seismological conventions for variable names
- Use proper units and document them
- Maintain scientific accuracy in all calculations

### Dependencies

- Minimum Python version: 3.12
- Core dependencies: pysmo, sqlmodel, numpy, scipy, matplotlib
- Keep dependencies up to date

### File Organisation

- Source code in `src/aimbat/`
- Tests in `tests/`
- Documentation in `docs/`
- Use appropriate module structure

## Before Committing

1. Run `black .` to format code
2. Run `ruff check --fix .` to check and fix linting issues
3. Run tests with `pytest`
4. Verify type hints with `mypy`
5. Check British English spelling
6. Ensure docstrings follow Google style
