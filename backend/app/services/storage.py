from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings

URL_SECONDS = 600


@dataclass(frozen=True)
class StoredObject:
    size_bytes: int
    content_type: str


class Storage(Protocol):
    def presign_put(self, key: str, content_type: str) -> str: ...
    def presign_get(self, key: str) -> str: ...
    def head(self, key: str) -> StoredObject | None: ...


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket_attachments
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                # Garage does not accept the newer default checksum headers.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def presign_put(self, key: str, content_type: str) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=URL_SECONDS,
        )

    def presign_get(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=URL_SECONDS
        )

    def head(self, key: str) -> StoredObject | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return StoredObject(
            response["ContentLength"], response.get("ContentType", "application/octet-stream")
        )
