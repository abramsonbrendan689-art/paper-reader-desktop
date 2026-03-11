class ProviderError(Exception):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class ImportErrorDuplicate(Exception):
    pass

