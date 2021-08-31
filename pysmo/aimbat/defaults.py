#!/usr/bin/env python

import os
import yaml
import click
import pysmo.aimbat
from dataclasses import dataclass, field
from typing import Any
from prettytable import PrettyTable

# Default name of the local overrides in the working directory.
_LOCAL_DEFAULTS_FILE = 'aimbat.yml'
# Defaults shipped with Aimbat
_GLOBAL_DEFAULTS_FILE = os.path.join(os.path.dirname(pysmo.aimbat.__file__), 'defaults.yml')


@dataclass(frozen=True)
class AimbatDefaultItem:
    local_value: Any
    global_value: Any
    allowed_types: list[Any]
    description: str

    @property
    def value(self):
        if self.local_value is None:
            return self.global_value
        return self.local_value

    @property
    def source(self) -> str:
        if self.local_value is None:
            return "global"
        return "local"


@dataclass
class AimbatDefaults:
    """
    Class to store and access Aimbat defaults.
    """
    global_defaults_file: str = _GLOBAL_DEFAULTS_FILE
    local_defaults_file: str = _LOCAL_DEFAULTS_FILE
    global_only: bool = False
    items: list[str] = field(default_factory=list)

    def __post_init__(self):
        with open(self.global_defaults_file, 'r') as stream:
            defaults_dict = yaml.safe_load(stream)
            for name in defaults_dict:
                # rename the the 'value' key to 'global_value'
                defaults_dict[name]['global_value'] = defaults_dict[name].pop('value')
                defaults_dict[name]['local_value'] = None
                defaults_dict[name]['allowed_types'] = tuple(eval(a) for a in defaults_dict[name]['allowed_types'])
        if os.path.isfile(self.local_defaults_file) and self.global_only is False:
            with open(self.local_defaults_file, 'r') as stream:
                local_defaults_dict = yaml.safe_load(stream)
                for name, value in local_defaults_dict.items():
                    # Only allow keys that already exist in the global defaults file.
                    if name not in defaults_dict.keys():
                        raise AimbatConfigError(name=name, value=value, local_default_file=self.local_default_file,
                                                message=f"{name} is not a valid Aimbat configuration key.")
                    # Check for correct type (as defined in the global defaults file)
                    allowed_types = defaults_dict[name]['allowed_types']
                    if not isinstance(value, allowed_types):
                        raise AimbatConfigError(name=name, value=value, local_default_file=self.local_default_file,
                                                message=(f"{name} is of type {type(value)}, but needs to be of "
                                                         f"type {allowed_types}"))
                    defaults_dict[name]['local_value'] = value
        for name, pars in defaults_dict.items():
            setattr(self, name, AimbatDefaultItem(**pars))
            self.items.append(name)

    @property
    def simple_dict(self) -> dict:
        """
        Returns a simplified dictionary of Aimbat configuration options (i.e. without description,
        allowed types, etc).
        """
        return {item: getattr(self, item).value for item in self.items}

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
        for item in self.items:
            table.add_row([item,
                           getattr(self, item).value,
                           getattr(self, item).source,
                           getattr(self, item).description,
                           ])
        print(table)


@dataclass
class AimbatConfigError(Exception):
    """
    Custom error that is raised when there are incorrect entries Aimbat configuration files.
    """
    name: str
    value: Any
    message: str
    local_default_file: str

    def __post_init__(self):
        self.message += f" Please check your {self.local_default_file} for errors."
        super().__init__(self.message)


@click.command('defaults')
@click.option('-f', '--file', 'local_defaults_file', default=_LOCAL_DEFAULTS_FILE, show_default=True,
              help="Name of optional local configuration file to override builtin defaults (must be in yaml format).")
@click.option('-g', '--global', 'global_only', is_flag=True,
              help="Ignore local configuration file and only show global defaults.")
@click.option('-y', '--yaml', 'print_yaml', is_flag=True,
              help="Output yaml instead of a table (to help with the creation of a local configuration file).")
def cli(local_defaults_file, global_only, print_yaml):
    """
    Lists default values for options that controll Aimbat behaviour.
    """
    defaults = AimbatDefaults(local_defaults_file=local_defaults_file, global_only=global_only)
    if print_yaml:
        defaults.print_yaml()
    else:
        defaults.print_table()


if __name__ == "__main__":
    cli()
