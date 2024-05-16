import boto3
from os import getenv

def get_s3_client():
    s3 = boto3.client('s3')
    
    return s3