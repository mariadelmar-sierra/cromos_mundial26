import os
import html
import textwrap
import unicodedata

import pandas as pd
import streamlit as st

EXCEL_FILE = "Cromos_Panini_Mundial_2026.xlsx"
CSV_FILE = "album_guardado.csv"

st.set_page_config(
    page_title="Álbum Mundial 2026",
    page_icon="⚽",
    layout="wide"
)

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}

.card {
    width: 100%;
    aspect-ratio: 1 / 1;
    border-radius: 12px;
    padding: 8px;
    background-color: white;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    transition: 0.2s;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
}

.card:hover {
    transform: translateY(-2px);
}

.card-owned {
    border: 2px solid #2ecc71;
    background-color: #f3fff8;
}

.card-missing {
    border: 2px solid #ff6b6b;
    background-color: #fff5f5;
}

.card-repeated {
    border: 2px solid #f7b731;
    background-color: #fff8e7;
}

.code {
    font-size: 16px;
    font-weight: 800;
}

.name {
    font-size: 10px;
    font-weight: 700;
    line-height: 1.1;
    margin-top: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.team {
    font-size: 8px;
    color: #777;
    margin-top: 3px;
}

.badge {
    font-size: 8px;
    padding: 2px 6px;
    border-radius: 999px;
    background-color: rgba(0,0,0,0.06);
    width: fit-content;
}

button[kind="secondary"] {
    border-radius: 10px !important;
}

</style>
""", unsafe_allow_html=True)


def quitar_tildes(texto):
    if pd.isna(texto):
        return ""

    texto = str(texto)

    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    ).lower()


def crear_csv_desde_excel():
    df = pd.read_excel(
        EXCEL_FILE,
        sheet_name="Listado de cromos",
        header=3
    )

    df = df.rename(columns={
        "Nº": "codigo",
        "Cromo": "nombre",
        "Selección": "seleccion",
        "Tipo": "tipo",
        "Sección": "seccion"
    })

    df = df[[
        "codigo",
        "nombre",
        "seleccion",
        "tipo",
        "seccion"
    ]].copy()

    df = df.dropna(subset=["codigo", "nombre"])
    df["codigo"] = df["codigo"].astype(str)
    df = df.reset_index(drop=True)

    df["orden_album"] = df.index
    df["lo_tengo"] = False
    df["repetidos"] = 0
    df["wishlist"] = False

    df.to_csv(CSV_FILE, index=False)

    return df


def cargar_datos():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)

        if "orden_album" not in df.columns:
            df["orden_album"] = range(len(df))

        return df

    return crear_csv_desde_excel()


def guardar_datos(df):
    df.to_csv(CSV_FILE, index=False)


def clase_card(row):
    if int(row["repetidos"]) > 0:
        return "card card-repeated"

    if bool(row["lo_tengo"]):
        return "card card-owned"

    return "card card-missing"


def estado_texto(row):
    if bool(row["lo_tengo"]) and int(row["repetidos"]) > 0:
        return f"✅ · 🔁 {int(row['repetidos'])}"

    if bool(row["lo_tengo"]):
        return "✅ Tengo"

    return "❌ Falta"


df = cargar_datos()

st.title("⚽ Álbum Mundial 2026")

f1, f2 = st.columns(2)

with f1:
    seleccion = st.selectbox(
        "Selección",
        ["Todas"] + sorted(df["seleccion"].dropna().unique().tolist())
    )

with f2:
    estado = st.selectbox(
        "Estado",
        [
            "Todos",
            "Los tengo",
            "Me faltan",
            "Repetidos",
            "Wishlist"
        ]
    )

busqueda = st.text_input("🔍 Buscar cromo")

df_filtrado = df.copy()

if seleccion != "Todas":
    df_filtrado = df_filtrado[
        df_filtrado["seleccion"] == seleccion
    ]

if estado == "Los tengo":
    df_filtrado = df_filtrado[
        df_filtrado["lo_tengo"] == True
    ]

elif estado == "Me faltan":
    df_filtrado = df_filtrado[
        df_filtrado["lo_tengo"] == False
    ]

elif estado == "Repetidos":
    df_filtrado = df_filtrado[
        df_filtrado["repetidos"] > 0
    ]

elif estado == "Wishlist":
    df_filtrado = df_filtrado[
        df_filtrado["wishlist"] == True
    ]

if busqueda:
    busqueda_normalizada = quitar_tildes(busqueda)

    df_filtrado = df_filtrado[
        (
            df_filtrado["codigo"]
            .astype(str)
            .apply(quitar_tildes)
            .str.contains(busqueda_normalizada, na=False)
        )
        |
        (
            df_filtrado["nombre"]
            .astype(str)
            .apply(quitar_tildes)
            .str.contains(busqueda_normalizada, na=False)
        )
        |
        (
            df_filtrado["seleccion"]
            .astype(str)
            .apply(quitar_tildes)
            .str.contains(busqueda_normalizada, na=False)
        )
    ]

df_filtrado = df_filtrado.sort_values("orden_album")

st.write(f"Mostrando **{len(df_filtrado)}** cromos")
st.divider()

COLUMNAS = 9

for inicio in range(0, len(df_filtrado), COLUMNAS):

    fila = df_filtrado.iloc[inicio:inicio + COLUMNAS]

    cols = st.columns(COLUMNAS)

    for col, (i, row) in zip(cols, fila.iterrows()):

        with col:

            codigo = html.escape(str(row["codigo"]))
            nombre = html.escape(str(row["nombre"]))
            seleccion_txt = html.escape(str(row["seleccion"]))
            estado_txt = html.escape(estado_texto(row))

            html_card = textwrap.dedent(f"""
            <div class="{clase_card(row)}">
                <div>
                    <div class="code">{codigo}</div>
                    <div class="name">{nombre}</div>
                    <div class="team">{seleccion_txt}</div>
                </div>
                <div class="badge">{estado_txt}</div>
            </div>
            """)

            st.markdown(html_card, unsafe_allow_html=True)

            with st.popover("⚙️"):

                lo_tengo = st.checkbox(
                    "Lo tengo",
                    value=bool(row["lo_tengo"]),
                    key=f"tengo_{i}"
                )

                repetidos = st.number_input(
                    "Repetidos",
                    min_value=0,
                    value=int(row["repetidos"]),
                    step=1,
                    key=f"rep_{i}"
                )

                wishlist = st.checkbox(
                    "Wishlist",
                    value=bool(row["wishlist"]),
                    key=f"wish_{i}"
                )

                if st.button("Guardar", key=f"save_{i}"):

                    idx = df[
                        df["codigo"].astype(str) == str(row["codigo"])
                    ].index[0]

                    df.at[idx, "lo_tengo"] = lo_tengo
                    df.at[idx, "repetidos"] = repetidos
                    df.at[idx, "wishlist"] = wishlist

                    guardar_datos(df)

                    st.rerun()
