"""
Sistema Maldini - Trading Journal (Streamlit)
-----------------------------------------------
App web para registrar operaciones y ver estadísticas en tiempo real.

Correr localmente:
    pip install streamlit pandas
    streamlit run app.py

Desplegar gratis:
    Sube este archivo (+ requirements.txt) a un repo de GitHub y conéctalo
    en https://share.streamlit.io (Streamlit Community Cloud).
"""

import os
from datetime import datetime

import pandas as pd
import streamlit as st

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades_log.csv")

FIELDS = [
    "id", "fecha", "par", "direccion", "sesion", "bias_htf", "tf_entrada",
    "entrada", "stop_loss", "take_profit", "salida", "riesgo_pct",
    "pips_riesgo", "pips_resultado", "r_multiplo", "resultado",
    "contexto_smc", "razon_entrada", "se_siguio_plan", "estado_emocional", "notas",
]

PARES = ["EURUSD", "XAUUSD", "NAS100", "Otro"]
SESIONES = ["Londres", "NY", "Asia", "Londres-NY overlap", "Otro"]

st.set_page_config(page_title="Sistema Maldini - Trading Journal", layout="wide")


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
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=FIELDS)
    return pd.read_csv(CSV_FILE)


def save_all(df):
    df.to_csv(CSV_FILE, index=False)


def append_trade(fila):
    df = load_trades()
    df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
    save_all(df)


# ---------- Header ----------
st.markdown(
    "<p style='color:#D4A24C; font-family:monospace; letter-spacing:2px; "
    "font-size:12px; margin-bottom:0;'>SISTEMA MALDINI</p>",
    unsafe_allow_html=True,
)
st.title("Trading journal")

df = load_trades()

# ---------- Estadísticas ----------
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

# ---------- Formulario ----------
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
                    "id": len(df) + 1,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "par": par,
                    "direccion": direccion,
                    "sesion": sesion,
                    "bias_htf": bias_htf,
                    "tf_entrada": tf_entrada,
                    "entrada": entrada,
                    "stop_loss": sl,
                    "take_profit": tp if tp else "",
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

# ---------- Registro ----------
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
                    df2 = load_trades()
                    df2 = df2[df2["id"] != row["id"]]
                    save_all(df2)
                    st.rerun()
