from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "graph_app"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

users_collection = db["users"]
charts_collection = db["charts"]
dashboards_collection = db["dashboards"]