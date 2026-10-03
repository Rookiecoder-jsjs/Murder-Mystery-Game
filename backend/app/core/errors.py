"""Transport-independent failures raised by the shared game runtime."""


class GameError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ModelInterrupted(Exception):
    """A mobile call cannot safely continue; never turn it into a paid retry."""
