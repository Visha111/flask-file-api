from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv
import os

mongo_client = None
db = None

def create_app():
    global mongo_client, db

    load_dotenv()

    # Project root and uploads folder
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_path = os.path.join(project_root, "uploads")

    # Flask app setup
    app = Flask(
        __name__,
        static_folder=uploads_path,
        static_url_path="/files"
    )
    app.config["DEBUG"] = True
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "defaultsecret")

    # MongoDB connection
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/file_api")
    mongo_client = MongoClient(mongo_uri)
    db = mongo_client.get_database("file_api")

    # Upload folders
    app.config['BASE_UPLOAD_FOLDER'] = app.static_folder
    app.config['IMAGE_FOLDER'] = os.path.join(app.static_folder, "images")
    app.config['EXCEL_FOLDER'] = os.path.join(app.static_folder, "excel")
    app.config['JSON_FOLDER'] = os.path.join(app.static_folder, "json")

    for folder in [app.config['IMAGE_FOLDER'], app.config['EXCEL_FOLDER'], app.config['JSON_FOLDER']]:
        os.makedirs(folder, exist_ok=True)

    # Register routes
    from .routes import register_routes
    register_routes(app, db)

    return app
