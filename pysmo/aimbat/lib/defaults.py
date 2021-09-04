#!/usr/bin/env python

import os
import yaml
import pysmo.aimbat
from dataclasses import dataclass
from prettytable import PrettyTable


# Default name of the local overrides in the working directory.
_LOCAL_DEFAULTS_FILE = 'aimbat.yml'
# Defaults shipped with Aimbat
_GLOBAL_DEFAULTS_FILE = os.path.join(os.path.dirname(pysmo.aimbat.__file__), 'lib/defaults.yml')

with open(_GLOBAL_DEFAULTS_FILE, 'r') as stream:
    _GLOBAL_DEFAULTS_DICT = yaml.safe_load(stream)
    for name in _GLOBAL_DEFAULTS_DICT:
        # Rename the the 'value' key to 'global_value'
        _GLOBAL_DEFAULTS_DICT[name]['global_value'] = _GLOBAL_DEFAULTS_DICT[name].pop('value')
        # get the actual types from the str expressions.
        _GLOBAL_DEFAULTS_DICT[name]['allowed_types'] = tuple(eval(item) for item in
                                                             _GLOBAL_DEFAULTS_DICT[name]['allowed_types'])


class AimbatDefaultItem():
    def __set_name__(self, owner, name):
        self.private_name = '_' + name

    def __init__(self, global_value, allowed_types, description):
        self.global_value = global_value
        self.allowed_types = allowed_types

    def __get__(self, obj, objtype=None):
        try:
            return getattr(obj, self.private_name)
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
    global_defaults_file: str = _GLOBAL_DEFAULTS_FILE
    local_defaults_file: str = _LOCAL_DEFAULTS_FILE
    global_only: bool = False
    _keys = _GLOBAL_DEFAULTS_DICT.keys()
    # Pupulate class with descriptors for each default item
    for key in _keys:
        locals()[key] = AimbatDefaultItem(**_GLOBAL_DEFAULTS_DICT[key])

    def __post_init__(self):
        # Read user defined configuration and update variables
        if os.path.isfile(self.local_defaults_file) and self.global_only is False:
            with open(self.local_defaults_file, 'r') as stream:
                for name, value in yaml.safe_load(stream).items():
                    setattr(self, name, value)

    @property
    def simple_dict(self) -> dict:
        """
        Returns a simplified dictionary of Aimbat configuration options (i.e. without description,
        allowed types, etc).
        """
        return {item: getattr(self, item) for item in self._keys}

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
        for item in self._keys:
            if getattr(self, item) == _GLOBAL_DEFAULTS_DICT[item]['global_value']:
                source = "global"
            else:
                source = "local"
            table.add_row([item, getattr(self, item), source, _GLOBAL_DEFAULTS_DICT[item]['description']])
        print(table)
