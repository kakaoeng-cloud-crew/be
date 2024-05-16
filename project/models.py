from pydantic import BaseModel, Field
from typing import Optional
from fastapi import File, UploadFile

# 프로젝트 생성을 위한 클래스
class Project(BaseModel):
    project_name: str = Field(..., min_length=4, max_length=20)
    template: UploadFile = Field(...)
    values: UploadFile = Field(...)
