"""Optional bounded parsed-object LRU storage."""

from collections import OrderedDict
from collections.abc import Callable, Iterator
from typing import Any

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)


class ParsedCache:
    """An object-count limit; retained references are not a byte/RSS limit.

    :param limit: Maximum retained parsed objects; zero disables storage.
    :type limit: int
    :raises ValueError: On a negative limit.
    """

    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("cache limit must be nonnegative")
        self.limit = limit
        self._values = OrderedDict()

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator:
        return iter(self._values)

    def clear(self) -> None:
        """Release cache-owned references.

        :rtype: None
        """
        self._values.clear()

    def load(self, kind: str, key: str, reader: Callable[[], Any]) -> Any:
        """Return or read a keyed source; failed reads never enter the cache.

        :param kind: Artifact representation kind.
        :type kind: str
        :param key: Source identifier.
        :type key: str
        :param reader: Function reading one source object.
        :type reader: collections.abc.Callable
        :return: Parsed object, reused only when caching is enabled.
        :rtype: typing.Any
        """
        cache_key = (kind, key)
        if cache_key in self._values:
            self._values.move_to_end(cache_key)
            logger.debug("Parsed source cache hit: %s", cache_key)
            return self._values[cache_key]
        value = reader()
        if self.limit:
            self._values[cache_key] = value
            while len(self._values) > self.limit:
                self._values.popitem(last=False)
        return value
