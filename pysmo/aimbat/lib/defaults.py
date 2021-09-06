#!/usr/bin/env python

import os
import yaml
import pysmo.aimbat
from dataclasses import dataclass
from prettytable import PrettyTable


# Defaults shipped with Aimbat
GLOBAL_DEFAULTS_FILE = os.path.join(os.path.dirname(pysmo.aimbat.__file__), 'lib/defaults.yml')
# Default name of the local overrides in the working directory.
LOCAL_DEFAULTS_FILE = 'aimbat.yml'

# Create python dictionary from yaml file
with open(GLOBAL_DEFAULTS_FILE, 'r') as stream:
    GLOBAL_DEFAULTS_DICT = yaml.safe_load(stream)
    for name in GLOBAL_DEFAULTS_DICT:
        # Rename the the 'value' key to 'global_value'
        GLOBAL_DEFAULTS_DICT[name]['global_value'] = GLOBAL_DEFAULTS_DICT[name].pop('value')
        # get the actual types from the str expressions.
        GLOBAL_DEFAULTS_DICT[name]['allowed_types'] = tuple(eval(item) for item in
                                                            GLOBAL_DEFAULTS_DICT[name]['allowed_types'])


class AimbatDefaultItem():
    """
    Descriptor class to store and validate aimbat default items.
    """
    @property
    def __doc__(self):
        return GLOBAL_DEFAULTS_DICT[self.public_name]['description']

    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = '_' + name

    def __init__(self, global_value, allowed_types, description):
        self.global_value = global_value
        self.allowed_types = allowed_types

    def __get__(self, obj, objtype=None):
        # Instance attribute accessed on class, return self
        if obj is None:
            return self

        # Try returning the local value stored in the instance
        try:
            return getattr(obj, self.private_name)
        # Assume global value otherwise
        except AttributeError:
            return self.global_value

    def __set__(self, obj, value):
        self.validate(obj, value)
        setattr(obj, self.private_name, value)

    def validate(self, obj, value):
        if obj.global_only is True:
            raise RuntimeError("global_only flag is set to True - updating defaults is not allowed.")
        if not isinstance(value, self.allowed_types):
            raise ValueError(f"Expected {value} to be of type {self.allowed_types} - found {type(value)}.")


@dataclass
class AimbatDefaults():
    """
    Class to store and access Aimbat defaults.
    """
    local_defaults_file: str = LOCAL_DEFAULTS_FILE
    global_only: bool = False

    # Populate class with descriptors for each default item
    for key in GLOBAL_DEFAULTS_DICT.keys():
        locals()[key] = AimbatDefaultItem(**GLOBAL_DEFAULTS_DICT[key])

    def __post_init__(self):
        # Read user defined configuration and update variables
        if os.path.isfile(self.local_defaults_file) and self.global_only is False:
            with open(self.local_defaults_file, 'r') as stream:
                for name, value in yaml.safe_load(stream).items():
                    setattr(self, name, value)

    def source(self, key: str) -> str:
        """
        Returns "global" if there is no local value for a key, or if the local value
        is equal to the global value. Returns "local" otherwise.
        """
        if getattr(self, key) == GLOBAL_DEFAULTS_DICT[key]['global_value']:
            return "global"
        else:
            return "local"

    def description(self, key: str) -> str:
        """
        Returns a string that describes the aimbat default.
        """
        descriptor_instance = getattr(type(self), key)
        # Return line 1 of the descriptor docstring.
        return descriptor_instance.__doc__.partition('\n')[0]

    @property
    def simple_dict(self) -> dict:
        """
        Returns a simplified dictionary of Aimbat configuration options (i.e. without description,
        allowed types, etc).
        """
        return {item: getattr(self, item) for item in GLOBAL_DEFAULTS_DICT.keys()}

    def print_yaml(self) -> None:
        """
        Prints yaml with configuration options
        """
        print(yaml.dump(self.simple_dict, default_flow_style=False, explicit_start=True))

    def print_table(self) -> None:
        """
        Prints a pretty table with Aimbat configuration options.
        """
        table = PrettyTable()
        table.field_names = ["Name", "Value", "Source", "Description"]
        for key in GLOBAL_DEFAULTS_DICT.keys():
            table.add_row([key, getattr(self, key), self.source(key), self.description(key)])
        print(table)
