# 베이스 이미지 = 3.10.x (작업 환경 속 버전 고려 3.10.12)
FROM python:3.10.12-slim

# 작업 디렉터리 설정
WORKDIR /app

# 의존성 파일 복사
COPY requirements.txt .

# 파이썬 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# Helm 설치 (EKS에서 사용 중인 버전에 맞춤)
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 && \
    chmod 700 get_helm.sh && \
    ./get_helm.sh --version v3.15.0-rc.2 && \
    rm get_helm.sh && \
    apt-get remove --purge -y curl && apt-get autoremove -y && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 현재 디렉터리의 모든 파일을 컨테이너의 작업 디렉터리로 복사
COPY . .

# 애플리케이션 실행
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
