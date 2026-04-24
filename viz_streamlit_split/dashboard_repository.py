from mongo_client import users_collection, charts_collection


def get_dashboard_stats(current_username: str):
    total_users = users_collection.count_documents({})
    total_charts = charts_collection.count_documents({})
    user_charts = charts_collection.count_documents({"username": current_username})

    pipeline_top_users = [
        {"$group": {"_id": "$username", "chart_count": {"$sum": 1}}},
        {"$sort": {"chart_count": -1}},
        {"$limit": 10},
    ]
    top_users = list(charts_collection.aggregate(pipeline_top_users))

    pipeline_recent_charts = [
        {"$sort": {"created_at": -1}},
        {"$limit": 10},
        {
            "$project": {
                "username": 1,
                "question": 1,
                "created_at": 1,
                "download_png_count": 1,
                "download_jpeg_count": 1,
                "download_pdf_count": 1,
            }
        },
    ]
    recent_charts = list(charts_collection.aggregate(pipeline_recent_charts))

    pipeline_downloads = [
        {
            "$group": {
                "_id": None,
                "total_png": {"$sum": "$download_png_count"},
                "total_jpeg": {"$sum": "$download_jpeg_count"},
                "total_pdf": {"$sum": "$download_pdf_count"},
            }
        }
    ]
    downloads_result = list(charts_collection.aggregate(pipeline_downloads))

    if downloads_result:
        downloads = downloads_result[0]
    else:
        downloads = {"total_png": 0, "total_jpeg": 0, "total_pdf": 0}

    return {
        "total_users": total_users,
        "total_charts": total_charts,
        "user_charts": user_charts,
        "total_png_downloads": downloads.get("total_png", 0),
        "total_jpeg_downloads": downloads.get("total_jpeg", 0),
        "total_pdf_downloads": downloads.get("total_pdf", 0),
        "top_users": top_users,
        "recent_charts": recent_charts,
    }