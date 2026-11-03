"""Keep secrets that live in URLs out of logs (§14: logs carry ids only).

Public status links put the token in the path (/api/public/status/<token>, /<locale>/s/<token>).
Access logs would otherwise become a second store of live links.
"""

import logging
import re

_SECRET_PATH = re.compile(r"(/(?:api/public/status|[a-z]{2}/s)/)[^/?\s\"']+")


def redact(text: str) -> str:
    return _SECRET_PATH.sub(r"\1****", text)  # ASCII: log files may not be UTF-8


class RedactSecretPaths(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def install() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "app"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretPaths) for f in logger.filters):
            logger.addFilter(RedactSecretPaths())
