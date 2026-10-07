"""Shared TOML configuration loading."""

from pathlib import Path

import tomllib


def read_toml(path: str | Path) -> dict:
    """Read a TOML document without modifying it.

    :param path: Configuration path.
    :type path: str | pathlib.Path
    :return: Parsed configuration.
    :rtype: dict
    :raises OSError: If the file cannot be read.
    :raises tomllib.TOMLDecodeError: If its syntax is invalid.
    """
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)
