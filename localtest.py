from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, BotoCoreError
import db_utils as db
from bson import ObjectId
from datetime import datetime, timedelta
import time
from os import getenv
import requests
from requests.auth import HTTPBasicAuth
import pytz
import asyncio

client = db.connect_to_db()
collection = db.get_collection(client, getenv("DB_NAME"), getenv("COL_NAME"))
s3 = boto3.client('s3')
bucket_name = "cc-helm-templates"
tz = pytz.timezone('Asia/Seoul') # 모든 리눅스의 기본 time은 미국 혹은 영국 시간

# 젠킨스 서버 데이터 => Configmap, Secret 예정
jenkins_url = "http://10.0.1.85:8080/job/localTest/buildWithParameters"
jenkins_token = "1151c1c51cd9cdb1d5d8fc1213e1325c3e"
jenkins_user = "admin"
header = {'Content-Type': 'application/x-www-form-urlencoded'}

app = FastAPI()

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    # 허용하는 접속 도메인 작성
    allow_origins=[
        "http://localhost:5173",
        "http://cloudcrew.site",
        "https://cloudcrew.site",
        "http://www.cloudcrew.site",
        "https://www.cloudcrew.site",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# api 주소 시작 페이지 API 구성 (디버깅용)
@app.get("/api")
async def root():
    return {"message": "Welcome to the API"}

# [GET] 프로젝트 목록 전체 조회
@app.get("/api/v1/projects", response_model=List[str])
async def get_projects():
    try:
        projects = collection.find().sort("day", -1)
        return [str(project['_id']) for project in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [POST] SB 프로젝트 생성
@app.post("/api/v1/projects")
async def new_project(
    project_name: str = Form(...),
    template: UploadFile = File(...),
    values: UploadFile = File(...)
):
    try:
        current_time = datetime.now(tz).strftime("%Y:%m:%d:%H:%M:%S")
        
        data = {
            "project_name": project_name,
            "template_url": "NULL",
            "values_url": "NULL",
            "end_point": "NULL",
            "day": current_time,
            "meta_data": {}
        }
        result = collection.insert_one(data)
        project_id = str(result.inserted_id)
        
        template_key = f"projects/{project_id}/{template.filename}"
        values_key = f"projects/{project_id}/{values.filename}"
        
        s3.upload_fileobj(template.file, bucket_name, template_key)
        s3.upload_fileobj(values.file, bucket_name, values_key)
        
        template_url = f"s3://{bucket_name}/{template_key}"
        values_url = f"s3://{bucket_name}/{values_key}"

        collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"template_url": template_url, "values_url": values_url}}
        )

        parameters = {
            'type': 'CREATE',
            'project_name': project_name,
            'project_id': project_id
        }
        
        response = requests.post(
            jenkins_url, 
            data=parameters, 
            headers=header, 
            auth=HTTPBasicAuth(jenkins_user, jenkins_token)
        )
        
        if response.status_code == 201:
            pass

        end_time = datetime.now() + timedelta(seconds=60)  # 타임아웃 설정
        while datetime.now() < end_time:
            doc = collection.find_one({"_id": ObjectId(project_id)})
            if doc['end_point'] != "NULL":
                return JSONResponse(content={"project_id": project_id}, status_code=201)
            await asyncio.sleep(2)  # 2초 후 다시 확인
        
        raise HTTPException(status_code=408, detail="Request Timeout: Jenkins job did not finish in time.")
    
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
        max_wait_time = 30
        check_interval = 2

        elapsed_time = 0
        while elapsed_time < max_wait_time:
            project = collection.find_one({"_id": ObjectId(project_id)})
            if project:
                meta_data = project.get("meta_data", {})
                required_keys = {"helm_name", "last_deployed", "namespace", "status", "revision", "chart", "app_version"}

                if meta_data and required_keys.issubset(meta_data.keys()):
                    project_data = {
                        "project_name": project["project_name"],
                        "end_point": project.get("end_point", "NULL"),
                        "day": project["day"],
                        "meta_data": meta_data
                    }
                    return project_data
                else:
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
            else:
                raise HTTPException(status_code=404, detail="Project not found")

        raise HTTPException(status_code=202, detail="Meta_data is not fully populated yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [DELETE] 프로젝트 삭제
@app.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str):
    try:
        project = collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_name = project.get("project_name")

        parameters = {
            'type': 'DELETE',
            'project_name': project_name,
            'project_id': project_id
        }

        response = requests.post(
            jenkins_url, 
            data=parameters, 
            headers=header, 
            auth=HTTPBasicAuth(jenkins_user, jenkins_token)
        )

        if response.status_code != 201:
            raise HTTPException(status_code=500, detail="Failed to trigger Jenkins job")

        max_wait_time = 60
        wait_interval = 2

        elapsed_time = 0
        while elapsed_time < max_wait_time:
            project = collection.find_one({"_id": ObjectId(project_id)})
            if not project:
                return {"message": "Project deleted successfully"}
            await asyncio.sleep(wait_interval)
            elapsed_time += wait_interval

        raise HTTPException(status_code=500, detail="Timed out waiting for project deletion")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [PUT] 프로젝트 수정
@app.put("/api/v1/projects/{project_id}")
async def update_project(
    project_id: str, 
    values: UploadFile = File(...)
):
    try:
        # S3에서 해당 프로젝트 ID의 values.yaml 파일 삭제
        s3.delete_object(Bucket=bucket_name, Key=f"projects/{project_id}/values.yaml")

        # 업로드된 파일 저장
        values_key = f"projects/{project_id}/{values.filename}"
        s3.upload_fileobj(values.file, bucket_name, values_key)
        
        values_url = f"s3://{bucket_name}/{values_key}"
        current_time = datetime.now(tz).strftime("%Y:%m:%d:%H:%M:%S") # 생성 일자 업데이트
        
        collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"day": current_time, "values_url": values_url}}
        )
        
        # Jenkins Job 트리거
        project = collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_name = project.get("project_name")
        meta_data = project.get("meta_data")
        current_revision = meta_data.get("revision")

        parameters = {
            'type': 'UPDATE',
            'project_name': project_name,
            'project_id': project_id
        }

        response = requests.post(
            jenkins_url, 
            data=parameters, 
            headers=header, 
            auth=HTTPBasicAuth(jenkins_user, jenkins_token)
        )

        if response.status_code != 201:
            raise HTTPException(status_code=500, detail="Failed to trigger Jenkins job")
        
        # 업데이트 완료 체크하기
        max_wait_time = 30 # 최대 시간
        wait_interval = 2 # 2초 마다 확인

        elapsed_time = 0 # 처음 시간
        while elapsed_time < max_wait_time:
            project = collection.find_one({"_id": ObjectId(project_id)})
            meta_data = project.get("meta_data")
            revision = meta_data.get("revision")
            if revision > current_revision:
                return JSONResponse(content="PUT request successful", status_code=200)
            await asyncio.sleep(wait_interval)
            elapsed_time += wait_interval

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project")
