from mongo_client import users_collection, charts_collection


print("=== USERS ===")
for user in users_collection.find({}, {"username": 1, "created_at": 1}):
    print(
        {
            "id": str(user.get("_id")),
            "username": user.get("username"),
            "created_at": user.get("created_at"),
        }
    )

print("\n=== Graphes ===")
for chart in charts_collection.find(
    {},
    {
        "username": 1,
        "question": 1,
        "created_at": 1,
        "original_filename": 1,
        "download_png_count": 1,
        "download_jpeg_count": 1,
        "download_pdf_count": 1,
    },
):
    print(
        {
            "id": str(chart.get("_id")),
            "username": chart.get("username"),
            "question": chart.get("question"),
            "created_at": chart.get("created_at"),
            "original_filename": chart.get("original_filename"),
            "download_png_count": chart.get("download_png_count", 0),
            "download_jpeg_count": chart.get("download_jpeg_count", 0),
            "download_pdf_count": chart.get("download_pdf_count", 0),
        }
    )