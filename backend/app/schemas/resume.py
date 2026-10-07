from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ResumeUploadResponse(BaseModel):
    id: int
    filename: str
    message: str = "Resume uploaded and parsed successfully"
    text_length: int


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    original_filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeDetailResponse(ResumeResponse):
    extracted_text: str | None = None
    has_analysis: bool = False

    model_config = ConfigDict(from_attributes=True)

