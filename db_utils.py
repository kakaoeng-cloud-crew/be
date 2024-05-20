from pymongo import MongoClient
from os import getenv

def connect_to_db():
    user = getenv("DB_USER")
    pwd = getenv("DB_PWD")
    host = getenv("DB_HOST")
    port = int(getenv("DB_PORT", 27017))
    
    if not all([user, pwd, host]):
        raise EnvironmentError("DB_USER, DB_PWD, and DB_HOST environment variables must be set")
    
    client = MongoClient(
        host=host,
        port=port,
        username=user,
        password=pwd
    )
    
    return client

def get_collection(client, db_name, collection_name):
    db = client[db_name]
    
    return db[collection_name]