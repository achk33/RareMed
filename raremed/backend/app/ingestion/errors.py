"""Ingestion failures that must be reported clearly."""


class MissingRequiredSourcesError(RuntimeError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        names = ", ".join(missing) if missing else "(none)"
        super().__init__(f"Required source files are absent: {names}")


class IngestionConflictError(RuntimeError):
    pass
