import traceback
from typing import Optional

import pandas as pd
import streamlit as st

from chart_generator import generate_chart
from config import DEFAULT_MODEL, DEFAULT_OLLAMA_BASE_URL, DEFAULT_TEMPERATURE
from data_loader import load_csv_bytes, load_jsonl_bytes
from export_utils import png_bytes_to_jpeg_bytes, png_bytes_to_pdf_bytes

from auth_repository import create_user, authenticate_user
from chart_repository import save_chart, get_user_charts
from export_utils import png_bytes_to_jpeg_bytes, png_bytes_to_pdf_bytes

from chart_repository import increment_download_count

from code_executor import exec_code_to_png


st.set_page_config(page_title="LLM Viz (Light)", layout="wide")

if "last_chart_id" not in st.session_state:
    st.session_state["last_chart_id"] = None

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "username" not in st.session_state:
    st.session_state["username"] = None

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

if "editable_code" not in st.session_state:
    st.session_state["editable_code"] = ""

if "editable_code_area" not in st.session_state:
    st.session_state["editable_code_area"] = ""

if "current_df" not in st.session_state:
    st.session_state["current_df"] = None

if not st.session_state["authenticated"]:
    st.title("Connexion")

    tab1, tab2 = st.tabs(["Se connecter", "S'inscrire"])

    with tab1:
        login_username = st.text_input("Nom d'utilisateur", key="login_username")
        login_password = st.text_input("Mot de passe", type="password", key="login_password")

        if st.button("Connexion"):
            if authenticate_user(login_username, login_password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = login_username
                st.rerun()
            else:
                st.error("Identifiants invalides.")

    with tab2:
        register_username = st.text_input("Nouveau nom d'utilisateur", key="register_username")
        register_password = st.text_input("Nouveau mot de passe", type="password", key="register_password")

        if st.button("Créer le compte"):
            ok, msg = create_user(register_username, register_password)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.stop()

if "last_df_loaded" not in st.session_state:
    st.session_state["last_df_loaded"] = False

st.title("LLM Viz — Version Light")
st.caption("")

with st.sidebar:

    st.write(f"Connecté en tant que : {st.session_state['username']}")

    if st.button("Se déconnecter"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["last_result"] = None
        st.rerun()

    st.subheader("Connexion LLM")
    base_url = st.text_input("Ollama base URL", value=DEFAULT_OLLAMA_BASE_URL)
    model_name = st.text_input("Model", value=DEFAULT_MODEL)
    temperature = st.slider("Temperature", 0.0, 0.9, float(DEFAULT_TEMPERATURE), 0.05)

    st.subheader("Données")
    sample_rows_jsonl = 50000
    sample_n_schema = st.number_input(
        "Nombre de lignes pour sample du schema",
        min_value=100,
        max_value=20000,
        value=800,
        step=100,
    )
    max_each_candidates = st.number_input(
        "Max de colonnes candidates",
        min_value=10,
        max_value=200,
        value=25,
        step=5,
    )

    st.subheader("Affichage")
    show_raw = st.checkbox("Afficher la réponse brute du modèle", value=False)
    show_schema = st.checkbox("Afficher colonnes candidates", value=True)
    show_columns = st.checkbox("Montrer toutes les colonnes", value=False)

col_left, col_right = st.columns([1.0, 1.2], gap="large")

with col_left:
    st.subheader("1) Upload")
    uploaded = st.file_uploader("CSV ou JSONL", type=["csv", "jsonl", "log", "txt"])
    df: Optional[pd.DataFrame] = None
    file_info = None

    if uploaded is not None:
        data_bytes = uploaded.getvalue()
        name = uploaded.name.lower()
        file_info = (uploaded.name, len(data_bytes))

        try:
            if name.endswith(".csv"):
                df = load_csv_bytes(data_bytes)
            else:
                df = load_jsonl_bytes(data_bytes, sample_rows=int(sample_rows_jsonl))

            st.session_state["current_df"] = df    
            st.success(f"Loaded {uploaded.name} — shape: {df.shape}")
        except Exception as e:
            st.error(f"Echec de chargement du fichier: {e}")
            df = None

    if df is not None and show_columns:
        with st.expander("Colonness"):
            st.write(list(df.columns))

with col_right:
    st.subheader("2) Prompt")
    default_prompt = "Ecrivez votre prompt"
    question = st.text_area("Question (FR)", value=default_prompt, height=120)

    cta_col1, cta_col2 = st.columns([1, 1])
    with cta_col1:
        run_btn = st.button("Générer", type="primary", use_container_width=True, disabled=(df is None))
    with cta_col2:
        st.button("Reset", use_container_width=True, on_click=lambda: st.session_state.clear())

    if run_btn and df is not None:
        with st.spinner("Génération du code + exécution..."):
            try:
                result = generate_chart(
                    df=df,
                    question=question,
                    base_url=base_url,
                    model=model_name,
                    temperature=float(temperature),
                    sample_n_schema=int(sample_n_schema),
                    max_each_candidates=int(max_each_candidates),
                )
                st.session_state["last_result"] = result

                new_code = result.get("code", "")
                st.session_state["editable_code"] = new_code
                st.session_state["editable_code_area"] = new_code
                
            except Exception as e:
                st.error(f"Echec de l'appel au llm: {e}")
                st.session_state["last_result"] = {
                    "error": traceback.format_exc(),
                    "code": "",
                    "png_bytes": None,
                    "candidate_cols": None,
                    "raw_model_output": "",
                }

    result = st.session_state.get("last_result")

    if result:
        if result.get("candidate_cols") and show_schema:
            with st.expander("Colonnes candidates (cat / num / time)", expanded=False):
                st.write(result["candidate_cols"])

        if result.get("error"):
            st.error("Erreur d'execution")
            with st.expander("Traceback", expanded=True):
                st.code(result["error"], language="text")

        if result.get("png_bytes"):
            st.subheader("3) Graphe")
            st.image(result["png_bytes"], width=1200)

            png_bytes = result["png_bytes"]
            jpeg_bytes = png_bytes_to_jpeg_bytes(png_bytes)
            pdf_bytes = png_bytes_to_pdf_bytes(png_bytes)

            chart_id = save_chart(
                username=st.session_state["username"],
                question=question,
                generated_code=result.get("code", ""),
                raw_model_output=result.get("raw_model_output", ""),
                candidate_cols=result.get("candidate_cols", {}),
                png_bytes=png_bytes,
                jpeg_bytes=jpeg_bytes,
                pdf_bytes=pdf_bytes,
                original_filename=uploaded.name if uploaded else None,
            )

            st.session_state["last_chart_id"] = chart_id

            dl1, dl2, dl3 = st.columns(3)

            with dl1:
                if st.download_button(
                    "Télécharger PNG",
                    data=png_bytes,
                    file_name="graph.png",
                    mime="image/png",
                    use_container_width=True,
                ) and chart_id:
                    increment_download_count(chart_id, "png")

            with dl2:
                if st.download_button(
                    "Télécharger JPEG",
                    data=jpeg_bytes,
                    file_name="graph.jpeg",
                    mime="image/jpeg",
                    use_container_width=True,
                ) and chart_id:
                    increment_download_count(chart_id, "jpeg")

            with dl3:
                if st.download_button(
                    "Télécharger PDF",
                    data=pdf_bytes,
                    file_name="graph.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                ) and chart_id:
                    increment_download_count(chart_id, "pdf")

        st.subheader("4) Code généré / modifiable")

        edited_code = st.text_area(
            "Code Python",
            height=300,
            key="editable_code_area",
        )

        st.session_state["editable_code"] = edited_code

        run_code_btn = st.button("Exécuter le code modifié", use_container_width=True)


        if run_code_btn:
            current_df = st.session_state.get("current_df")

            if current_df is None:
                st.error("Aucun dataset chargé.")
            else:
                with st.spinner("Exécution du code modifié..."):
                    png_bytes, tb = exec_code_to_png(st.session_state["editable_code"], current_df)

                if tb:
                    st.error("Erreur d'exécution du code modifié")
                    with st.expander("Traceback du code modifié", expanded=True):
                        st.code(tb, language="text")
                else:
                    st.success("Code modifié exécuté avec succès.")

                    if "last_result" not in st.session_state or st.session_state["last_result"] is None:
                        st.session_state["last_result"] = {}

                    st.session_state["last_result"]["png_bytes"] = png_bytes
                    st.session_state["last_result"]["error"] = None
                    st.session_state["last_result"]["code"] = st.session_state["editable_code"]

                    st.rerun()

        if show_raw:
            with st.expander("Output"):
                st.code(result.get("raw_model_output", ""), language="text")

    st.divider()

    with st.expander("Historique de mes graphes", expanded=False):
        history = get_user_charts(st.session_state["username"])

        if not history:
            st.write("Aucun graphe enregistré.")
        else:
            for item in history:
                st.markdown("---")
                st.write("Date :", item.get("created_at"))
                st.write("Question :", item.get("question", ""))

                if item.get("png_bytes"):
                    st.image(item["png_bytes"], width=500)

                st.download_button(
                    "Télécharger PNG",
                    data=item["png_bytes"],
                    file_name="graph.png",
                    mime="image/png",
                    key=f"hist_png_{item['_id']}",
                )

                if item.get("jpeg_bytes"):
                    st.download_button(
                        "Télécharger JPEG",
                        data=item["jpeg_bytes"],
                        file_name="graph.jpeg",
                        mime="image/jpeg",
                        key=f"hist_jpeg_{item['_id']}",
                    )

                if item.get("pdf_bytes"):
                    st.download_button(
                        "Télécharger PDF",
                        data=item["pdf_bytes"],
                        file_name="graph.pdf",
                        mime="application/pdf",
                        key=f"hist_pdf_{item['_id']}",
                    )
    
    st.caption("Température = 0 conseillé + Éviter les prompts trop longs.")