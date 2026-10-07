"""Interactive sequence and column selection over an already loaded MSA."""

from __future__ import annotations

from ..config import DEFAULT_STYLE
from .view import view_alignment


class AlignmentBrowser:
    """Sequence selection and MSA window controls over one already loaded MSA.

    :param alignment: Selected parsed Stockholm alignment.
    :type alignment: aminor_msa.io.parsers.stockholm.StockholmAlignment
    :param style: Rendering palette and hard row/column limits.
    :type style: aminor_msa.visualization.config.ViewStyle
    :param start: Initial zero-based alignment column.
    :type start: int
    :raises ValueError: On an empty alignment or invalid window/style limits.
    """

    def __init__(self, alignment, *, style=DEFAULT_STYLE, start=0):
        import ipywidgets as widgets

        if not alignment.sequences or not 0 <= start < alignment.length:
            raise ValueError("Select a nonempty alignment and a valid start column")
        if style.max_columns < 1 or style.max_sequences < 1:
            raise ValueError("Rendering limits must be positive")
        self.alignment = alignment
        self.style = style
        keys = tuple(alignment.sequences)
        self.sequences = widgets.SelectMultiple(
            options=keys,
            value=keys[: min(4, style.max_sequences)],
            description="Sequences:",
            rows=8,
            layout=widgets.Layout(width="600px"),
        )
        self.window = widgets.IntRangeSlider(
            value=(start, min(alignment.length, start + style.max_columns)),
            min=0,
            max=alignment.length,
            step=1,
            description="Columns:",
            continuous_update=False,
            layout=widgets.Layout(width="600px"),
        )
        self.output = widgets.Output()
        self.widget = widgets.VBox([self.sequences, self.window, self.output])
        self.html = None
        self.sequences.observe(self._refresh, names="value")
        self.window.observe(self._refresh, names="value")
        self._refresh()

    def _refresh(self, change=None):
        from IPython.display import display

        with self.output:
            self.output.clear_output(wait=True)
            start, stop = self.window.value
            if (
                len(self.sequences.value) > self.style.max_sequences
                or stop <= start
                or stop - start > self.style.max_columns
            ):
                self.html = None
                display(
                    f"Select 0–{self.style.max_sequences} sequences and 1–{self.style.max_columns} columns."
                )
                return
            self.html = view_alignment(
                self.alignment,
                sequence_ids=self.sequences.value,
                start=start,
                stop=stop,
                style=self.style,
            )
            display(self.html)
