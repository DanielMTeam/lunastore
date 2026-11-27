from django.test import SimpleTestCase, override_settings
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from jsonschema import validate

from apps.api.v3.batch import BATCH_OPERATIONS
from apps.api.v3.openapi_urls import urlpatterns


@override_settings(ROOT_URLCONF="lunastore.urls_api")
class V3SchemaContractTests(SimpleTestCase):
    def test_versioned_schema_and_batch_operations(self):
        schema = SchemaGenerator(patterns=urlpatterns).get_schema(public=True)
        validate_schema(schema)
        self.assertTrue(all(path.startswith("/v3/") for path in schema["paths"]))
        operations = {
            operation["operationId"]: operation
            for methods in schema["paths"].values()
            for operation in methods.values()
        }
        self.assertTrue(BATCH_OPERATIONS.keys() <= operations.keys())
        components = schema["components"]["schemas"]
        self.assertTrue({"icon_url", "banner_url"} <= components["V3Category"]["properties"].keys())
        self.assertEqual(
            components["V3Application"]["properties"]["categories"]["items"]["$ref"],
            "#/components/schemas/V3Category",
        )
        self.assertIn("is_developer", components["V3Me"]["properties"])
        self.assertIn("unread_count", components["NotificationPage"]["properties"])

        for url, status, media in (
            ("/v3/health/", 200, "application/json"),
            ("/v3/apps/?limit=101", 400, "application/problem+json"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                definition = schema["paths"][url.split("?")[0]]["get"]["responses"][str(status)]
                self.assertEqual(response.status_code, status)
                self.assertEqual(response["Content-Type"], media)
                validate(response.json(), {
                    **definition["content"][media]["schema"],
                    "components": schema["components"],
                })

    def test_v2_nested_app_lists_document_the_actual_response(self):
        from lunastore.urls_api import v2_patterns

        schema = SchemaGenerator(patterns=v2_patterns).get_schema(public=True)
        validate_schema(schema)
        components = schema["components"]["schemas"]
        self.assertIn("jwtAuth", schema["components"]["securitySchemes"])
        for url in ("/v2/category/{id}/apps/", "/v2/collection/{id}/apps/"):
            with self.subTest(url=url):
                payload = schema["paths"][url]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
                page = components[payload["$ref"].rsplit("/", 1)[-1]]
                entry = page["properties"]["results"]["items"]["$ref"].rsplit("/", 1)[-1]
                self.assertIn("title", components[entry]["properties"])
