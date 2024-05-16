from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import List
import boto3
import datetime
import db_utils as db
import aws_utils as aws

# 프로젝트 생성을 위한 클래스
class Project(BaseModel):
    project_name: str
    template: bytes
    values: bytes

client = db.connect_to_db()
collection = db.get_collection(client, "cloudcrew", "Projects")
s3 = aws.get_s3_client()

app = FastAPI()

# [GET] 프로젝트 목록 전체 조회
@app.get("/api/v1/projects", response_model=List[str])
async def get_projects():
    try:
        projects = collection.find()
        return [str(project['_id']) for project in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [POST] 프로젝트 생성
@app.post("/api/v1/projects")
async def new_project(project: Project):
    try:
        if len(project.project_name) < 4 or len(project.project_name) > 20:
            raise HTTPException(status_code=400, detail="[ERROR] newProject() input error")

        # 파일을 S3에 업로드
        s3.upload_fileobj(project.template, "your_bucket_name", f"{project.project_name}_template")
        s3.upload_fileobj(project.values, "your_bucket_name", f"{project.project_name}_values")

        # MongoDB에 프로젝트 정보 저장
        result = collection.insert_one({
            'project_name': project.project_name,
            'template': f"{project.project_name}_template",
            'values': f"{project.project_name}_values"
        })

        return {"projectId": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [GET] 단일 프로젝트 조회
@app.get("/api/v1/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    if project_id in projects:
        return projects[project_id]
    else:
        raise HTTPException(status_code=404, detail="[ERROR] GET Project error 요청한 프로젝트의 대한 정보를 찾을 수 없습니다.")

# [DELETE] 프로젝트 삭제
@app.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str):
    if project_id in projects:
        del projects[project_id]
        return {"success": "프로젝트 삭제 성공!"}
    else:
        raise HTTPException(status_code=404, detail="[ERROR] delete - 삭제할 프로젝트를 찾을 수 없습니다.")