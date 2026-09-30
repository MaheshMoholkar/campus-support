from pydantic import BaseModel, Field


class PresignIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int


class PresignOut(BaseModel):
    key: str
    upload_url: str
