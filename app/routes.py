from flask import request, jsonify, send_file, Response
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from . import db
import uuid
import json
import pandas as pd

# Allowed file types
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
ALLOWED_EXCEL_EXTENSIONS = {"xls", "xlsx"}
ALLOWED_JSON_EXTENSIONS = {"json"}

# Folders
BASE_UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
IMAGE_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, "images")
EXCEL_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, "excel")
JSON_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, "json")

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(EXCEL_FOLDER, exist_ok=True)
os.makedirs(JSON_FOLDER, exist_ok=True)


#Helper Functions 
def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def format_metadata(doc, include_data=False):
    """Convert MongoDB document to JSON-serializable dict"""
    res = {k: v for k, v in doc.items() if k != "_id" and (include_data or k != "data")}
    res["_id"] = str(doc["_id"])
    if "upload_date" in res:
        res["upload_date"] = res["upload_date"].isoformat()
    return res


def save_file(file, folder, allowed_exts):
    if not allowed_file(file.filename, allowed_exts):
        return None, "invalid file type"
    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(folder, unique_filename)
    file.save(file_path)
    size = os.path.getsize(file_path)
    return unique_filename, file_path, size


def register_routes(app):

    @app.route("/")
    def index():
        return "API is running!"

    #images 
    @app.route("/images", methods=["GET"])
    def list_images():
        files = list(db.image_files.find({}))
        files = [format_metadata(f) for f in files]
        return jsonify({"files": files})

    #upload images
    @app.route("/images/upload", methods=["POST"])
    def upload_image():
        if "file" not in request.files:
            return jsonify({"error": "no file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "no selected file"}), 400

        filename, file_path, size = save_file(file, IMAGE_FOLDER, ALLOWED_IMAGE_EXTENSIONS)
        if not filename:
            return jsonify({"error": "invalid file type"}), 400

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        result = db.image_files.insert_one(metadata)
        metadata["_id"] = str(result.inserted_id)
        metadata["upload_date"] = metadata["upload_date"].isoformat()

        return jsonify({"msg": "image uploaded", "metadata": metadata}), 201

    #delete images
    @app.route("/images/<filename>", methods=["DELETE"])
    def delete_image(filename):
        file_doc = db.image_files.find_one({"stored_filename": filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        file_path = os.path.join(IMAGE_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.image_files.delete_one({"stored_filename": filename})
        return jsonify({"msg": "file deleted"})

    #view image
    @app.route("/images/view/<filename>", methods=["GET"])
    def view_image(filename):
        file_path = os.path.join(IMAGE_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "file not found"}), 404
        return send_file(file_path, mimetype="image/jpeg")
    
    #update image
    @app.route("/images/<filename>", methods=["PUT"])
    def update_image(filename):
        file_doc = db.image_files.find_one({"stored_filename": filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404

        if "file" not in request.files:
            return jsonify({"error": "no file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "no selected file"}), 400

        new_filename, new_file_path, size = save_file(file, IMAGE_FOLDER, ALLOWED_IMAGE_EXTENSIONS)
        if not new_filename:
            return jsonify({"error": "invalid file type"}), 400

        old_file_path = os.path.join(IMAGE_FOLDER, filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": new_filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        db.image_files.update_one({"stored_filename": filename}, {"$set": metadata})
        metadata["_id"] = str(file_doc["_id"])
        metadata["upload_date"] = metadata["upload_date"].isoformat()

        return jsonify({"msg": "image updated", "metadata": metadata})

    #excel
    @app.route("/excel", methods=["GET"])
    def list_excel():
        files = list(db.excel_files.find({}))
        files = [format_metadata(f) for f in files]
        return jsonify({"files": files})

    #upload excel
    @app.route("/excel/upload", methods=["POST"])
    def upload_excel():
        if "file" not in request.files:
            return jsonify({"error": "no file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "no selected file"}), 400

        filename, file_path, size = save_file(file, EXCEL_FOLDER, ALLOWED_EXCEL_EXTENSIONS)
        if not filename:
            return jsonify({"error": "invalid file type"}), 400

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        result = db.excel_files.insert_one(metadata)
        metadata["_id"] = str(result.inserted_id)
        metadata["upload_date"] = metadata["upload_date"].isoformat()

        return jsonify({"msg": "excel uploaded", "metadata": metadata}), 201

    #delete excel
    @app.route("/excel/<filename>", methods=["DELETE"])
    def delete_excel(filename):
        file_doc = db.excel_files.find_one({"stored_filename": filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        file_path = os.path.join(EXCEL_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.excel_files.delete_one({"stored_filename": filename})
        return jsonify({"msg": "file deleted"})
    
    

    #view excel
    @app.route("/excel/view/<filename>", methods=["GET"])
    def view_excel(filename):
        file_path = os.path.join(EXCEL_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "file not found"}), 404
        df = pd.read_excel(file_path)
        return Response(df.to_html(), mimetype="text/html")
    
    #update excel
    @app.route("/excel/<filename>", methods=["PUT"])
    def update_excel(filename):
        file_doc = db.excel_files.find_one({"stored_filename": filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404

        if "file" not in request.files:
            return jsonify({"error": "no file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "no selected file"}), 400

        new_filename, new_file_path, size = save_file(file, EXCEL_FOLDER, ALLOWED_EXCEL_EXTENSIONS)
        if not new_filename:
            return jsonify({"error": "invalid file type"}), 400

        old_file_path = os.path.join(EXCEL_FOLDER, filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": new_filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        db.excel_files.update_one({"stored_filename": filename}, {"$set": metadata})
        metadata["_id"] = str(file_doc["_id"])
        metadata["upload_date"] = metadata["upload_date"].isoformat()

        return jsonify({"msg": "excel updated", "metadata": metadata})



    #JSON 
    @app.route("/json", methods=["GET"])
    def list_json():
        files = list(db.json_files.find({}, {"data": 0}))
        files = [format_metadata(f) for f in files]
        return jsonify({"files": files})

    #uplaod json
    @app.route("/json/upload", methods=["POST"])
    def upload_json():
        if "file" not in request.files:
            return jsonify({"error": "no file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "no selected file"}), 400
        if not allowed_file(file.filename, ALLOWED_JSON_EXTENSIONS):
            return jsonify({"error": "invalid file type"}), 400

        unique_filename = f"{uuid.uuid4().hex}.json"
        file_path = os.path.join(JSON_FOLDER, unique_filename)
        file.save(file_path)

        try:
            with open(file_path) as f:
                data = json.load(f)
        except Exception:
            os.remove(file_path)
            return jsonify({"error": "invalid JSON file"}), 400

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": unique_filename,
            "data": data,
            "upload_date": datetime.utcnow()
        }
        result = db.json_files.insert_one(metadata)
        metadata["_id"] = str(result.inserted_id)
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        del metadata["data"]  # don't send large data in response

        return jsonify({"msg": "JSON uploaded", "metadata": metadata}), 201

    #delete json
    @app.route("/json/<filename>", methods=["DELETE"])
    def delete_json(filename):
        file_doc = db.json_files.find_one({"stored_filename": filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        file_path = os.path.join(JSON_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.json_files.delete_one({"stored_filename": filename})
        return jsonify({"msg": "file deleted"})

    #view json
    @app.route("/json/view/<filename>", methods=["GET"])
    def view_json(filename):
        file_path = os.path.join(JSON_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "file not found"}), 404
        with open(file_path) as f:
            data = json.load(f)
        return jsonify(data)

    #update json
    @app.route("/json/<filename>", methods=["PUT"])
    def update_json(filename):
        file_doc = db.json_files.find_one({"stored_filename": filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        if "file" not in request.files:
            return jsonify({"error": "no file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "no selected file"}), 400
        if not allowed_file(file.filename, ALLOWED_JSON_EXTENSIONS):
            return jsonify({"error": "invalid file type"}), 400

        old_file_path = os.path.join(JSON_FOLDER, filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        unique_filename = f"{uuid.uuid4().hex}.json"
        new_file_path = os.path.join(JSON_FOLDER, unique_filename)
        file.save(new_file_path)

        try:
            with open(new_file_path) as f:
                data = json.load(f)
        except Exception:
            os.remove(new_file_path)
            return jsonify({"error": "invalid JSON file"}), 400

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": unique_filename,
            "data": data,
            "upload_date": datetime.utcnow()
        }
        db.json_files.update_one({"stored_filename": filename}, {"$set": metadata})
        metadata["_id"] = str(file_doc["_id"])
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        del metadata["data"]

        return jsonify({"msg": "JSON updated", "metadata": metadata})
