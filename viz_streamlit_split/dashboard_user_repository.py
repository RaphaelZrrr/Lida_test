from bson import ObjectId

from mongo_client import dashboards_collection, charts_collection


def create_user_dashboard(username: str, title: str, chart_ids: list[str], layout: str = "vertical"):
    doc = {
        "username": username,
        "title": title.strip(),
        "layout": layout,
        "chart_ids": [ObjectId(cid) for cid in chart_ids],
    }
    result = dashboards_collection.insert_one(doc)
    return str(result.inserted_id)


def get_user_dashboards(username: str):
    return list(
        dashboards_collection.find({"username": username})
    )


def get_user_dashboard_by_id(dashboard_id: str, username: str):
    return dashboards_collection.find_one(
        {"_id": ObjectId(dashboard_id), "username": username}
    )


def update_user_dashboard(dashboard_id: str, username: str, title: str, chart_ids: list[str], layout: str):
    dashboards_collection.update_one(
        {"_id": ObjectId(dashboard_id), "username": username},
        {
            "$set": {
                "title": title.strip(),
                "layout": layout,
                "chart_ids": [ObjectId(cid) for cid in chart_ids],
            }
        },
    )


def delete_user_dashboard(dashboard_id: str, username: str):
    dashboards_collection.delete_one(
        {"_id": ObjectId(dashboard_id), "username": username}
    )


def get_dashboard_charts(dashboard_doc):
    chart_ids = dashboard_doc.get("chart_ids", [])
    if not chart_ids:
        return []

    charts = list(charts_collection.find({"_id": {"$in": chart_ids}}))

    order_map = {cid: i for i, cid in enumerate(chart_ids)}
    charts.sort(key=lambda c: order_map.get(c["_id"], 10**9))
    return charts


def get_user_chart_choices(username: str):
    charts = list(
        charts_collection.find({"username": username})
    )
    return charts