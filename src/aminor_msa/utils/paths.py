"""Project location independent of the notebook working directory."""

from pathlib import Path


def find_project_root(start: str | Path | None = None) -> Path:
    """Find the nearest project root above a file or directory.

    :param start: Starting location; defaults to the working directory.
    :type start: str | pathlib.Path | None
    :return: Root containing pyproject.toml and src/aminor_msa.
    :rtype: pathlib.Path
    :raises FileNotFoundError: If no matching ancestor exists.
    """
    location = Path.cwd() if start is None else Path(start).resolve()
    if location.is_file():
        location = location.parent
    for candidate in (location, *location.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src/aminor_msa"
        ).is_dir():
            return candidate
    raise FileNotFoundError(f"No aminor-msa project above {location}")
