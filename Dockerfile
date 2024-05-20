# 베이스 이미지를 파이썬 3.8로 설정
FROM python:3.10.12-slim

# 작업 디렉터리 설정
WORKDIR /app

# 의존성 파일 복사
COPY requirements.txt .

# 파이썬 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 현재 디렉터리의 모든 파일을 컨테이너의 작업 디렉터리로 복사
COPY . .

# 애플리케이션 실행
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
