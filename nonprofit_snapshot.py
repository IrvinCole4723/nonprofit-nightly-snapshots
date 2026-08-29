from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field


class DonorReceipt(BaseModel):
    receipt_id: str
    donor_id: str
    amount_cents: int = Field(ge=1)
    received_on: date


class VolunteerReminder(BaseModel):
    volunteer_id: str
    shift_id: str
    due_on: date
    sent: bool = False


class CampaignReport(BaseModel):
    campaign_id: str
    donated_cents: int = Field(ge=0)
    volunteer_hours: int = Field(ge=0)


class NightlySnapshotRequest(BaseModel):
    nonprofit_id: str
    snapshot_date: date
    receipts: list[DonorReceipt]
    reminders: list[VolunteerReminder]
    campaigns: list[CampaignReport]


class StoragePort(Protocol):
    def create_bucket(self, name: str) -> None:
        raise AssertionError("protocol method")

    def presign_put(
        self, bucket: str, key: str, content_type: str, idempotency_key: str
    ) -> str:
        raise AssertionError("protocol method")

    def upload_signed(self, url: str, document: bytes, content_type: str) -> None:
        raise AssertionError("protocol method")


@dataclass(frozen=True)
class SnapshotResult:
    object_key: str
    receipt_count: int
    reminder_count: int
    campaign_count: int
    sha256: str


def build_snapshot(request: NightlySnapshotRequest) -> dict[str, object]:
    pending_reminders = [item for item in request.reminders if not item.sent]
    active_campaigns = [
        item
        for item in request.campaigns
        if item.donated_cents > 0 or item.volunteer_hours > 0
    ]
    return {
        "nonprofit_id": request.nonprofit_id,
        "snapshot_date": request.snapshot_date.isoformat(),
        "donor_receipts": [item.model_dump(mode="json") for item in request.receipts],
        "volunteer_reminders": [
            item.model_dump(mode="json") for item in pending_reminders
        ],
        "campaign_reporting": [
            item.model_dump(mode="json") for item in active_campaigns
        ],
    }


def store_nightly_snapshot(
    request: NightlySnapshotRequest, storage: StoragePort, bucket: str
) -> SnapshotResult:
    storage.create_bucket(bucket)
    snapshot = build_snapshot(request)
    document = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(document).hexdigest()
    object_key = (
        f"nonprofits/{request.nonprofit_id}/nightly/"
        f"{request.snapshot_date.isoformat()}.json"
    )
    upload_url = storage.presign_put(
        bucket, object_key, "application/json", f"snapshot-{digest}"
    )
    storage.upload_signed(upload_url, document, "application/json")
    return SnapshotResult(
        object_key=object_key,
        receipt_count=len(request.receipts),
        reminder_count=len(snapshot["volunteer_reminders"]),
        campaign_count=len(snapshot["campaign_reporting"]),
        sha256=digest,
    )
