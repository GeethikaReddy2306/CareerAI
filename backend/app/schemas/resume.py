from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ResumeUploadResponse(BaseModel):
    id: str
    filename: str
    message: str = "Resume uploaded and parsed successfully"
    text_length: int


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=False)


class ResumeDetailResponse(ResumeResponse):
    extracted_text: str | None = None
    has_analysis: bool = False

    model_config = ConfigDict(from_attributes=False)
