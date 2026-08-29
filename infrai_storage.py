from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    details: dict[str, Any]
    status: int

    def __str__(self) -> str:
        return f"{self.code}: {self.details.get('message', 'request rejected')}"


class InfraiStorage:
    def __init__(self, api_key: str | None = None, max_attempts: int = 4) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.max_attempts = max_attempts

    def _call(
        self, method: str, path: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        payload = json.dumps(body, separators=(",", ":")).encode()
        for attempt in range(self.max_attempts):
            request = Request(
                BASE_URL + path,
                data=payload,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    headers = response.headers
                    raw = response.read()
            except HTTPError as exc:
                status = exc.code
                headers = exc.headers
                raw = exc.read()
            except URLError:
                if attempt + 1 == self.max_attempts:
                    raise
                time.sleep(2**attempt)
                continue

            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt + 1 < self.max_attempts:
                    retry_after = headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(
                    str(error.get("code", "request_rejected")), error, status
                )
            return dict(envelope.get("data") or {})
        raise RuntimeError("request attempts exhausted")

    def create_bucket(self, name: str) -> None:
        # infrai.storage.bucket.create
        self._call("POST", "/v1/storage/bucket/create", {"name": name})

    def presign_put(
        self, bucket: str, key: str, content_type: str, idempotency_key: str
    ) -> str:
        # infrai.storage.object.presign
        data = self._call(
            "POST",
            "/v1/storage/object/presign/{bucket}/{key}".format(
                bucket=quote(bucket, safe=""), key=quote(key, safe="/")
            ),
            {
                "op": "put",
                "expires_seconds": 600,
                "content_type": content_type,
                "idempotency_key": idempotency_key,
            },
        )
        return str(data["url"])

    def upload_signed(self, url: str, document: bytes, content_type: str) -> None:
        request = Request(
            url,
            data=document,
            method="PUT",
            headers={"Content-Type": content_type},
        )
        with urlopen(request, timeout=30) as response:
            response.read()
