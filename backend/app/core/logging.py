"""Logging setup.

Modules log through ``logging.getLogger(__name__)``, so every application logger lives
under the ``app`` namespace configured here. Never log passwords, JWTs, card data, or
``OPENAI_API_KEY`` (design: Error Handling).
"""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
APP_LOGGER_NAME = "app"


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure console logging for the application (idempotent).

    Application loggers (``app.*``) log at ``level``; third-party libraries stay at
    WARNING so HTTP client libraries do not add request noise. ``basicConfig`` only
    installs a root handler when none exists, so repeated calls and test runners
    (pytest's ``caplog``) are left untouched.
    """
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)
    logging.getLogger(APP_LOGGER_NAME).setLevel(level)
