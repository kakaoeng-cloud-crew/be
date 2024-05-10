import boto3
import pymongo
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse

app = FastAPI()

# / 엔드포인트의 GET 메서드
@app.get("/")
def welcome() -> dict:
    return {
            "message": "hello fastapi"
    }

# /news 엔드포인트의 GET 메서드
@app.get("/news")
def news() -> str:
    return "뉴스 페이지"

# /blog 엔드포인트의 GET 메서드
@app.get("/blog")
def blog():
    return FileResponse('blog/index.html')

# /k8s 엔드포인트의 GET 메서드
@app.get('/k8s')
def k8s():
    return RedirectResponse('https://kubernetes.io')

# 리다이렉션은 이렇게도 가능하다
@app.get("/docker", response_class=RedirectResponse)
async def redirect_fastapi():
    return "https://www.docker.com/"