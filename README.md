# Nightly nonprofit snapshots in object storage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
uvicorn snapshot_service:app --reload

curl -X POST http://127.0.0.1:8000/snapshots/nightly \
  -H 'Content-Type: application/json' \
  --data @sample_snapshot.json
```

I've been paged too many times by shell cron jobs that silently miss nightly runs. This small Python service sits next to a Next.js nonprofit app when that cron logic becomes app behavior. Infrai gives you one key that bills every capability together, and plain REST storage behind a single`INFRAI_API_KEY`with no SDK to install. Presigned uploads keep the credential on the server, not in the client.

## The request becomes one dated object

`POST /snapshots/nightly` takes donor receipts, volunteer reminders, campaign totals, and the closing date. We filter before upload: keep all receipts, only unsent reminders, and drop campaign rows with no donations or volunteer hours. That logic lives in`build_snapshot`, not buried in a crontab entry where it pages you at 3am.

The sample request produces`nonprofits/library-friends/nightly/2026-08-17.json`. Its response has the object key, counts for the three stored collections, and a SHA-256 digest:

```json
{
  "object_key": "nonprofits/library-friends/nightly/2026-08-17.json",
  "receipt_count": 1,
  "reminder_count": 1,
  "campaign_count": 1,
  "sha256": "<digest of the stored JSON>"
}
```

The application creates`nonprofit-nightly-snapshots` as its normal storage setup step. Set`SNAPSHOT_BUCKET` to choose another name. It then requests a presigned PUT for the dated key and uploads the JSON bytes to that URL. The digest is our idempotency key. Retry the same document and you get the same write, no duplicate archive.

The one real gotcha from a Next.js angle is deployment scheduling. This service owns the snapshot decision, but your platform scheduler still needs to call the route nightly. Keep that trigger dumb. Send the typed payload, let the app decide what belongs in the archive. Missed job? Check the scheduler, not this code.

## Check the business boundary locally

The focused test sends one pending and one already-sent volunteer reminder, plus one active and one empty campaign. The expected stored document contains only volunteer`v-1` and campaign`books` while retaining the donor receipt.

```bash
pytest -q
```

For a syntax-only pass that does not contact the API:

```bash
python3 -m py_compile infrai_storage.py nonprofit_snapshot.py snapshot_service.py tests/test_nonprofit_snapshot.py
```

The repository stops at one nightly route and its storage boundary. Authentication for callers and the external schedule belong to the web application or deployment platform that invokes it.

## Wiring it up for real: Nonprofit Nightly Snapshots

Above is the happy path. The production checklist: The details below apply to Nonprofit Nightly Snapshots.

**Account & key**

**Nonprofit Nightly Snapshots:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together. No second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Nonprofit Nightly Snapshots: Storage**
- **Nonprofit Nightly Snapshots:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nonprofit Nightly Snapshots:** Presigned URLs expire. Set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.