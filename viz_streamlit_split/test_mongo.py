import sys
print("PYTHON =", sys.executable)

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["graph_app"]

print("Connexion OK")
print("Base =", db.name)
print("Collections =", db.list_collection_names())