from kubernetes import client, config as kube_config
import ssl

# 기존에 설정된 인증 정보를 사용합니다.
config = client.Configuration()
config.api_key['authorization'] = open('/var/run/secrets/kubernetes.io/serviceaccount/token').read()
config.api_key_prefix['authorization'] = 'Bearer'
config.host = 'https://kubernetes.default'
config.ssl_ca_cert = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
config.verify_ssl = True

# API 클라이언트 설정
api_client = client.ApiClient(config)
v1 = client.CoreV1Api(api_client)

# 'test123' 네임스페이스 생성
namespace_name = 'test123'
namespace_body = client.V1Namespace(
    metadata=client.V1ObjectMeta(name=namespace_name)
)

try:
    # 네임스페이스 생성 시도
    v1.create_namespace(body=namespace_body)
    print(f"Namespace '{namespace_name}' created successfully.")
except client.exceptions.ApiException as e:
    if e.status == 409:
        print(f"Namespace '{namespace_name}' already exists.")
    else:
        print(f"Failed to create namespace '{namespace_name}'. Error: {e}")