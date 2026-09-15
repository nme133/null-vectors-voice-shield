from __future__ import annotations

import logging
import sys


class _TagAdapter(logging.LoggerAdapter):
    """Injectable per-module tag for structured logs."""

    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).setdefault("tag", self.extra["tag"])
        return msg, kwargs


def _build_base_logger() -> logging.Logger:
    logger = logging.getLogger("voiceshield")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            fmt="[%(asctime)s] %(tag)-14s %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


_base = _build_base_logger()


def get_logger(tag: str) -> _TagAdapter:
    return _TagAdapter(_base, {"tag": tag})