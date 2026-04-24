from datetime import datetime

from bson import ObjectId
from mongo_client import charts_collection


def save_chart(
    username: str,
    question: str,
    generated_code: str,
    raw_model_output: str,
    candidate_cols: dict,
    png_bytes: bytes,
    jpeg_bytes: bytes | None = None,
    pdf_bytes: bytes | None = None,
    original_filename: str | None = None,
):
    doc = {
        "username": username,
        "created_at": datetime.utcnow(),
        "question": question,
        "generated_code": generated_code,
        "raw_model_output": raw_model_output,
        "candidate_cols": candidate_cols,
        "original_filename": original_filename,
        "png_bytes": png_bytes,
        "jpeg_bytes": jpeg_bytes,
        "pdf_bytes": pdf_bytes,
        "download_png_count": 0,
        "download_jpeg_count": 0,
        "download_pdf_count": 0,
    }
    result = charts_collection.insert_one(doc)
    return str(result.inserted_id)


def get_user_charts(username: str):
    return list(charts_collection.find({"username": username}).sort("created_at", -1))


def delete_chart(chart_id: str, username: str):
    charts_collection.delete_one({
        "_id": ObjectId(chart_id),
        "username": username
    })

def increment_download_count(chart_id: str, fmt: str):
    field_map = {
        "png": "download_png_count",
        "jpeg": "download_jpeg_count",
        "pdf": "download_pdf_count",
    }

    field = field_map.get(fmt)
    if not field:
        return

    charts_collection.update_one(
        {"_id": ObjectId(chart_id)},
        {"$inc": {field: 1}}
    )