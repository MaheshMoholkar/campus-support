from app.services.storage import StoredObject


class FakeStorage:
    """In-memory stand-in for S3. Tests call put() to simulate a finished upload."""

    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}

    def put(self, key: str, size_bytes: int = 1000, content_type: str = "image/png") -> str:
        self.objects[key] = StoredObject(size_bytes, content_type)
        return key

    def presign_put(self, key: str, content_type: str) -> str:
        return f"https://fake.storage/put/{key}"

    def presign_get(self, key: str) -> str:
        return f"https://fake.storage/get/{key}"

    def head(self, key: str) -> StoredObject | None:
        return self.objects.get(key)
