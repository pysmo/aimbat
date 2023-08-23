from __future__ import annotations
from aimbat import __file__ as aimbat_dir
import os
import yaml
from dataclasses import dataclass
from prettytable import PrettyTable


# Defaults shipped with Aimbat
GLOBAL_DEFAULTS_FILE = os.path.join(os.path.dirname(aimbat_dir), 'lib/defaults.yml')
# Default name of the local overrides in the working directory.
LOCAL_DEFAULTS_FILE = 'aimbat.yml'

# Create python dictionary from yaml file
with open(GLOBAL_DEFAULTS_FILE, 'r') as stream:
    global_dict = yaml.safe_load(stream)
    for name in global_dict:
        # Rename the the 'value' key to 'global_value'
        global_dict[name]['global_value'] = global_dict[name].pop('value')
        # get the actual types from the str expressions.
        global_dict[name]['allowed_types'] = tuple(eval(item) for item in global_dict[name]['allowed_types'])


class AimbatDefaultItem:
    """Descriptor class to store and validate aimbat default items."""

    def __set_name__(self, owner: AimbatDefaults, name: str) -> None:
        self.public_name = name
        self.private_name = '_' + name

    def __init__(self, global_value, allowed_types, description: str):  # type: ignore
        self.global_value = global_value
        self.allowed_types = allowed_types
        self.__doc__ = description

    def __get__(self, obj, objtype=None):  # type: ignore
        # Instance attribute accessed on class, return self
        if obj is None:
            return self

        # Try returning the local value stored in the instance
        try:
            return getattr(obj, self.private_name)
        # Assume global value otherwise
        except AttributeError:
            return self.global_value

    def __set__(self, obj, value) -> None:  # type: ignore
        self.validate(obj, value)
        setattr(obj, self.private_name, value)

    def validate(self, obj, value) -> None:  # type: ignore
        if obj.global_only is True:
            raise RuntimeError("global_only flag is set to True - updating defaults is not allowed.")
        if not isinstance(value, self.allowed_types):
            raise ValueError(f"Expected {value} to be of type {self.allowed_types} - found {type(value)}.")


@dataclass
class AimbatDefaults:
    """Class to store and access Aimbat defaults."""

    local_defaults_file: str = LOCAL_DEFAULTS_FILE
    global_only: bool = False

    # Populate class with descriptors for each default item
    for key in global_dict.keys():
        locals()[key] = AimbatDefaultItem(**global_dict[key])

    def __post_init__(self) -> None:
        # Read user defined configuration and update variables
        if os.path.isfile(self.local_defaults_file) and self.global_only is False:
            with open(self.local_defaults_file, 'r') as stream:
                for name, value in yaml.safe_load(stream).items():
                    try:
                        setattr(self, name, value)
                    except AttributeError:
                        raise AttributeError(f"Invalid attribe {name=}.")

    def source(self, key: str) -> str:
        """Returns "global" if there is no local value for a key, or if the local
        value is equal to the global value. Returns "local" otherwise.
        """
        if getattr(self, key) == getattr(type(self), key).global_value:
            return "global"
        else:
            return "local"

    def description(self, key: str) -> str:
        """Returns a string that describes the aimbat default."""
        return getattr(type(self), key).__doc__.partition("\n")[0]

    @property
    def simple_dict(self) -> dict:
        """Returns a simplified dictionary of Aimbat configuration options (i.e.
        without description, allowed types, etc).
        """
        return {item: getattr(self, item) for item in global_dict.keys()}

    def print_yaml(self) -> None:
        """Prints yaml with configuration options"""
        print(yaml.dump(self.simple_dict, default_flow_style=False, explicit_start=True))

    def print_table(self) -> None:
        """Prints a pretty table with Aimbat configuration options."""
        table = PrettyTable()
        table.field_names = ["Name", "Value", "Source", "Description"]
        for key in global_dict.keys():
            table.add_row([key, getattr(self, key), self.source(key),
                           self.description(key)])
        print(table)
