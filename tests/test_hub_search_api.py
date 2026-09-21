from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.apis.hub_api import build_router
from src.common.schemas.api import APIResponse
from src.services.hub_service import HubGatewayService


class FakeHubService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def search(self, **kwargs) -> APIResponse:
        self.calls.append(kwargs)
        return APIResponse(status=200, message="Success", data=[{"key": "1"}])


class HubSearchAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeHubService()
        app = FastAPI()
        app.include_router(build_router(self.service))
        self.client = TestClient(app)

    def test_text_search_dispatches_to_unified_service(self) -> None:
        response = self.client.post(
            "/hub/search",
            data={
                "model": "siglip_alpha",
                "search_type": "text",
                "text": "a red car",
                "k": "10",
                "frame_class_filter": "[1, 4]",
                "skip_frames": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [{"key": "1"}])
        self.assertEqual(self.service.calls[0]["model"], "siglip_alpha")
        self.assertEqual(self.service.calls[0]["search_type"], "text")
        self.assertEqual(self.service.calls[0]["frame_class_filter"], [1, 4])

    def test_all_search_types_reach_dispatcher(self) -> None:
        cases = {
            "image": {"image_path": "data:image/png;base64,AA=="},
            "temporal": {"text": "enter. sit.", "main_event_index": "1"},
            "scroll": {"video_filter": "L28_V009", "utility_feature": "shot"},
        }
        for search_type, extra in cases.items():
            with self.subTest(search_type=search_type):
                response = self.client.post(
                    "/hub/search",
                    data={
                        "model": "siglip_alpha",
                        "search_type": search_type,
                        **extra,
                    },
                )
                self.assertEqual(response.status_code, 200)

    def test_conditional_required_field_returns_400(self) -> None:
        response = self.client.post(
            "/hub/search",
            data={"model": "siglip_alpha", "search_type": "image"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("image_path is required", response.json()["detail"])

    def test_json_list_fields_reject_non_lists(self) -> None:
        response = self.client.post(
            "/hub/search",
            data={
                "model": "siglip_alpha",
                "search_type": "text",
                "text": "query",
                "frame_class_filter": "{}",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("must be a JSON list", response.json()["detail"])


class RetrievalRegistryTest(unittest.TestCase):
    def test_configured_registry_overrides_fallback_and_adds_models(self) -> None:
        service = HubGatewayService.__new__(HubGatewayService)
        service._settings = SimpleNamespace(
            siglip_v2_host_public="http://alpha:9029",
            siglip_v2_b_host_public="http://beta:9030",
            metaclip_host_public="http://meta:9031",
            retrieval_model_registry={
                "siglip_alpha": "http://override/alpha/",
                "custom": "http://custom/retrieval",
            },
        )

        self.assertEqual(service._model_base_url("siglip_alpha"), "http://override/alpha")
        self.assertEqual(service._model_base_url("custom"), "http://custom/retrieval")
        self.assertEqual(
            service._model_base_url("siglip_beta"),
            "http://beta:9030/siglip_beta",
        )


if __name__ == "__main__":
    unittest.main()
