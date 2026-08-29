from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from infrai_storage import InfraiError, InfraiStorage
from nonprofit_snapshot import NightlySnapshotRequest, SnapshotResult, store_nightly_snapshot


app = FastAPI(title="Nonprofit nightly snapshot")


@app.post("/snapshots/nightly", response_model=SnapshotResult)
def create_nightly_snapshot(request: NightlySnapshotRequest) -> SnapshotResult:
    try:
        return store_nightly_snapshot(
            request,
            InfraiStorage(),
            os.environ.get("SNAPSHOT_BUCKET", "nonprofit-nightly-snapshots"),
        )
    except InfraiError as exc:
        client_status = exc.status if 400 <= exc.status < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.details) from exc
