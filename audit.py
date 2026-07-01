from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AUDIT_LOG = DATA_DIR / "audit.log"
APPEALS_FILE = DATA_DIR / "appeals.jsonl"
CERTIFICATES_FILE = DATA_DIR / "certificates.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def write_audit_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dir()
    event = {
        "event_id": new_id("evt"),
        "event_type": event_type,
        "timestamp": utc_now(),
        **payload,
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def save_appeal(appeal: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dir()
    with APPEALS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(appeal, sort_keys=True) + "\n")
    return appeal


def read_appeals(limit: int = 50) -> list[dict[str, Any]]:
    if not APPEALS_FILE.exists():
        return []
    entries = []
    with APPEALS_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-limit:]


def read_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    if not AUDIT_LOG.exists():
        return []
    entries = []
    with AUDIT_LOG.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-limit:]


def save_certificate(certificate: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dir()
    with CERTIFICATES_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(certificate, sort_keys=True) + "\n")
    return certificate


def read_certificates(limit: int = 50) -> list[dict[str, Any]]:
    if not CERTIFICATES_FILE.exists():
        return []
    entries = []
    with CERTIFICATES_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-limit:]


def latest_certificate_for_creator(creator_id: str) -> dict[str, Any] | None:
    for certificate in reversed(read_certificates(limit=500)):
        if certificate.get("creator_id") == creator_id and certificate.get("status") == "verified_human":
            return certificate
    return None
