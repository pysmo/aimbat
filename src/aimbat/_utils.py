from contextlib import suppress


def export_module_names(globals_dict: dict, module_name: str) -> None:
    """
    Updates the __module__ attribute of all objects in __all__ to match
    the current module name.

    Args:
        globals_dict: The globals() dictionary of the calling module.
        module_name: The name of the calling module (usually __name__).
    """
    all_names = globals_dict.get("__all__", [])

    for name in all_names:
        obj = globals_dict.get(name)
        if obj is not None and hasattr(obj, "__module__"):
            with suppress(AttributeError, TypeError):
                obj.__module__ = module_name
