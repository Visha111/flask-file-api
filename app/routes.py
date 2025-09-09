from flask import request, jsonify, Response
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
import json
import pandas as pd

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
ALLOWED_EXCEL_EXTENSIONS = {"xls", "xlsx"}
ALLOWED_JSON_EXTENSIONS = {"json"}

def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

def format_metadata(doc, include_data=False):
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

def generate_file_url(host_url, stored_filename):
    return f"{host_url.rstrip('/')}/files/{stored_filename}"

def register_routes(app, db):
    @app.route("/")
    def index():
        return "API is running! Access files at /files/..."

    # ---------------- Images ----------------
    @app.route("/images", methods=["GET"])
    def list_images():
        files = [format_metadata(f) for f in db.image_files.find({})]
        host_url = request.host_url
        for f in files:
            f["url"] = generate_file_url(host_url, f["stored_filename"])
        return jsonify({"files": files})

    @app.route("/images/upload", methods=["POST"])
    def upload_image():
        if "file" not in request.files or request.files["file"].filename == "":
            return jsonify({"error": "no file selected"}), 400
        file = request.files["file"]

        os.makedirs(app.config['IMAGE_FOLDER'], exist_ok=True)
        ext = file.filename.rsplit(".", 1)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"error": "invalid file type"}), 400

        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(app.config['IMAGE_FOLDER'], unique_filename)
        file.save(file_path)
        size = os.path.getsize(file_path)
        stored_filename = f"images/{unique_filename}"

        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": stored_filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        result = db.image_files.insert_one(metadata)
        metadata["_id"] = str(result.inserted_id)
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        metadata["url"] = generate_file_url(request.host_url, stored_filename)
        return jsonify({"msg": "image uploaded", "metadata": metadata}), 201

    @app.route("/images/<filename>", methods=["DELETE"])
    def delete_image(filename):
        stored_filename = f"images/{filename}"
        file_doc = db.image_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        file_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.image_files.delete_one({"stored_filename": stored_filename})
        return jsonify({"msg": "file deleted"})

    @app.route("/images/<filename>", methods=["PUT"])
    def update_image(filename):
        stored_filename = f"images/{filename}"
        file_doc = db.image_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        if "file" not in request.files or request.files["file"].filename == "":
            return jsonify({"error": "no file selected"}), 400
        file = request.files["file"]

        new_filename, _, size = save_file(file, app.config['IMAGE_FOLDER'], ALLOWED_IMAGE_EXTENSIONS)
        if not new_filename:
            return jsonify({"error": "invalid file type"}), 400

        old_file_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        new_stored_filename = f"images/{new_filename}"
        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": new_stored_filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        db.image_files.update_one({"_id": file_doc["_id"]}, {"$set": metadata})
        metadata["_id"] = str(file_doc["_id"])
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        metadata["url"] = generate_file_url(request.host_url, new_stored_filename)
        return jsonify({"msg": "image updated", "metadata": metadata})

    # ---------------- Excel ----------------
    @app.route("/excel", methods=["GET"])
    def list_excel():
        files = [format_metadata(f) for f in db.excel_files.find({})]
        for f in files:
            f["url"] = generate_file_url(request.host_url, f["stored_filename"])
        return jsonify({"files": files})

    @app.route("/excel/upload", methods=["POST"])
    def upload_excel():
        if "file" not in request.files or request.files["file"].filename == "":
            return jsonify({"error": "no file selected"}), 400
        file = request.files["file"]

        os.makedirs(app.config['EXCEL_FOLDER'], exist_ok=True)
        filename, _, size = save_file(file, app.config['EXCEL_FOLDER'], ALLOWED_EXCEL_EXTENSIONS)
        if not filename:
            return jsonify({"error": "invalid file type"}), 400

        stored_filename = f"excel/{filename}"
        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": stored_filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        result = db.excel_files.insert_one(metadata)
        metadata["_id"] = str(result.inserted_id)
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        metadata["url"] = generate_file_url(request.host_url, stored_filename)
        return jsonify({"msg": "excel uploaded", "metadata": metadata}), 201

    @app.route("/excel/view/<filename>", methods=["GET"])
    def view_excel(filename):
        file_path = os.path.join(app.config['EXCEL_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "file not found"}), 404
        df = pd.read_excel(file_path)
        return Response(df.to_html(), mimetype="text/html")

    @app.route("/excel/<filename>", methods=["DELETE"])
    def delete_excel(filename):
        stored_filename = f"excel/{filename}"
        file_doc = db.excel_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        file_path = os.path.join(app.config['EXCEL_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.excel_files.delete_one({"stored_filename": stored_filename})
        return jsonify({"msg": "file deleted"})

    @app.route("/excel/<filename>", methods=["PUT"])
    def update_excel(filename):
        stored_filename = f"excel/{filename}"
        file_doc = db.excel_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        if "file" not in request.files or request.files["file"].filename == "":
            return jsonify({"error": "no file selected"}), 400
        file = request.files["file"]

        new_filename, _, size = save_file(file, app.config['EXCEL_FOLDER'], ALLOWED_EXCEL_EXTENSIONS)
        if not new_filename:
            return jsonify({"error": "invalid file type"}), 400

        old_file_path = os.path.join(app.config['EXCEL_FOLDER'], filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        new_stored_filename = f"excel/{new_filename}"
        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": new_stored_filename,
            "content_type": file.content_type,
            "size": size,
            "upload_date": datetime.utcnow()
        }
        db.excel_files.update_one({"_id": file_doc["_id"]}, {"$set": metadata})
        metadata["_id"] = str(file_doc["_id"])
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        metadata["url"] = generate_file_url(request.host_url, new_stored_filename)
        return jsonify({"msg": "excel updated", "metadata": metadata})

    # ---------------- JSON ----------------
    @app.route("/json", methods=["GET"])
    def list_json():
        files = [format_metadata(f) for f in db.json_files.find({}, {"data": 0})]
        for f in files:
            f["url"] = generate_file_url(request.host_url, f["stored_filename"])
        return jsonify({"files": files})

    @app.route("/json/upload", methods=["POST"])
    def upload_json():
        if "file" not in request.files or request.files["file"].filename == "":
            return jsonify({"error": "no file selected"}), 400
        file = request.files["file"]
        if not allowed_file(file.filename, ALLOWED_JSON_EXTENSIONS):
            return jsonify({"error": "invalid file type"}), 400

        os.makedirs(app.config['JSON_FOLDER'], exist_ok=True)
        unique_filename = f"{uuid.uuid4().hex}.json"
        file_path = os.path.join(app.config['JSON_FOLDER'], unique_filename)
        file.save(file_path)

        try:
            with open(file_path) as f:
                data = json.load(f)
        except Exception:
            os.remove(file_path)
            return jsonify({"error": "invalid JSON file"}), 400

        stored_filename = f"json/{unique_filename}"
        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": stored_filename,
            "data": data,
            "upload_date": datetime.utcnow()
        }
        result = db.json_files.insert_one(metadata)
        metadata["_id"] = str(result.inserted_id)
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        del metadata["data"]
        metadata["url"] = generate_file_url(request.host_url, stored_filename)
        return jsonify({"msg": "JSON uploaded", "metadata": metadata}), 201

    @app.route("/json/view/<filename>", methods=["GET"])
    def view_json(filename):
        stored_filename = f"json/{filename}"
        file_doc = db.json_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        return jsonify(format_metadata(file_doc, include_data=True))

    @app.route("/json/<filename>", methods=["DELETE"])
    def delete_json(filename):
        stored_filename = f"json/{filename}"
        file_doc = db.json_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        file_path = os.path.join(app.config['JSON_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.json_files.delete_one({"stored_filename": stored_filename})
        return jsonify({"msg": "file deleted"})

    @app.route("/json/<filename>", methods=["PUT"])
    def update_json(filename):
        stored_filename = f"json/{filename}"
        file_doc = db.json_files.find_one({"stored_filename": stored_filename})
        if not file_doc:
            return jsonify({"error": "file not found"}), 404
        if "file" not in request.files or request.files["file"].filename == "":
            return jsonify({"error": "no file selected"}), 400
        file = request.files["file"]
        if not allowed_file(file.filename, ALLOWED_JSON_EXTENSIONS):
            return jsonify({"error": "invalid file type"}), 400

        old_file_path = os.path.join(app.config['JSON_FOLDER'], filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        unique_filename = f"{uuid.uuid4().hex}.json"
        new_file_path = os.path.join(app.config['JSON_FOLDER'], unique_filename)
        file.save(new_file_path)

        try:
            with open(new_file_path) as f:
                data = json.load(f)
        except Exception:
            os.remove(new_file_path)
            return jsonify({"error": "invalid JSON file"}), 400

        new_stored_filename = f"json/{unique_filename}"
        metadata = {
            "original_filename": secure_filename(file.filename),
            "stored_filename": new_stored_filename,
            "data": data,
            "upload_date": datetime.utcnow()
        }
        db.json_files.update_one({"_id": file_doc["_id"]}, {"$set": metadata})
        metadata["_id"] = str(file_doc["_id"])
        metadata["upload_date"] = metadata["upload_date"].isoformat()
        del metadata["data"]
        metadata["url"] = generate_file_url(request.host_url, new_stored_filename)
        return jsonify({"msg": "JSON updated", "metadata": metadata})
