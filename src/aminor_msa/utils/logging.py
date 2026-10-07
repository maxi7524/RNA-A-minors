"""Library logging without application-level handler configuration."""

import logging


def get_custom_logger(name: str) -> logging.Logger:
    """Return a logger configured by the calling application.

    :param name: Module logger name.
    :type name: str
    :return: Standard library logger.
    :rtype: logging.Logger
    """
    return logging.getLogger(name)
