from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client.spotify

result = db.test.insert_one({
    "name": "test"
})

print("INSERTED:", result.inserted_id)

print("COUNT:", db.test.count_documents({}))
