"""Project-specific exceptions."""


class FCPLMError(RuntimeError):
    """Base error for an expected, user-actionable pipeline failure."""


class ConfigurationError(FCPLMError):
    """Configuration is missing or invalid."""


class ValidationError(FCPLMError):
    """An input artifact failed an explicit validation rule."""


class DependencyError(FCPLMError):
    """A required optional dependency or executable is unavailable."""

