import json

from nonprofit_snapshot import NightlySnapshotRequest, store_nightly_snapshot


class RecordingStorage:
    def __init__(self) -> None:
        self.bucket = ""
        self.key = ""
        self.idempotency_key = ""
        self.document = b""

    def create_bucket(self, name: str) -> None:
        self.bucket = name

    def presign_put(
        self, bucket: str, key: str, content_type: str, idempotency_key: str
    ) -> str:
        self.key = key
        self.idempotency_key = idempotency_key
        return "https://signed.example/upload"

    def upload_signed(self, url: str, document: bytes, content_type: str) -> None:
        self.document = document


def test_snapshot_keeps_pending_work_and_active_campaigns() -> None:
    request = NightlySnapshotRequest.model_validate(
        {
            "nonprofit_id": "library-friends",
            "snapshot_date": "2026-08-17",
            "receipts": [
                {
                    "receipt_id": "rcpt-104",
                    "donor_id": "donor-8",
                    "amount_cents": 7500,
                    "received_on": "2026-08-17",
                }
            ],
            "reminders": [
                {"volunteer_id": "v-1", "shift_id": "s-9", "due_on": "2026-08-18"},
                {
                    "volunteer_id": "v-2",
                    "shift_id": "s-10",
                    "due_on": "2026-08-18",
                    "sent": True,
                },
            ],
            "campaigns": [
                {"campaign_id": "books", "donated_cents": 7500, "volunteer_hours": 3},
                {"campaign_id": "quiet", "donated_cents": 0, "volunteer_hours": 0},
            ],
        }
    )
    storage = RecordingStorage()

    result = store_nightly_snapshot(request, storage, "nightly-archive")
    saved = json.loads(storage.document)

    assert storage.bucket == "nightly-archive"
    assert result.object_key == "nonprofits/library-friends/nightly/2026-08-17.json"
    assert [item["volunteer_id"] for item in saved["volunteer_reminders"]] == ["v-1"]
    assert [item["campaign_id"] for item in saved["campaign_reporting"]] == ["books"]
    assert storage.idempotency_key.startswith("snapshot-")
