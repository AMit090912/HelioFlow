class CalcError(Exception):
    """A calculation that cannot honestly produce a number. `code` is API-ready (§2 Languages)."""

    def __init__(self, code: str, message: str, **context: object):
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context
