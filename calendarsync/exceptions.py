class CalendarSynchronizerError(Exception):
    """Base class for all errors of this module."""
    pass


class SourceRetrievalError(CalendarSynchronizerError):
    """Raised when the retrieval of events from the source calendar failed."""
    pass


class InvalidCredentialsError(SourceRetrievalError):
    """Raised when the retrieval of the source failed because of invalid credentials."""
    pass


class UploadCalendarError(CalendarSynchronizerError):
    """Base class for all errors of the upload calendar."""
    pass


class CalendarConnectionError(UploadCalendarError):
    """Raised when the connection to the upload calendar failed."""
    pass


class EventRetrievalError(UploadCalendarError):
    """Raised when the retrieval of existing events of the upload calendar failed."""
    pass


class EventDeletionError(UploadCalendarError):
    """Raised when the removing of an event failed."""
    pass


class EventUploadError(UploadCalendarError):
    """Raised when the adding of an event to the upload calendar failed."""
    pass
