from rest_framework.views import exception_handler
from rest_framework.response import Response
from .constants import ErrorCodes
import logging

logger = logging.getLogger(__name__)


def luna_exception_handler(exc, context):
    # get default response from DRF
    response = exception_handler(exc, context)

    # if DRF returned None, it means it's an unhandled exception (ValueError,
    # KeyError, database errors, etc.)
    if response is None:
        # log the error so it doesn't get lost in production
        logger.error(f"Unhandled API Exception: {exc}", exc_info=True)

        # make the API return JSON even on 500 error
        return Response({
            "status": "error",
            "message": "Internal Server Error",
            "error_code": ErrorCodes.UNKNOWN_ERROR
        }, status=500)

    # if the response is not None, safely extract the data
    data = response.data

    # safely get the message (considering that data may be dict, list or str)
    if isinstance(data, dict):
        message = data.get('detail', 'Error of request')
    elif isinstance(data, list) and len(data) > 0:
        message = str(data[0])
    else:
        message = str(data)

    custom_data = {
        "status": "error",
        "message": message,
        "error_code": ErrorCodes.UNKNOWN_ERROR
    }

    if hasattr(exc, 'code'):
        custom_data['error_code'] = exc.code
    elif response.status_code == 400 and isinstance(data, dict) and 'detail' not in data:
        custom_data['error_code'] = ErrorCodes.VALIDATION_ERROR
        custom_data['message'] = "Error of validation"
        custom_data['fields'] = data
    elif response.status_code == 404 and isinstance(data, dict) and 'detail' not in data:
        custom_data['error_code'] = ErrorCodes.NOT_FOUND
        custom_data['message'] = "'Not Found' error"
        custom_data['fields'] = data

    response.data = custom_data
    return response
