from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import boto3
from botocore.exceptions import NoCredentialsError
import db_utils as db
from bson import ObjectId
from datetime import datetime

client = db.connect_to_db()
collection = db.get_collection(client, "cloudcrew", "Projects")
s3 = boto3.client('s3')
bucket_name = "cc-helm-templates"

app = FastAPI()

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 필요한 출처 추가
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
        # Save the current time
        current_time = datetime.now().strftime("%Y:%m:%d:%H:%M:%S")
        
        # Save the project information to MongoDB and get the _id
        data = {
            "project_name": project_name,
            "template_url": "",
            "values_url": "",
            "end_point": "",
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [GET] 단일 프로젝트 조회
@app.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str):
    print("GET API")

# [DELETE] 프로젝트 삭제
@app.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str):
    print("DELETE API")
