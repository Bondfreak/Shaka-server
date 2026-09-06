#!/usr/bin/env python3
"""S4 F1 runtime smoke — POST /f1/answer + GET /f1/assets?side=BB.

Modes:
  --mode testclient   (default) uses FastAPI TestClient; no live server/Core
  --mode http         hits a running uvicorn (--base-url)

Expects fixture freeze snapshot_id=ac-fixture-v1. No Drive writes. No LLM.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


EXPECTED_SNAPSHOT = "ac-fixture-v1"
DEFAULT_QUERY = "Hvornår blev impellerne sidst skiftet?"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _check_answer(body: dict[str, Any]) -> None:
    for key in (
        "conclusion",
        "basis",
        "uncertainty_conflict",
        "sources",
        "policy_results",
        "epistemic_status",
        "snapshot_id",
    ):
        if key not in body:
            _fail(f"answer missing field {key!r}")
    if body.get("snapshot_id") != EXPECTED_SNAPSHOT:
        _fail(f"expected snapshot_id={EXPECTED_SNAPSHOT!r}, got {body.get('snapshot_id')!r}")
    if not isinstance(body["conclusion"], str) or not body["conclusion"].strip():
        _fail("answer.conclusion must be non-empty string")
    audit = body.get("audit") or {}
    if isinstance(audit, dict) and audit.get("snapshot_id") not in (None, EXPECTED_SNAPSHOT):
        _fail(f"audit.snapshot_id mismatch: {audit.get('snapshot_id')!r}")


def _check_assets(body: dict[str, Any]) -> None:
    assets = body.get("assets")
    if not isinstance(assets, list) or not assets:
        _fail("assets list missing or empty for side=BB")
    if any(a.get("side") != "BB" for a in assets if isinstance(a, dict)):
        _fail("assets?side=BB returned non-BB asset")
    ids = {a.get("id") for a in assets if isinstance(a, dict)}
    if "AI-D4-BB-ENGINE" not in ids:
        # tolerate alternate id constants if present in registry
        if not any(isinstance(a, dict) and a.get("side") == "BB" and a.get("serial") for a in assets):
            _fail(f"BB assets missing expected engine identity; ids={sorted(ids)}")


def _run_testclient(query: str) -> None:
    from fastapi.testclient import TestClient

    from shaka_server.app import create_app
    from shaka_server.core_client import CoreResult

    class _StubCore:
        def asset_instance_detail(self, public_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def graph(self, public_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def object_detail(self, public_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def cog_graph(self, graph_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def cog_object(self, public_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def cog_flow(self, circuit_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def cog_topology(self, system_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

        def cog_diagnostic(self, scenario_id: str) -> CoreResult:
            return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    client = TestClient(create_app(core_client=_StubCore()))
    answer = client.post("/api/v1/f1/answer", json={"query": query})
    if answer.status_code != 200:
        _fail(f"/f1/answer status {answer.status_code}: {answer.text}")
    _check_answer(answer.json())

    assets = client.get("/api/v1/f1/assets", params={"side": "BB"})
    if assets.status_code != 200:
        _fail(f"/f1/assets status {assets.status_code}: {assets.text}")
    _check_assets(assets.json())
    print("PASS (testclient): /api/v1/f1/answer + /api/v1/f1/assets?side=BB")
    print(f"  snapshot_id={answer.json().get('snapshot_id')}")
    print(f"  bb_assets={len(assets.json().get('assets') or [])}")


def _run_http(base_url: str, query: str) -> None:
    import httpx

    base = base_url.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        answer = client.post(
            f"{base}/api/v1/f1/answer",
            json={"query": query},
            headers={"Content-Type": "application/json"},
        )
        if answer.status_code != 200:
            _fail(f"/f1/answer status {answer.status_code}: {answer.text}")
        body = answer.json()
        _check_answer(body)

        assets = client.get(f"{base}/api/v1/f1/assets", params={"side": "BB"})
        if assets.status_code != 200:
            _fail(f"/f1/assets status {assets.status_code}: {assets.text}")
        _check_assets(assets.json())

    print(f"PASS (http {base}): /api/v1/f1/answer + /api/v1/f1/assets?side=BB")
    print(f"  snapshot_id={body.get('snapshot_id')}")
    print(f"  bb_assets={len(assets.json().get('assets') or [])}")
    print(json.dumps({"conclusion": body.get("conclusion"), "snapshot_id": body.get("snapshot_id")}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="S4 F1 runtime smoke (ac-fixture-v1)")
    parser.add_argument(
        "--mode",
        choices=("testclient", "http"),
        default="testclient",
        help="testclient (default, no live server) or http against --base-url",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="uvicorn base URL when --mode http (default http://127.0.0.1:8000)",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="F1 answer query")
    args = parser.parse_args()

    if args.mode == "testclient":
        _run_testclient(args.query)
    else:
        _run_http(args.base_url, args.query)


if __name__ == "__main__":
    main()
