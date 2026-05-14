import json

from app.api.utils import response_payloads


def _get_json(response):
    """Decode a Starlette/JSONResponse body into a Python dict."""
    # response.body is bytes
    return json.loads(response.body.decode())


def test_success_response_with_data():
    resp = response_payloads.success_response(200, "OK", {"id": 1})
    assert resp.status_code == 200
    body = _get_json(resp)
    assert body["status"] == "SUCCESS"
    assert body["status_code"] == 200
    assert body["message"] == "OK"
    assert body["data"] == {"id": 1}


def test_success_response_no_data():
    resp = response_payloads.success_response(200, "No data")
    body = _get_json(resp)
    assert body["data"] == {}


def test_auth_response_merges_data_and_token():
    resp = response_payloads.auth_response(201, "Logged in", "token123", {"user": {"id": 1}})
    assert resp.status_code == 201
    body = _get_json(resp)
    assert body["status"] == "SUCCESS"
    assert body["data"]["access_token"] == "token123"
    assert body["data"]["user"] == {"id": 1}


def test_error_response():
    resp = response_payloads.error_response(
        status_code=400, message="Bad Request", errors={"errors": ["x"]}
    )
    assert resp.status_code == 400
    body = _get_json(resp)

    assert body["error_code"] == "ERROR"
    assert body["message"] == "Bad Request"
    assert body["status_code"] == 400
    assert body["errors"] == {"errors": ["x"]}
