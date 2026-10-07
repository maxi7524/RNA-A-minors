"""Bounded HTML alignment views with preserved column annotations."""

from __future__ import annotations

from html import escape

from aminor_msa.io.parsers.stockholm import StockholmAlignment

from ..config import DEFAULT_STYLE, ViewStyle


def view_alignment(
    alignment: StockholmAlignment,
    *,
    sequence_ids=None,
    start=0,
    stop=None,
    style: ViewStyle = DEFAULT_STYLE,
):
    """Render an explicit MSA window with GC annotations and base colors.

    Slices use Python zero-based half-open MSA columns, including gaps.
    This view does not infer consensus pairs or a structure-to-MSA mapping.

    :param alignment: Parsed selected MSA.
    :type alignment: StockholmAlignment
    :param sequence_ids: Selected identifiers; defaults to the first bounded rows.
    :type sequence_ids: collections.abc.Iterable[str] | None
    :param start: First alignment column, inclusive.
    :type start: int
    :param stop: Last alignment column, exclusive; default is a bounded window.
    :type stop: int | None
    :param style: Shared palette and rendering limits.
    :type style: ViewStyle
    :return: Rich HTML suitable for display().
    :rtype: IPython.display.HTML
    :raises ValueError: On an invalid window or rendering limits exceeded.
    :raises KeyError: On an unknown sequence identifier.
    """
    from IPython.display import HTML

    if style.max_sequences < 1 or style.max_columns < 1 or style.font_size <= 0:
        raise ValueError("Rendering limits and font size must be positive")
    stop = min(alignment.length, start + style.max_columns) if stop is None else stop
    if not 0 <= start < stop <= alignment.length or stop - start > style.max_columns:
        raise ValueError("Select a nonempty MSA window within max_columns")
    keys = (
        list(alignment.sequences)[: style.max_sequences]
        if sequence_ids is None
        else list(sequence_ids)
    )
    if len(keys) > style.max_sequences:
        raise ValueError("Too many sequences for the rendering limit")
    lines = []
    for key in keys:
        sequence = alignment.sequences[key][start:stop]
        bases = "".join(
            f'<span style="background:{escape(style.bases.get(base.upper(), "#FFFFFF"), quote=True)}">{escape(base)}</span>'
            for base in sequence
        )
        lines.append(
            f'<tr><th style="text-align:left;padding-right:12px">{escape(key)}</th><td>{bases}</td></tr>'
        )
    for tag, annotation in alignment.column_annotations.items():
        lines.append(
            f'<tr><th style="text-align:left;padding-right:12px">#=GC {escape(tag)}</th><td>{escape(annotation[start:stop])}</td></tr>'
        )
    content = (
        f'<div style="overflow-x:auto;font-family:monospace;font-size:{style.font_size}px"><p>MSA columns [{start}, {stop}); {len(keys)} / {len(alignment.sequences)} sequences</p><table style="white-space:pre">'
        + "".join(lines)
        + "</table></div>"
    )
    return HTML(content)
