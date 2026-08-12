"""
Sistema Maldini - Trading Journal (Streamlit + Supabase)
-----------------------------------------------------------
App web para registrar operaciones y ver estadísticas en tiempo real,
más el checklist de 8 pasos (SMC) como capa de apoyo a la decisión.

Correr localmente:
    pip install streamlit pandas supabase requests
    Crea .streamlit/secrets.toml con SUPABASE_URL y SUPABASE_KEY
    (opcional) N8N_WEBHOOK_URL si ya tienes el webhook de n8n listo
    streamlit run app.py
"""

from datetime import datetime

import pandas as pd
import streamlit as st
from supabase import create_client

try:
    import requests
except ImportError:
    requests = None

FIELDS = [
    "id", "fecha", "par", "direccion", "sesion", "bias_htf", "tf_entrada",
    "entrada", "stop_loss", "take_profit", "salida", "riesgo_pct",
    "pips_riesgo", "pips_resultado", "r_multiplo", "resultado",
    "contexto_smc", "razon_entrada", "se_siguio_plan", "estado_emocional", "notas",
]

PARES = ["EURUSD", "XAUUSD", "NAS100", "Otro"]
SESIONES = ["Londres", "NY", "Asia", "Londres-NY overlap", "Otro"]

# ---------- Checklist Sistema Maldini (8 pasos + 2 filtros de confirmación) ----------
CHECKLIST_ITEMS = [
    ("estructura_1d", "1. Estructura 1D definida"),
    ("h4_retroceso", "2. H4 en retroceso hacia zona de interés"),
    ("patron_wm", "3. Patrón W/M identificado"),
    ("sale_canal", "4. Sale de canal"),
    ("linea_tendencia", "5. Rompe línea de tendencia"),
    ("linea_engano", "6. Línea de engaño confirmada"),
    ("sale_canal_engano", "7. Sale de canal de engaño"),
    ("liquidity_sweep", "8. Liquidity sweep confirmado"),
    ("fvg_identificado", "9. FVG identificado"),
    ("rr_1_2", "10. RR mínimo 1:2 disponible"),
]

st.set_page_config(page_title="Sistema Maldini - Trading Journal", layout="wide")


@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_client()


def pip_size(par):
    if par.upper() == "XAUUSD":
        return 0.1
    if par.upper() == "NAS100":
        return 1.0
    return 0.0001


def calcular_r(par, direccion, entrada, sl, salida):
    pip = pip_size(par)
    if direccion == "long":
        pips_riesgo = (entrada - sl) / pip
        pips_resultado = (salida - entrada) / pip
    else:
        pips_riesgo = (sl - entrada) / pip
        pips_resultado = (entrada - salida) / pip

    pips_riesgo = abs(pips_riesgo)
    r = pips_resultado / pips_riesgo if pips_riesgo != 0 else 0
    return round(pips_riesgo, 1), round(pips_resultado, 1), round(r, 2)


def load_trades():
    response = supabase.table("trades").select("*").order("id", desc=False).execute()
    if not response.data:
        return pd.DataFrame(columns=FIELDS)
    return pd.DataFrame(response.data)


def append_trade(fila):
    fila = {k: v for k, v in fila.items() if k != "id"}
    supabase.table("trades").insert(fila).execute()


def delete_trade(trade_id):
    supabase.table("trades").delete().eq("id", int(trade_id)).execute()


def load_checklists():
    response = (
        supabase.table("checklist_estado").select("*").order("id", desc=True).execute()
    )
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def save_checklist(par, valores, score):
    fila = {"par": par, "score": score, "enviado_telegram": False}
    fila.update(valores)
    resp = supabase.table("checklist_estado").insert(fila).execute()
    if resp.data:
        return resp.data[0]["id"]
    return None


def marcar_enviado(checklist_id):
    supabase.table("checklist_estado").update({"enviado_telegram": True}).eq(
        "id", int(checklist_id)
    ).execute()


def load_alertas():
    response = (
        supabase.table("alertas_precio").select("*").order("id", desc=True).execute()
    )
    if not response.data:
        return pd.DataFrame()
    return pd.DataFrame(response.data)


def crear_alerta(par, nivel_precio, direccion, nota):
    fila = {
        "par": par,
        "nivel_precio": nivel_precio,
        "direccion": direccion,
        "nota": nota,
        "activa": True,
        "disparada": False,
    }
    supabase.table("alertas_precio").insert(fila).execute()


def eliminar_alerta(alerta_id):
    supabase.table("alertas_precio").delete().eq("id", int(alerta_id)).execute()


def desactivar_alerta(alerta_id):
    supabase.table("alertas_precio").update({"activa": False}).eq(
        "id", int(alerta_id)
    ).execute()


def enviar_a_n8n(payload):
    """Dispara el webhook de n8n si está configurado. Devuelve (ok, mensaje)."""
    webhook_url = st.secrets.get("N8N_WEBHOOK_URL", "")
    if not webhook_url:
        return False, "N8N_WEBHOOK_URL no configurado en secrets todavía."
    if requests is None:
        return False, "Falta instalar 'requests' (pip install requests)."
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        return True, "Enviado a n8n correctamente."
    except Exception as e:
        return False, f"Error al enviar a n8n: {e}"


# ---------- Header ----------
st.markdown(
    "<p style='color:#D4A24C; font-family:monospace; letter-spacing:2px; "
    "font-size:12px; margin-bottom:0;'>SISTEMA MALDINI</p>",
    unsafe_allow_html=True,
)
st.title("Trading journal")

tab_journal, tab_checklist, tab_alertas = st.tabs(
    ["📓 Journal", "✅ Checklist de setup", "🎯 Alertas de precio"]
)

# =====================================================================
# TAB 1: JOURNAL (igual que antes)
# =====================================================================
with tab_journal:
    df = load_trades()

    col1, col2, col3, col4 = st.columns(4)

    if len(df) > 0:
        total = len(df)
        wins = df[df["resultado"] == "WIN"]
        losses = df[df["resultado"] == "LOSS"]
        winrate = len(wins) / total * 100
        gain_sum = wins["r_multiplo"].sum()
        loss_sum = abs(losses["r_multiplo"].sum())
        pf = gain_sum / loss_sum if loss_sum > 0 else float("inf")
        expectancy = df["r_multiplo"].mean()

        col1.metric("Operaciones", total)
        col2.metric("Winrate", f"{winrate:.1f}%")
        col3.metric("Profit factor", f"{pf:.2f}" if pf != float("inf") else "∞")
        col4.metric("Expectancy", f"{expectancy:.2f} R")

        st.caption("Curva acumulada (R)")
        curva = df["r_multiplo"].cumsum()
        st.line_chart(curva, height=140)
    else:
        col1.metric("Operaciones", 0)
        col2.metric("Winrate", "—")
        col3.metric("Profit factor", "—")
        col4.metric("Expectancy", "—")
        st.info("Aún no registras operaciones. Tu primera entrada aparecerá aquí.")

    st.divider()

    layout_form, layout_log = st.columns([1, 1.4])

    with layout_form:
        st.subheader("Nueva operación")
        with st.form("nuevo_trade", clear_on_submit=True):
            par = st.selectbox("Par", PARES)
            if par == "Otro":
                par = st.text_input("Especifica el par")

            c1, c2 = st.columns(2)
            direccion = c1.selectbox("Dirección", ["long", "short"])
            sesion = c2.selectbox("Sesión", SESIONES)

            c3, c4 = st.columns(2)
            bias_htf = c3.text_input("Bias HTF (ej: H4 alcista)")
            tf_entrada = c4.text_input("Timeframe de entrada (ej: H1)")

            c5, c6 = st.columns(2)
            entrada = c5.number_input("Precio de entrada", format="%.5f")
            sl = c6.number_input("Stop loss", format="%.5f")

            c7, c8 = st.columns(2)
            tp = c7.number_input("Take profit (opcional)", format="%.5f", value=0.0)
            salida = c8.number_input("Precio de salida real", format="%.5f")

            riesgo_pct = st.number_input("Riesgo usado (% de la cuenta)", format="%.2f")
            contexto_smc = st.text_area("Contexto SMC (order block, FVG, liquidity grab...)")
            razon_entrada = st.text_area("Razón de entrada / setup")
            se_siguio_plan = st.selectbox("¿Se siguió el plan?", ["si", "no"])
            estado_emocional = st.select_slider(
                "Estado emocional (1 tranquilo — 5 ansioso/FOMO)",
                options=["1", "2", "3", "4", "5"],
            )
            notas = st.text_area("Notas / lecciones")

            enviado = st.form_submit_button("Guardar operación", use_container_width=True)

            if enviado:
                if entrada == 0 or sl == 0 or salida == 0:
                    st.error("Completa al menos entrada, stop loss y salida.")
                else:
                    pips_riesgo, pips_resultado, r = calcular_r(par, direccion, entrada, sl, salida)
                    resultado = "WIN" if r > 0 else ("LOSS" if r < 0 else "BE")

                    fila = {
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "par": par,
                        "direccion": direccion,
                        "sesion": sesion,
                        "bias_htf": bias_htf,
                        "tf_entrada": tf_entrada,
                        "entrada": entrada,
                        "stop_loss": sl,
                        "take_profit": tp if tp else None,
                        "salida": salida,
                        "riesgo_pct": riesgo_pct,
                        "pips_riesgo": pips_riesgo,
                        "pips_resultado": pips_resultado,
                        "r_multiplo": r,
                        "resultado": resultado,
                        "contexto_smc": contexto_smc,
                        "razon_entrada": razon_entrada,
                        "se_siguio_plan": se_siguio_plan,
                        "estado_emocional": estado_emocional,
                        "notas": notas,
                    }
                    append_trade(fila)
                    st.success(f"Trade guardado. Resultado: {resultado} | R = {r}")
                    st.rerun()

    with layout_log:
        st.subheader(f"Registro ({len(df)} operaciones)")

        if len(df) == 0:
            st.caption("Aquí aparecerán tus operaciones a medida que las registres.")
        else:
            for _, row in df.sort_values("id", ascending=False).iterrows():
                color = {"WIN": "🟢", "LOSS": "🔴", "BE": "⚪"}.get(row["resultado"], "⚪")
                titulo = f"{color} {row['par']} · {row['direccion']} · {row['r_multiplo']:+.2f} R · {row['fecha']}"
                with st.expander(titulo):
                    st.write(f"**Sesión:** {row['sesion']}  |  **TF entrada:** {row['tf_entrada']}  |  **Bias HTF:** {row['bias_htf']}")
                    st.write(f"**Entrada:** {row['entrada']}  **SL:** {row['stop_loss']}  **TP:** {row['take_profit']}  **Salida:** {row['salida']}")
                    st.write(f"**Riesgo:** {row['riesgo_pct']}%  |  **Pips riesgo:** {row['pips_riesgo']}  |  **Pips resultado:** {row['pips_resultado']}")
                    st.write(f"**Contexto SMC:** {row['contexto_smc'] or '—'}")
                    st.write(f"**Razón de entrada:** {row['razon_entrada'] or '—'}")
                    st.write(f"**Siguió el plan:** {row['se_siguio_plan']}  |  **Estado emocional:** {row['estado_emocional']}/5")
                    st.write(f"**Notas:** {row['notas'] or '—'}")

                    if st.button("Eliminar", key=f"del_{row['id']}"):
                        delete_trade(row["id"])
                        st.rerun()

# =====================================================================
# TAB 2: CHECKLIST DE SETUP (paso 1 del plan)
# =====================================================================
with tab_checklist:
    st.subheader("Checklist Sistema Maldini")
    st.caption(
        "Marca solo lo que ya confirmaste en el gráfico. El score es informativo — "
        "tú decides si ejecutas, el sistema nunca ejecuta solo."
    )

    par_checklist = st.selectbox("Par a evaluar", PARES, key="par_checklist")
    if par_checklist == "Otro":
        par_checklist = st.text_input("Especifica el par", key="par_checklist_otro")

    st.divider()

    valores = {}
    cols = st.columns(2)
    for i, (key, label) in enumerate(CHECKLIST_ITEMS):
        col = cols[i % 2]
        valores[key] = col.checkbox(label, key=f"chk_{key}")

    marcados = sum(1 for v in valores.values() if v)
    total_items = len(CHECKLIST_ITEMS)
    score = round(marcados / total_items * 100, 1)

    st.divider()

    score_col, btn_col1, btn_col2 = st.columns([1.2, 1, 1])

    with score_col:
        st.metric("Score del setup", f"{score:.1f}%", f"{marcados}/{total_items} puntos")
        if score >= 70:
            st.success("Setup con alta confluencia. Sigue revisando antes de decidir.")
        elif score >= 40:
            st.warning("Confluencia parcial. Falta confirmar varios puntos.")
        else:
            st.info("Confluencia baja todavía.")

    with btn_col1:
        guardar = st.button("Guardar checklist", use_container_width=True)

    with btn_col2:
        enviar = st.button("Enviar a Telegram (n8n)", use_container_width=True, type="primary")

    if guardar:
        checklist_id = save_checklist(par_checklist, valores, score)
        if checklist_id:
            st.success(f"Checklist guardado (id {checklist_id}).")
        else:
            st.error("No se pudo guardar el checklist. Revisa la conexión con Supabase.")

    if enviar:
        checklist_id = save_checklist(par_checklist, valores, score)
        payload = {
            "checklist_id": checklist_id,
            "par": par_checklist,
            "score": score,
            "marcados": marcados,
            "total": total_items,
            "detalle": {label: valores[key] for key, label in CHECKLIST_ITEMS},
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        ok, msg = enviar_a_n8n(payload)
        if ok:
            if checklist_id:
                marcar_enviado(checklist_id)
            st.success(msg)
        else:
            st.warning(msg)

    st.divider()
    st.subheader("Últimos checklists guardados")
    hist = load_checklists()
    if hist.empty:
        st.caption("Aún no guardas ningún checklist.")
    else:
        cols_mostrar = ["fecha", "par", "score", "enviado_telegram"]
        cols_mostrar = [c for c in cols_mostrar if c in hist.columns]
        st.dataframe(hist[cols_mostrar].head(10), use_container_width=True, hide_index=True)

# =====================================================================
# TAB 3: ALERTAS DE PRECIO
# =====================================================================
with tab_alertas:
    st.subheader("Alertas de precio")
    st.caption(
        "Define un nivel de precio y n8n te avisa por Telegram cuando el precio "
        "lo cruce. Esto revisa el mercado solo, sin que tengas que estar pendiente."
    )

    with st.form("nueva_alerta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        par_alerta = c1.selectbox("Par", PARES, key="par_alerta")
        if par_alerta == "Otro":
            par_alerta = st.text_input("Especifica el par", key="par_alerta_otro")

        nivel_precio = c2.number_input("Nivel de precio", format="%.5f")

        direccion = st.selectbox(
            "Dirección del cruce",
            ["cualquiera", "arriba", "abajo"],
            format_func=lambda x: {
                "cualquiera": "Cualquiera (toca el nivel desde cualquier lado)",
                "arriba": "Solo si sube y lo cruza hacia arriba",
                "abajo": "Solo si baja y lo cruza hacia abajo",
            }[x],
        )
        nota = st.text_input("Nota (opcional, ej: 'order block H4')")

        crear = st.form_submit_button("Crear alerta", use_container_width=True)

        if crear:
            if nivel_precio == 0:
                st.error("Ingresa un nivel de precio válido.")
            else:
                crear_alerta(par_alerta, nivel_precio, direccion, nota)
                st.success(f"Alerta creada: {par_alerta} @ {nivel_precio}")
                st.rerun()

    st.divider()
    st.subheader("Alertas activas")

    alertas = load_alertas()
    activas = alertas[alertas["activa"] == True] if not alertas.empty else alertas

    if activas.empty:
        st.caption("No tienes alertas activas.")
    else:
        for _, row in activas.sort_values("id", ascending=False).iterrows():
            dir_emoji = {"cualquiera": "↕️", "arriba": "⬆️", "abajo": "⬇️"}.get(row["direccion"], "↕️")
            titulo = f"{dir_emoji} {row['par']} @ {row['nivel_precio']}"
            with st.expander(titulo):
                st.write(f"**Dirección:** {row['direccion']}")
                st.write(f"**Nota:** {row['nota'] or '—'}")
                st.write(f"**Creada:** {row['fecha_creacion']}")
                if row.get("ultimo_precio_visto"):
                    st.write(f"**Último precio visto por n8n:** {row['ultimo_precio_visto']}")

                bc1, bc2 = st.columns(2)
                if bc1.button("Desactivar", key=f"desact_{row['id']}", use_container_width=True):
                    desactivar_alerta(row["id"])
                    st.rerun()
                if bc2.button("Eliminar", key=f"elim_{row['id']}", use_container_width=True):
                    eliminar_alerta(row["id"])
                    st.rerun()

    st.divider()
    st.subheader("Historial (disparadas / inactivas)")
    inactivas = alertas[alertas["activa"] == False] if not alertas.empty else alertas
    if inactivas.empty:
        st.caption("Aún no hay alertas disparadas o desactivadas.")
    else:
        cols_mostrar = ["fecha_creacion", "par", "nivel_precio", "direccion", "disparada", "fecha_disparada"]
        cols_mostrar = [c for c in cols_mostrar if c in inactivas.columns]
        st.dataframe(
            inactivas[cols_mostrar].head(15), use_container_width=True, hide_index=True
        )
