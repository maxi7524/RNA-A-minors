"""Repository-local default locations."""

from pathlib import Path

from aminor_msa.utils.paths import find_project_root

ROOT = find_project_root(Path(__file__))
