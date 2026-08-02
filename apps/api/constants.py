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

    # Auth & API constants (4xxx like)
    TWO_FACTOR_REQUIRED = 4000
    TWO_FACTOR_INVALID = 4001
    METHOD_NOT_FOUND = 4005

    # Collection ErrorCode constants (5xxx like)
    COLLECTION_NOT_FOUND = 5000
    COLLECTION_PRIVATE = 5001


PUB_UPLOAD_POLICIES = {
    "avatar": {
        "mw": 512,
        "mh": 512,
        "mimes": "image/jpeg;image/png;image/webp",
        "obj": "avatar",
    },
    "icon": {
        "mw": 512,
        "mh": 512,
        "mimes": "image/jpeg;image/png;image/webp",
        "obj": "icon",
    },
    "screenshot": {
        "mw": 1920,
        "mh": 1080,
        "mimes": "image/jpeg;image/png;image/webp",
        "obj": "screenshot",
    },
}

ALLOWED_MIMES_LIST = [
    # universal binary stream (fallback)
    "application/octet-stream",

    # .exe (Windows Executables)
    "application/x-msdownload",
    "application/exe",
    "application/x-exe",
    "application/dos-exe",
    "application/x-winexe",
    "application/msdos-windows",
    "application/x-msdos-program",

    # .msi (Windows Installer)
    "application/x-msi",
    "application/x-ms-installer",
    "application/x-windows-installer",
    "application/x-ole-storage",

    # .zip (ZIP Archives)
    "application/zip",
    "application/x-zip-compressed",
    "application/x-zip",
    "multipart/x-zip",

    # .rar (RAR Archives)
    "application/vnd.rar",
    "application/x-rar-compressed",
    "application/x-rar",
    "application/rar",

    # .7z (7-Zip Archives)
    "application/x-7z-compressed",
    "application/7z",
]

ALLOWED_MIMES = ";".join(ALLOWED_MIMES_LIST)
