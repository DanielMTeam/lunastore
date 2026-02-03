# <center>LunaStore API Documentation</center>

The LunaStore API is a RESTful API designed for interacting with a LunaStore instance. JSON is used for all requests and responses (`Content-Type: application/json`).

**Base URL:**
All API requests should be made to the domain `api.store.myslivets.com`.
Please note that all API endpoints are prefixed with `/method/`.

For a full description of the API methods and how to interact with them, please refer to the Swagger UI, accessible at `api.store.myslivets.com`. Regarding Docker deployment, the LunaStore API container is exposed on port `7088`.

### Error Handling

In addition to standard HTTP status codes, the LunaStore API utilizes its own custom error numbering system:

| Range | Description |
| --- | --- |
| 0xxx | General type errors |
| 1xxx | User model errors |
| 2xxx | Application model errors |
| 3xxx | Category model errors |

Below is the complete list of errors you may encounter, mapped to their standard HTTP status codes:

| Number | Error Code | Description |
| --- | --- | --- |
| 0 | EVERYTHING_IS_ALRIGHT | Operation completed successfully. |
| 1 | UNKNOWN_ERROR | Unknown error. Indicates a server-side backend issue. |
| 2 | VALIDATION_ERROR | Validation error. Occurs when a required field is missing or invalid. |
| 3 | NOT_FOUND | Resource not found. |
| 1000 | USER_NOT_FOUND | The specified user does not exist. |
| 1001 | USER_IS_BLOCKED | The specified user is blocked. |
| 2000 | APPLICATION_NOT_FOUND | The specified application does not exist. |
| 2001 | APPLICATION_IS_UNDER_DMCA | The application is unavailable due to a DMCA takedown. |
| 3000 | CATEGORY_NOT_FOUND | The specified category was not found. |

### Example Request

Let's send a test request to the LunaStore API using the `/service/heartbeat` endpoint:

```bash
curl -X 'GET' \
  'https://api.store.myslivets.com/method/service/heartbeat/' \
  -H 'accept: application/json'
```

Response:

```json
{
  "status": "ok",
  "timestamp": "2026-02-03T07:33:25.768663",
  "version": "1.1.0"
}
```

For further details on API methods, please visit the SwaggerUI: `api.store.myslivets.com`