"""End-to-end API tests: real HTTP routes, real Postgres, Celery tasks run inline."""

import http.server
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

HEADER = "sku,name,description,price,active\n"


def upload(client, csv_text: str) -> dict:
    """Upload a CSV and return its final status (the import runs inline in tests)."""
    r = client.post("/upload/start", files={"file": ("products.csv", csv_text.encode(), "text/csv")})
    assert r.status_code == 202, r.text
    return client.get(f"/upload/status/{r.json()['task_id']}").json()


def list_products(client, **params) -> dict:
    return client.get("/products", params={"limit": 100, **params}).json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- CSV import --------------------------------------------------------------


def test_import_keeps_last_duplicate_and_reports_progress(client):
    status = upload(client, HEADER + "A1,v1,,10,true\nA1,v2,,20,true\nB1,b,,5,false\n")

    assert status["status"]["status"] == "COMPLETED"
    assert status["progress"] == {
        "processed_rows": "3", "total_rows": "3", "successful_rows": "3", "failed_rows": "0",
    }
    products = {p["sku"]: p for p in list_products(client)["items"]}
    assert products["A1"]["name"] == "v2" and products["A1"]["price"] == 20
    assert products["B1"]["active"] is False


def test_sku_is_case_insensitive_across_uploads(client):
    upload(client, HEADER + "Case-1,first,,1,true\n")
    upload(client, HEADER + "CASE-1,second,,2,true\n")

    items = list_products(client)["items"]
    assert len(items) == 1
    assert items[0]["name"] == "second"


def test_minimal_three_column_csv_without_trailing_newline(client):
    status = upload(client, "sku,name,description\nM1,Minimal,\nM2,Minimal 2,has a description")

    assert status["progress"]["total_rows"] == "2"
    assert status["progress"]["failed_rows"] == "0"
    assert list_products(client)["total"] == 2


def test_invalid_rows_are_counted_not_silently_dropped(client):
    status = upload(client, HEADER + ",no sku,,1,true\nX1,,,1,true\nX2,bad price,,abc,true\nOK1,good,,1,true\n")

    assert status["progress"]["successful_rows"] == "1"
    assert status["progress"]["failed_rows"] == "3"
    assert [p["sku"] for p in list_products(client)["items"]] == ["OK1"]


def test_uploaded_file_is_deleted_after_import(client):
    upload(client, HEADER + "F1,file,,1,true\n")
    assert list(Path(os.environ["UPLOAD_DIR"]).iterdir()) == []


# --- Products API ---------------------------------------------------------------


def test_create_update_delete_and_conflicts(client):
    r = client.post("/products", json={"sku": "P1", "name": "One", "price": 9.5})
    assert r.status_code == 201
    pid = r.json()["id"]

    assert client.post("/products", json={"sku": "p1", "name": "dup"}).status_code == 409
    assert client.post("/products", json={"sku": "  ", "name": "blank"}).status_code == 422

    r = client.put(f"/products/{pid}", json={"name": "One v2", "active": False})
    assert r.status_code == 200
    assert r.json()["name"] == "One v2" and r.json()["active"] is False

    other = client.post("/products", json={"sku": "P2", "name": "Two"}).json()["id"]
    assert client.put(f"/products/{other}", json={"sku": "P1"}).status_code == 409

    assert client.delete(f"/products/{pid}").status_code == 204
    assert client.delete(f"/products/{pid}").status_code == 404


def test_filters_and_pagination(client):
    rows = "".join(f"SKU-{i:03d},Item {i},,1,{'false' if i % 5 == 0 else 'true'}\n" for i in range(25))
    upload(client, HEADER + rows)

    page = client.get("/products", params={"limit": 10, "offset": 20}).json()
    assert page["total"] == 25 and len(page["items"]) == 5

    assert list_products(client, active="false")["total"] == 5
    assert list_products(client, sku="sku-003")["total"] == 1  # SKU filter ignores case
    assert list_products(client, name="item 2")["total"] == 6  # "Item 2", "Item 20".."Item 24"


def test_bulk_delete_respects_filters(client):
    upload(client, HEADER + "D1,a,,1,true\nD2,b,,1,true\nD3,c,,1,false\n")

    assert client.delete("/products/all", params={"active": "false"}).status_code == 204
    assert list_products(client)["total"] == 2

    assert client.delete("/products/all").status_code == 204
    assert list_products(client)["total"] == 0


# --- Webhooks ------------------------------------------------------------------


@dataclass
class Receiver:
    url: str
    received: list
    status: int = 200  # HTTP status the receiver answers with; tests can change it


@pytest.fixture
def webhook_receiver():
    """A throwaway local HTTP server that records the JSON bodies POSTed to it."""
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(receiver.status)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    receiver = Receiver(url=f"http://127.0.0.1:{server.server_port}/hook", received=received)
    yield receiver
    server.shutdown()


def create_hook(client, url, event="import.completed") -> dict:
    r = client.post("/webhooks", json={"event": event, "url": url})
    assert r.status_code == 201
    return r.json()


def test_webhook_fires_when_import_completes(client, webhook_receiver):
    create_hook(client, webhook_receiver.url)

    status = upload(client, HEADER + "W1,webhook,,1,true\n")

    assert webhook_receiver.received == [
        {"event": "import.completed", "data": {"task_id": status["task_id"], "processed_rows": 1}}
    ]
    assert len(client.get("/webhooks").json()) == 1  # importing doesn't create junk webhook rows


def test_webhook_test_endpoint_and_delete(client, webhook_receiver):
    hook = create_hook(client, webhook_receiver.url, event="ping")

    assert client.post("/webhooks/test/ping").status_code == 202
    assert webhook_receiver.received == [{"event": "ping", "data": {"hello": "world"}}]

    assert client.delete(f"/webhooks/{hook['id']}").status_code == 204
    assert client.get("/webhooks").json() == []


# --- Delivery log ------------------------------------------------------------


def test_successful_delivery_is_logged(client, webhook_receiver):
    hook = create_hook(client, webhook_receiver.url)
    upload(client, HEADER + "L1,log,,1,true\n")

    [delivery] = client.get(f"/webhooks/{hook['id']}/deliveries").json()
    assert delivery["success"] is True
    assert delivery["status_code"] == 200
    assert delivery["response_ms"] > 0
    assert delivery["attempt"] == 1 and delivery["event"] == "import.completed"

    listed = client.get("/webhooks").json()[0]
    assert listed["last_delivery"]["id"] == delivery["id"]


def test_server_errors_are_retried_up_to_three_attempts(client, webhook_receiver, monkeypatch):
    from app.core.celery_app import celery_app

    # With eager propagation on, Celery re-raises the Retry signal instead of
    # running the retry inline; off, eager apply() performs the retries itself.
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False)
    webhook_receiver.status = 500
    hook = create_hook(client, webhook_receiver.url, event="ping")

    client.post("/webhooks/test/ping")  # background path; eager Celery runs the retries inline

    deliveries = client.get(f"/webhooks/{hook['id']}/deliveries").json()
    assert [d["attempt"] for d in deliveries] == [3, 2, 1]  # newest first
    assert all(not d["success"] and d["status_code"] == 500 for d in deliveries)
    assert len(webhook_receiver.received) == 3


def test_client_errors_are_not_retried(client, webhook_receiver):
    webhook_receiver.status = 404
    hook = create_hook(client, webhook_receiver.url, event="ping")

    client.post("/webhooks/test/ping")

    [delivery] = client.get(f"/webhooks/{hook['id']}/deliveries").json()
    assert delivery["status_code"] == 404 and delivery["error"].startswith("HTTP 404")


def test_test_button_returns_the_real_result(client, webhook_receiver):
    hook = create_hook(client, webhook_receiver.url)

    r = client.post(f"/webhooks/{hook['id']}/test")

    assert r.status_code == 200
    assert r.json()["success"] is True and r.json()["status_code"] == 200
    assert webhook_receiver.received[0]["data"]["test"] is True
    assert client.post("/webhooks/999999/test").status_code == 404


def test_unreachable_url_is_logged_as_failure(client):
    hook = create_hook(client, "http://127.0.0.1:9/hook")  # port 9: nothing listens

    result = client.post(f"/webhooks/{hook['id']}/test").json()

    assert result["success"] is False
    assert result["status_code"] is None
    assert result["error"] == "Connection refused by 127.0.0.1"  # readable, not urllib3's repr


def test_deleting_a_webhook_removes_its_delivery_log(client, webhook_receiver):
    from sqlalchemy import text

    from app.core.database import engine

    hook = create_hook(client, webhook_receiver.url)
    client.post(f"/webhooks/{hook['id']}/test")
    client.delete(f"/webhooks/{hook['id']}")

    assert client.get(f"/webhooks/{hook['id']}/deliveries").status_code == 404
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM webhook_deliveries")).scalar() == 0
