from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from werkzeug.exceptions import abort
from pymongo.errors import ServerSelectionTimeoutError
import os
import fe_klassen


def get_db_conn(collection = None) -> MongoClient:
    try:
        try:
            # standard configuration
            if collection is None:
                collection = os.environ['MONGO_DB_COLLECTION']
                
            host_conf = os.environ['MONGO_DB_HOST']
            username = os.environ['MONGO_DB_USER']
            password = os.environ['MONGO_DB_PASSWORD']
            port_conf = os.environ['MONGO_DB_PORT']
            database_conf = os.environ['MONGO_DB_NAME']
            #coll_conf = os.environ['MONGO_DB_COLLECTION']
            coll_conf = collection
        
        db_host = f"mongodb://{username}:{password}@{host_conf}:{port_conf}"
        client = MongoClient(db_host, serverSelectionTimeoutMS=2000)
        client.server_info()  # Test the connection
        db = client[database_conf]
        collection = db[coll_conf]
        return collection
    except ServerSelectionTimeoutError:
        return None
    

# gets the conf mongodb collection
def get_conf(user):
    conn = get_db_conn('conf')
    conf = conn.find_one({'_id': user})
    return conf


# gets a single conf
def get_single_conf(user, key: str):
    conn = get_db_conn('conf')
    conf = conn.find_one({'_id': user})
    try:
        val = conf.get(key)
    except AttributeError:
        val = None
    return val


# updates a single conf
def update_single_conf(user, key: str, value: any):
    conn = get_db_conn('conf')
    conn.update_one({'_id': user}, {'$set': {key: value}})
    

# sets a single conf
def set_single_conf(user, key: str, value: any):
    conn = get_db_conn('conf')
    conn.insert_one({'_id': user}, {'$set': {key: value}}, upsert=True)
