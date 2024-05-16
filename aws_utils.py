import boto3
from os import getenv

def get_s3_client():
    s3 = boto3.client(
        's3',
        aws_access_key_id=getenv('AWS_PUB_KEY'),
        aws_secret_access_key=getenv('AWS_PRI_KEY')
    )
    
    return s3
