"""
Hostal Ukumari - Sistema de Registro de Huéspedes
Stack: Streamlit + Supabase (mismo patrón que Sistema Maldini)
"""

import streamlit as st
from supabase import create_client, Client
from datetime import date
import pandas as pd

# ---------------------------------------------------------------------------
# Configuración inicial
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Hostal Ukumari - Registro",
    page_icon="🏔️",
    layout="wide",
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_client()

# ---------------------------------------------------------------------------
# Sidebar / navegación
# ---------------------------------------------------------------------------
st.sidebar.title("🏔️ Hostal Ukumari")
pagina = st.sidebar.radio("Menú", ["Registrar huésped", "Ver huéspedes"])

# ---------------------------------------------------------------------------
# Página 1: Registrar huésped
# ---------------------------------------------------------------------------
if pagina == "Registrar huésped":
    st.title("Registro de huésped")

    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Nombre completo *")
            tipo_documento = st.selectbox("Tipo de documento *", ["Cédula", "Pasaporte"])
            numero_documento = st.text_input("Número de documento *")
            nacionalidad = st.text_input("Nacionalidad *", value="Ecuador")

        with col2:
            telefono = st.text_input("Teléfono")
            email = st.text_input("Email")
            numero_personas = st.number_input("Número de personas", min_value=1, value=1, step=1)
            habitacion = st.text_input("Habitación / cabaña")

        col3, col4 = st.columns(2)
        with col3:
            fecha_checkin = st.date_input("Fecha check-in *", value=date.today())
        with col4:
            fecha_checkout = st.date_input("Fecha check-out (estimada)", value=None)

        notas = st.text_area("Notas (alergias, pedidos especiales, etc.)")

        submitted = st.form_submit_button("Registrar huésped", use_container_width=True)

        if submitted:
            if not nombre or not numero_documento:
                st.error("Nombre y número de documento son obligatorios.")
            else:
                data = {
                    "nombre": nombre,
                    "tipo_documento": tipo_documento,
                    "numero_documento": numero_documento,
                    "nacionalidad": nacionalidad,
                    "telefono": telefono or None,
                    "email": email or None,
                    "numero_personas": int(numero_personas),
                    "habitacion": habitacion or None,
                    "fecha_checkin": str(fecha_checkin),
                    "fecha_checkout": str(fecha_checkout) if fecha_checkout else None,
                    "notas": notas or None,
                }
                try:
                    supabase.table("huespedes").insert(data).execute()
                    st.success(f"✅ Huésped '{nombre}' registrado correctamente.")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")

# ---------------------------------------------------------------------------
# Página 2: Ver huéspedes
# ---------------------------------------------------------------------------
elif pagina == "Ver huéspedes":
    st.title("Huéspedes registrados")

    busqueda = st.text_input("🔍 Buscar por nombre o documento")

    try:
        query = supabase.table("huespedes").select("*").order("creado_en", desc=True)
        response = query.execute()
        df = pd.DataFrame(response.data)

        if not df.empty:
            if busqueda:
                mask = (
                    df["nombre"].str.contains(busqueda, case=False, na=False)
                    | df["numero_documento"].str.contains(busqueda, case=False, na=False)
                )
                df = df[mask]

            columnas_mostrar = [
                "nombre", "tipo_documento", "numero_documento", "nacionalidad",
                "numero_personas", "habitacion", "fecha_checkin", "fecha_checkout",
            ]
            st.dataframe(df[columnas_mostrar], use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            col1.metric("Total huéspedes", len(df))
            col2.metric("Personas hoy", df[df["fecha_checkin"] == str(date.today())]["numero_personas"].sum())
            col3.metric("Nacionalidades distintas", df["nacionalidad"].nunique())
        else:
            st.info("Todavía no hay huéspedes registrados.")

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
