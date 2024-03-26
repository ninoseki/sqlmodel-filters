class SQLModelFiltersError(Exception):
    pass


class IllegalFieldError(SQLModelFiltersError):
    pass


class IllegalFilterError(SQLModelFiltersError):
    pass
