import streamlit as st

from dashboard_user_repository import (
    create_user_dashboard,
    get_user_dashboards,
    get_user_dashboard_by_id,
    update_user_dashboard,
    delete_user_dashboard,
    get_dashboard_charts,
    get_user_chart_choices,
)
from dashboard_export_utils import build_dashboard_exports


st.set_page_config(page_title="Mes dashboards", layout="wide")

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("Veuillez vous connecter depuis l'application principale.")
    st.stop()

username = st.session_state["username"]

st.title("Mes dashboards utilisateur")

tab1, tab2 = st.tabs(["Créer / modifier", "Voir mes dashboards"])


def format_dt(dt):
    if not dt:
        return ""
    return str(dt)


with tab1:
    st.subheader("Créer ou modifier un dashboard")

    existing_dashboards = get_user_dashboards(username)
    mode = st.radio("Mode", ["Créer un nouveau dashboard", "Modifier un dashboard existant"], horizontal=True)

    selected_dashboard = None
    selected_dashboard_id = None

    if mode == "Modifier un dashboard existant":
        if not existing_dashboards:
            st.info("Vous n'avez encore aucun dashboard.")
            st.stop()

        options = {
            f"{d.get('title', 'Sans titre')} — {str(d['_id'])[:8]}": str(d["_id"])
            for d in existing_dashboards
        }
        selected_label = st.selectbox("Choisir un dashboard", list(options.keys()))
        selected_dashboard_id = options[selected_label]
        selected_dashboard = get_user_dashboard_by_id(selected_dashboard_id, username)

    all_user_charts = get_user_chart_choices(username)

    if not all_user_charts:
        st.info("Vous n'avez encore aucun graphe dans votre historique.")
    else:
        default_title = selected_dashboard.get("title", "") if selected_dashboard else ""
        default_layout = selected_dashboard.get("layout", "vertical") if selected_dashboard else "vertical"
        existing_ids = [str(x) for x in selected_dashboard.get("chart_ids", [])] if selected_dashboard else []

        title = st.text_input("Titre du dashboard", value=default_title)
        layout = st.selectbox(
            "Disposition",
            ["vertical", "2_columns"],
            index=0 if default_layout == "vertical" else 1,
            format_func=lambda x: "Vertical" if x == "vertical" else "2 colonnes"
        )

        st.markdown("### Sélection des graphes")
        st.caption("Choisis les graphes à inclure, puis définis leur ordre.")

        selections = []

        for i, chart in enumerate(all_user_charts):
            chart_id = str(chart["_id"])
            checked_default = chart_id in existing_ids

            c1, c2 = st.columns([0.65, 0.35])

            with c1:
                checked = st.checkbox(
                    f"{chart.get('question', 'Sans question')} — {format_dt(chart.get('created_at'))}",
                    value=checked_default,
                    key=f"chart_select_{chart_id}",
                )

            with c2:
                default_order = existing_ids.index(chart_id) + 1 if chart_id in existing_ids else i + 1
                order = st.number_input(
                    f"Ordre {chart_id[:6]}",
                    min_value=1,
                    max_value=999,
                    value=default_order,
                    step=1,
                    key=f"chart_order_{chart_id}",
                    label_visibility="collapsed",
                )

            if checked:
                selections.append((order, chart_id, chart))

        if selections:
            st.markdown("### Aperçu des graphes sélectionnés")
            ordered = sorted(selections, key=lambda x: x[0])
            for _, _, chart in ordered:
                st.write(chart.get("question", ""))
                if chart.get("png_bytes"):
                    st.image(chart["png_bytes"], width=500)

        if mode == "Créer un nouveau dashboard":
            if st.button("Créer le dashboard", type="primary"):
                if not title.strip():
                    st.error("Veuillez saisir un titre.")
                elif not selections:
                    st.error("Veuillez sélectionner au moins un graphe.")
                else:
                    ordered_ids = [chart_id for _, chart_id, _ in sorted(selections, key=lambda x: x[0])]
                    create_user_dashboard(username, title, ordered_ids, layout)
                    st.success("Dashboard créé.")
                    st.rerun()

        else:
            c1, c2 = st.columns(2)

            with c1:
                if st.button("Enregistrer les modifications", type="primary"):
                    if not title.strip():
                        st.error("Veuillez saisir un titre.")
                    elif not selections:
                        st.error("Veuillez sélectionner au moins un graphe.")
                    else:
                        ordered_ids = [chart_id for _, chart_id, _ in sorted(selections, key=lambda x: x[0])]
                        update_user_dashboard(selected_dashboard_id, username, title, ordered_ids, layout)
                        st.success("Dashboard mis à jour.")
                        st.rerun()

            with c2:
                if st.button("Supprimer ce dashboard"):
                    delete_user_dashboard(selected_dashboard_id, username)
                    st.success("Dashboard supprimé.")
                    st.rerun()


with tab2:
    st.subheader("Voir mes dashboards")

    dashboards = get_user_dashboards(username)

    if not dashboards:
        st.info("Aucun dashboard enregistré.")
    else:
        options = {
            f"{d.get('title', 'Sans titre')} — {str(d['_id'])[:8]}": str(d["_id"])
            for d in dashboards
        }

        selected_label = st.selectbox("Choisir un dashboard à afficher", list(options.keys()), key="view_dashboard_select")
        dashboard_id = options[selected_label]
        dashboard = get_user_dashboard_by_id(dashboard_id, username)

        if not dashboard:
            st.error("Dashboard introuvable.")
            st.stop()

        title = dashboard.get("title", "Sans titre")
        layout = dashboard.get("layout", "vertical")

        st.markdown(f"## {title}")
        st.caption(f"Créé / modifié par {username}")

        charts = get_dashboard_charts(dashboard)

        if not charts:
            st.info("Ce dashboard ne contient aucun graphe.")
        else:
            chart_png_list = [c.get("png_bytes") for c in charts if c.get("png_bytes")]

            if chart_png_list:
                dashboard_png, dashboard_jpeg, dashboard_pdf = build_dashboard_exports(title, chart_png_list, layout)

                e1, e2, e3 = st.columns(3)
                with e1:
                    st.download_button(
                        "Télécharger PNG",
                        data=dashboard_png,
                        file_name=f"{title}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                with e2:
                    st.download_button(
                        "Télécharger JPEG",
                        data=dashboard_jpeg,
                        file_name=f"{title}.jpeg",
                        mime="image/jpeg",
                        use_container_width=True,
                    )
                with e3:
                    st.download_button(
                        "Télécharger PDF",
                        data=dashboard_pdf,
                        file_name=f"{title}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

            st.divider()

            if layout == "2_columns":
                for i in range(0, len(charts), 2):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(charts[i].get("question", ""))
                        if charts[i].get("png_bytes"):
                            st.image(charts[i]["png_bytes"], use_container_width=True)
                    if i + 1 < len(charts):
                        with col2:
                            st.write(charts[i + 1].get("question", ""))
                            if charts[i + 1].get("png_bytes"):
                                st.image(charts[i + 1]["png_bytes"], use_container_width=True)
            else:
                for chart in charts:
                    st.write(chart.get("question", ""))
                    if chart.get("png_bytes"):
                        st.image(chart["png_bytes"], use_container_width=True)
                    st.markdown("---")