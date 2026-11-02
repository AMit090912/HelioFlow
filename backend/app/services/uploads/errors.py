class UploadError(Exception):
    """A file we refuse to store. `code` is translated by the frontend; `status` is HTTP."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
