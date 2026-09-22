import unittest

from fastapi.testclient import TestClient

from nurion_pg.api.app import create_app
from nurion_pg.api.settings import Settings


class GuestUiTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(create_app(Settings(environment="test")))

    def test_guest_home_is_public_synthetic_and_read_only(self):
        response=self.client.get("/guest")
        self.assertEqual(response.status_code,200)
        self.assertIn("게스트 분석 모드",response.text)
        self.assertIn("합성 데이터",response.text)
        self.assertIn("disabled",response.text)
        self.assertNotIn("paymentKey",response.text)
        self.assertEqual(response.headers["cache-control"],"no-store")

    def test_root_routes_to_guest_preview_without_authentication(self):
        response=self.client.get("/")
        self.assertEqual(response.status_code,200)
        self.assertIn("NURION PG",response.text)

    def test_detail_is_static_demo_and_never_calls_operations_repository(self):
        class ExplodingRepository:
            def __getattr__(self,_name):
                raise AssertionError("guest UI must not access an operations repository")
        client=TestClient(create_app(Settings(environment="test"),operations_repository=ExplodingRepository()))
        response=client.get("/guest/payments/demo-pay-001")
        self.assertEqual(response.status_code,200)
        self.assertIn("합성 결제 상세",response.text)
        self.assertIn("변경 작업은 사용할 수 없습니다",response.text)
        self.assertNotIn("Webhook 원문",response.text)
        self.assertEqual(client.get("/guest/payments/not-a-demo").status_code,404)

    def test_guest_javascript_has_no_production_api_fetch_or_write_method(self):
        script=self.client.get("/guest/assets/app.js")
        self.assertEqual(script.status_code,200)
        self.assertNotIn("fetch(",script.text)
        self.assertNotIn("/v1/merchants",script.text)
        for method in ('method:"POST"','method:"PUT"','method:"PATCH"','method:"DELETE"'):
            self.assertNotIn(method,script.text)

    def test_accessibility_and_responsive_contracts(self):
        home=self.client.get("/guest").text
        css=self.client.get("/guest/assets/styles.css").text
        self.assertIn("본문으로 바로가기",home)
        self.assertIn('aria-label="주요 메뉴"',home)
        self.assertIn("prefers-reduced-motion",css)
        self.assertIn("focus-visible",css)
        self.assertIn("@media(max-width:760px)",css)

    def test_production_guest_preview_is_disabled_by_default(self):
        client=TestClient(create_app(Settings(environment="production",guest_preview_enabled=False)))
        self.assertEqual(client.get("/guest").status_code,404)
        self.assertEqual(client.get("/guest/assets/app.js").status_code,404)


if __name__=="__main__":unittest.main()
