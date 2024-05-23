# 베이스 이미지 = 3.10.x (작업 환경 속 버전 고려 3.10.12)
FROM python:3.10.12-slim

# 작업 디렉터리 설정
WORKDIR /app

# 의존성 파일 복사
COPY requirements.txt .

# 파이썬 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# kubectl 설치
RUN apt-get update && \
    apt-get install -y curl && \
    curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

# helm 설치
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 현재 디렉터리의 모든 파일을 컨테이너의 작업 디렉터리로 복사
COPY . .

# 애플리케이션 실행
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
