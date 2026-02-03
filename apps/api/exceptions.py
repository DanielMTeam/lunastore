from rest_framework.exceptions import APIException
from rest_framework import status

class LunaException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A logic error occurred in LunaStore'
    default_code = '1'

    def __init__(self, code: int, message: str, status_code=status.HTTP_400_BAD_REQUEST):
        self.status_code = status_code
        self.code = code  
        self.detail = message  
        super().__init__(message)