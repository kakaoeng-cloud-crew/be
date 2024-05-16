from pydantic import BaseModel
from typing import Dict, Optional

# 프로젝트 단일 조회 시 사용할 클래스
class ProjectConfig(BaseModel):
    end_point: str
    meta_data: Dict[str, Optional[str]]
