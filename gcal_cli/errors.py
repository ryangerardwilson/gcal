class GcalError(Exception):
    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class UsageError(GcalError):
    pass


class ConfigError(GcalError):
    pass


class ApiError(GcalError):
    pass
