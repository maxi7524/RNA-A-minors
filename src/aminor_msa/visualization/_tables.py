"""Optional table construction shared by domain views."""

from __future__ import annotations


def _frame(rows, columns=None):
    """Construct an optional pandas table with stable column order.

    :param rows: Small row records already prepared by a domain table function.
    :type rows: collections.abc.Iterable
    :param columns: Explicit output schema, including empty tables.
    :type columns: list[str] | None
    :return: Table of the supplied rows.
    :rtype: pandas.DataFrame
    """
    import pandas as pd

    return pd.DataFrame(rows, columns=columns)
