class ErrorCodes:
    # Main ErrorCode constants (0xxx like)
    EVERYTHING_IS_ALRIGHT = 0
    UNKNOWN_ERROR = 1
    VALIDATION_ERROR = 2
    NOT_FOUND = 3

    # User ErrorCode constants (1xxx like)
    USER_NOT_FOUND = 1000
    USER_IS_BLOCKED = 1001

    # Application ErrorCode constants (2xxx like)
    APPLICATION_NOT_FOUND = 2000
    APPLICATION_IS_UNDER_DMCA = 2001
    APPLICATION_PRIVATE = 2002

    # Category ErrorCode constants (3xxx like)
    CATEGORY_NOT_FOUND = 3000
