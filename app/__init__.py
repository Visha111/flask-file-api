from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv
import os

mongo_client=None
db=None

def create_app():
    global mongo_client,db

    load_dotenv()

    app = Flask(__name__)

    app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","defaultsecret")
    mongo_uri=os.getenv("MONGO_URI","mongodb://localhost:27017/file_api")

    mongo_client = MongoClient(mongo_uri)
    db = mongo_client.get_database("file_api")

    from .routes import register_routes
    register_routes(app)

    return app




