from pymongo import MongoClient
from os import getenv

def connect_to_db():
    user = getenv("DB_USER")
    pwd = getenv("DB_PWD")
    host = getenv("DB_HOST")
    port = 27017
    
    client = MongoClient(
        host=host,
        port=27017,
        username=user,
        password=pwd
    )
    
    return client

def get_collection(client, db_name, collection_name):
    db = client[db_name]
    
    return db[collection_name]