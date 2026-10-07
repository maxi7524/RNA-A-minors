"""Shared defaults for bounded notebook views."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ViewStyle:
    """Display settings; limits bound rendering, not parser memory.

    :param max_sequences: Maximum MSA rows rendered at once.
    :param max_columns: Maximum MSA columns rendered at once.
    :param font_size: Monospace alignment font size in pixels.
    :param width: Coordinate viewer width in pixels.
    :param height: Coordinate viewer height in pixels.
    :param donor_color: Motif donor marker color.
    :param pair_color: Motif pair marker color.
    :param bases: Base colors used in alignment views.
    """

    max_sequences: int = 12
    max_columns: int = 100
    font_size: int = 13
    width: int = 800
    height: int = 500
    donor_color: str = "#D55E00"
    pair_color: str = "#0072B2"
    bases: dict[str, str] = field(
        default_factory=lambda: {
            "A": "#F0E442",
            "C": "#56B4E9",
            "G": "#E69F00",
            "U": "#009E73",
            "T": "#009E73",
            "-": "#EEEEEE",
            ".": "#EEEEEE",
        }
    )


DEFAULT_STYLE = ViewStyle()
