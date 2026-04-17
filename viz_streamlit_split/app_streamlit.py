import traceback
from typing import Optional

import pandas as pd
import streamlit as st

from chart_generator import generate_chart
from config import DEFAULT_MODEL, DEFAULT_OLLAMA_BASE_URL, DEFAULT_TEMPERATURE
from data_loader import load_csv_bytes, load_jsonl_bytes


st.set_page_config(page_title="LLM Viz (Light)", layout="wide")

st.title("LLM Viz — Version Light")
st.caption("")

with st.sidebar:
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
            except Exception as e:
                st.error(f"Echec de l'appel au llm: {e}")
                result = {
                    "error": traceback.format_exc(),
                    "code": "",
                    "png_bytes": None,
                    "candidate_cols": None,
                    "raw_model_output": "",
                }

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

        st.subheader("4) Code généré")
        st.code(result.get("code", ""), language="python")

        if show_raw:
            with st.expander("Output"):
                st.code(result.get("raw_model_output", ""), language="text")

    st.divider()
    st.caption("Température = 0 conseillé + Éviter les prompts trop longs.")