from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, BotoCoreError
import db_utils as db
from bson import ObjectId
from datetime import datetime
from datetime import timedelta
import time
from os import getenv
import requests
from requests.auth import HTTPBasicAuth
import pytz

client = db.connect_to_db()
collection = db.get_collection(client, getenv("DB_NAME"), getenv("COL_NAME"))
s3 = boto3.client('s3')
bucket_name = "cc-helm-templates"
tz = pytz.timezone('Asia/Seoul') # 모든 리눅스의 기본 time은 미국 혹은 영국 시간

# 젠킨스 서버 데이터 => Configmap, Secret 예정
jenkins_url = "http://10.0.1.85:8080/job/CloudCrew-JOB/buildWithParameters"
jenkins_token = "1151c1c51cd9cdb1d5d8fc1213e1325c3e"
jenkins_user = "admin"
header = {'Content-Type': 'application/x-www-form-urlencoded'}

app = FastAPI()

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    # 허용하는 접속 도메인 작성
    allow_origins=[
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
        # 생성 날짜를 내림차순 기준으로 리턴
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
            "day": current_time
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
            print('Job triggered successfully.')
        else:
            print(f'Failed to trigger job: {response.status_code}')
            print(response.text)

        # Jenkins 파이프라인의 응답 대기 및 확인 로직 추가
        end_time = datetime.now() + timedelta(seconds=60)  # 타임아웃 설정
        while datetime.now() < end_time:
            doc = collection.find_one({"_id": ObjectId(project_id)})
            if doc['end_point'] != "NULL":
                return JSONResponse(content={"project_id": project_id}, status_code=201)
            time.sleep(3)  # 3초 후 다시 확인
        
        # 1분이 지나도 end_point가 업데이트 되지 않으면 타임아웃 예외 처리
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

@app.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str):
    project = collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_name = project.get("project_name")

    # 1. 넘겨줄 매개변수 틀 작성
    parameters = {
        'type': 'DELETE',
        'project_name': project_name,
        'project_id': project_id
    }

    # 2. 젠킨스 Job에 POST 요청 보내서 Job 실행하기
    response = requests.post(
        jenkins_url, 
        data=parameters, 
        headers=header, 
        auth=HTTPBasicAuth(jenkins_user, jenkins_token)
    )

    # 3. 응답 확인
    if response.status_code != 201:
        raise HTTPException(status_code=500, detail="Failed to trigger Jenkins job")

    # 4. 데이터베이스에서 프로젝트 삭제 여부 확인
    max_wait_time = 60  # 최대 5분 대기
    wait_interval = 3   # 10초 간격으로 확인

    elapsed_time = 0
    while elapsed_time < max_wait_time:
        project = collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            return {"message": "Project deleted successfully"}
        time.sleep(wait_interval)
        elapsed_time += wait_interval

    raise HTTPException(status_code=500, detail="Timed out waiting for project deletion")
