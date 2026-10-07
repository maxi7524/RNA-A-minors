"""Interactive participant, RNA type and family selection."""

from __future__ import annotations

from .tables import families_table, mappings_table, participants_table, structures_table


class FamilyBrowser:
    """Participant/type/family controls; never load coordinates or report bodies.

    :param store: Source store; only small catalogues are read by this widget.
    :type store: aminor_msa.DataStore
    :param participant: Initial exact participant identifier, or None for all.
    :type participant: str | None
    :param accession: Initial family, when present in the selected subset.
    :type accession: str | None
    :raises ValueError: If the initial participant is unknown.
    """

    def __init__(self, store, *, participant=None, accession=None):
        import ipywidgets as widgets

        self.store = store
        ids = participants_table(store)["participant_id"].tolist()
        if participant is not None and participant not in ids:
            raise ValueError(f"Unknown participant: {participant}")
        types = sorted(
            {
                token.strip()
                for row in store.family_records()
                for token in row.get("rna_type", "").split(";")
                if token.strip()
            }
        )
        self.participant = widgets.Dropdown(
            options=[("All participants", None), *((key, key) for key in ids)],
            value=participant,
            description="Participant:",
            layout=widgets.Layout(width="500px"),
        )
        self.rna_type = widgets.Dropdown(
            options=[("All RNA types", None), *((key, key) for key in types)],
            description="RNA type:",
        )
        self.family = widgets.Dropdown(
            options=[], description="Family:", layout=widgets.Layout(width="500px")
        )
        self.output = widgets.Output()
        self.widget = widgets.VBox(
            [self.participant, self.rna_type, self.family, self.output]
        )
        self.tables = {}
        self._updating = False
        self._refresh_selection(preferred=accession)
        self.participant.observe(self._selection_changed, names="value")
        self.rna_type.observe(self._selection_changed, names="value")
        self.family.observe(self._family_changed, names="value")

    @property
    def selected_family(self):
        """Return the selected lazy family handle, or None for an empty subset.

        :rtype: aminor_msa.io.sources.family.FamilySource | None
        """
        return (
            None if self.family.value is None else self.store.family(self.family.value)
        )

    def _selection_changed(self, change):
        self._refresh_selection()

    def _refresh_selection(self, preferred=None):
        self._updating = True
        try:
            table = families_table(
                self.store,
                participant=self.participant.value,
                rna_type=self.rna_type.value,
            )
            self.tables = {"families": table}
            options = [
                (f"{row['rfam_acc']} · {row.get('family_name', '')}", row["rfam_acc"])
                for row in table.to_dict("records")
            ]
            self.family.options = options
            keys = [value for _, value in options]
            self.family.value = (
                preferred if preferred in keys else keys[0] if keys else None
            )
        finally:
            self._updating = False
        self._family_changed()

    def _family_changed(self, change=None):
        from IPython.display import display

        if self._updating:
            return
        source = self.selected_family
        self.tables = {"families": self.tables["families"]}
        if source is not None:
            self.tables.update(
                mappings=mappings_table(source), structures=structures_table(source)
            )
        with self.output:
            self.output.clear_output(wait=True)
            for name, table in self.tables.items():
                display({"table": name, "rows": len(table)})
                display(table)
