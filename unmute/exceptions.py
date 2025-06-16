import unmute.openai_realtime_api_events as ora


class MissingServiceAtCapacity(Exception):
    """A service is operating at capacity, but no serious error."""

    def __init__(self, service: str):
        self.service = service
        super().__init__(f"{service} is not available.")


class MissingServiceTimeout(Exception):
    """A service timed out."""

    def __init__(self, service: str):
        self.service = service
        super().__init__(f"{service} timed out.")


class WebSocketClosedError(Exception):
    """Remote web socket is closed, let's move on."""


def make_ora_error(type: str, message: str) -> ora.Error:
    details = ora.ErrorDetails(type=type, message=message)
    return ora.Error(error=details)
