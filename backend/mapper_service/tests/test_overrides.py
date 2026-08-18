from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_DIR = REPO_ROOT / "backend" / "mapper_service"
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app import apply_overrides, parse_overrides  # noqa: E402


def test_review_override_replaces_only_target_column():
    columns = [
        {"code": None, "dict_type": None, "status": "unmapped", "via": None},
        {"code": "WQ-002", "dict_type": "측정항목", "status": "exact", "via": "body"},
    ]

    apply_overrides(columns, {"0": {"code": "WQ-001", "dict_type": "측정항목"}})

    assert columns[0] == {
        "code": "WQ-001",
        "dict_type": "측정항목",
        "status": "exact",
        "via": "review",
    }
    assert columns[1]["code"] == "WQ-002"
    assert columns[1]["via"] == "body"


def test_invalid_override_json_is_rejected_before_streaming():
    with pytest.raises(HTTPException) as raised:
        parse_overrides("not-json")
    assert raised.value.status_code == 400
