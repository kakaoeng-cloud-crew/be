from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, BotoCoreError
import db_utils as db
from bson import ObjectId
from datetime import datetime
from os import getenv

client = db.connect_to_db()
collection = db.get_collection(client, getenv("DB_NAME"), getenv("COL_NAME"))
s3 = boto3.client('s3')
bucket_name = "cc-helm-templates"

app = FastAPI()

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],  # 리액트에서 보내는 요청 허용
    #allow_origins=["https://www.cloudcrew.site"],
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# [GET] Retrieve the entire list of projects
@app.get("/api/v1/projects", response_model=List[str])
async def get_projects():
    try:
        projects = collection.find()
        return [str(project['_id']) for project in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [POST] Create a new project
@app.post("/api/v1/projects")
async def new_project(
    project_name: str = Form(...),
    template: UploadFile = File(...),
    values: UploadFile = File(...)
):
    try:
        # create current datetime
        current_time = datetime.now().strftime("%Y:%m:%d:%H:%M:%S")
        
        # create documents and save project _id property
        data = {
            "project_name": project_name,
            "template_url": "NULL",
            "values_url": "NULL",
            "end_point": "No data endPoint",
            "day": current_time
        }
        result = collection.insert_one(data)
        project_id = str(result.inserted_id)
        
        # Upload files to S3
        template_key = f"projects/{project_id}/{template.filename}"
        values_key = f"projects/{project_id}/{values.filename}"
        
        s3.upload_fileobj(template.file, bucket_name, template_key)
        s3.upload_fileobj(values.file, bucket_name, values_key)
        
        template_url = f"https://{bucket_name}.s3.amazonaws.com/{template_key}"
        values_url = f"https://{bucket_name}.s3.amazonaws.com/{values_key}"
        
        # Update the S3 URLs in MongoDB
        collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"template_url": template_url, "values_url": values_url}}
        )
        
        return JSONResponse(content={"project_id": project_id}, status_code=201)
    
    except NoCredentialsError:
        raise HTTPException(status_code=403, detail="AWS credentials not available")
    except PartialCredentialsError:
        raise HTTPException(status_code=403, detail="Incomplete AWS credentials")
    except BotoCoreError as e:
        raise HTTPException(status_code=500, detail=f"AWS error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [GET] 단일 프로젝트 조회
@app.get("/api/v1/projects/{project_id}", response_model=dict)
async def get_project(project_id: str):
    try:
        # ObjectId로 변환하여 MongoDB에서 프로젝트 찾기
        project = collection.find_one({"_id": ObjectId(project_id)})
        if project:
            # 프로젝트 정보를 dict로 변환하고, _id를 문자열로 변환
            project_data = {
                "project_name": project["project_name"],
                "end_point": project.get("end_point", "NULL"), # end_point가 없는 경우 빈 문자열 반환
                "day": project["day"],
                "meta_data": "Metadata not available"
            }
            return project_data
        else:
            # 프로젝트가 없는 경우 404 에러 반환
            raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        # 예외 처리
        raise HTTPException(status_code=500, detail=str(e))

# [DELETE] 프로젝트 삭제
@app.delete("/api/v1/projects/{project_id}", response_model=dict)
async def delete_project(project_id: str):
    try:
        # ObjectId로 변환하여 MongoDB에서 프로젝트 삭제
        result = collection.delete_one({"_id": ObjectId(project_id)})
        if result.deleted_count:
            # 프로젝트가 성공적으로 삭제된 경우
            return {"message": "Project successfully deleted"}
        else:
            # 프로젝트가 없는 경우 404 에러 반환
            raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        # 예외 처리
        raise HTTPException(status_code=500, detail=str(e))
