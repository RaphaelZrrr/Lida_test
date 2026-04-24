import streamlit as st
import pandas as pd

from auth_repository import get_user_by_username
from dashboard_repository import get_dashboard_stats


st.set_page_config(page_title="Dashboard global", layout="wide")

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("Veuillez vous connecter depuis l'application principale.")
    st.stop()

username = st.session_state["username"]
user = get_user_by_username(username)

if not user:
    st.error("Utilisateur introuvable.")
    st.stop()

allowed_admin_id = "69e88d4aef0f338958e9b1ed"

if str(user["_id"]) != allowed_admin_id:
    st.error("Accès refusé.")
    st.stop()

st.title("Dashboard global")
st.caption(f"Vue globale — accès autorisé pour {username}")

stats = get_dashboard_stats(username)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Utilisateurs", stats["total_users"])
with c2:
    st.metric("Graphes totaux", stats["total_charts"])
with c3:
    st.metric("Mes graphes", stats["user_charts"])

c4, c5, c6 = st.columns(3)
with c4:
    st.metric("Downloads PNG", stats["total_png_downloads"])
with c5:
    st.metric("Downloads JPEG", stats["total_jpeg_downloads"])
with c6:
    st.metric("Downloads PDF", stats["total_pdf_downloads"])

st.divider()

st.subheader("Utilisateurs les plus actifs")
top_users = stats["top_users"]
if top_users:
    df_top = pd.DataFrame(
        [{"username": row["_id"], "chart_count": row["chart_count"]} for row in top_users]
    )
    st.dataframe(df_top, use_container_width=True)
    st.bar_chart(df_top.set_index("username"))
else:
    st.info("Aucune donnée.")

st.subheader("Derniers graphes générés")
recent_charts = stats["recent_charts"]
if recent_charts:
    df_recent = pd.DataFrame(
        [
            {
                "username": row.get("username"),
                "question": row.get("question"),
                "created_at": row.get("created_at"),
                "png_downloads": row.get("download_png_count", 0),
                "jpeg_downloads": row.get("download_jpeg_count", 0),
                "pdf_downloads": row.get("download_pdf_count", 0),
            }
            for row in recent_charts
        ]
    )
    st.dataframe(df_recent, use_container_width=True)
else:
    st.info("Aucun graphe enregistré.")