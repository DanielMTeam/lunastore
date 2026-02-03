from rest_framework.views import exception_handler
from .constants import ErrorCodes

def luna_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        custom_data = {
            "status": "error",
            "message": response.data.get('detail', 'Error of request'),
            "error_code": ErrorCodes.UNKNOWN_ERROR 
        }
        if hasattr(exc, 'code'):
            custom_data['error_code'] = exc.code
        elif response.status_code == 400 and 'detail' not in response.data:
            custom_data['error_code'] = ErrorCodes.VALIDATION_ERROR
            custom_data['message'] = "Error of validation"
            custom_data['fields'] = response.data
        elif response.status_code == 404 and 'detail' not in response.data:
            custom_data['error_code'] = ErrorCodes.NOT_FOUND
            custom_data['message'] = "'Not Found' error"
            custom_data['fields'] = response.data
        response.data = custom_data
    return response