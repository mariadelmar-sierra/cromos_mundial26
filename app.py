import os
import pandas as pd
import streamlit as st
import unicodedata

EXCEL_FILE = "Cromos_Panini_Mundial_2026.xlsx"
CSV_FILE = "album_guardado.csv"

st.set_page_config(
    page_title="Álbum Mundial 2026",
    page_icon="⚽",
    layout="wide"
)

# =====================================================
# CSS
# =====================================================

st.markdown("""
<style>

.block-container {
    padding-top: 0.8rem;
    padding-bottom: 2rem;
}

/* =========================
   TARJETAS
========================= */

.card {
    border-radius: 5px;
    padding: 6px;
    margin-bottom: 4px;
    background-color: white;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    transition: 0.2s;
    min-height: 75px;
}

.card:hover {
    transform: translateY(-2px);
}

/* =========================
   ESTADOS
========================= */

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

/* =========================
   TEXTO
========================= */

.code {
    font-size: 6px;
    font-weight: 800;
}

.name {
    font-size: 9px;
    font-weight: 700;
    margin-top: 2px;
    line-height: 1.1;
}

.team {
    color: #666;
    font-size: 7px;
    margin-top: 1px;
}

.badge {
    display: inline-block;
    margin-top: 3px;
    padding: 1px 4px;
    border-radius: 999px;
    background-color: rgba(0,0,0,0.06);
    font-size: 7px;
    font-weight: 600;
}

/* =========================
   EXPANDER
========================= */

div[data-testid="stExpander"] {
    border: none !important;
}

/* =========================
   MÁS COMPACTO EN MÓVIL
========================= */

@media (max-width: 768px) {

    .block-container {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }

}

</style>
""", unsafe_allow_html=True)

# =====================================================
# FUNCIONES
# =====================================================

def quitar_tildes(texto):

    if pd.isna(texto):
        return ""

    texto = str(texto)

    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
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

    # =========================================
    # LIMPIEZA
    # =========================================

    df = df.dropna(subset=["codigo", "nombre"])

    df["codigo"] = df["codigo"].astype(str)

    df = df.reset_index(drop=True)

    # ORDEN REAL DEL ÁLBUM
    df["orden_album"] = df.index

    # =========================================

    df["lo_tengo"] = False
    df["repetidos"] = 0
    df["wishlist"] = False

    df.to_csv(CSV_FILE, index=False)

    return df


def cargar_datos():

    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)

    return crear_csv_desde_excel()


def guardar_datos(df):

    df.to_csv(CSV_FILE, index=False)


def clase_card(row):

    if row["repetidos"] > 0:
        return "card card-repeated"

    if row["lo_tengo"]:
        return "card card-owned"

    return "card card-missing"


def estado_texto(row):

    if row["lo_tengo"] and row["repetidos"] > 0:
        return f"✅ · 🔁 {row['repetidos']}"

    if row["lo_tengo"]:
        return "✅ Tengo"

    return "❌ Falta"


# =====================================================
# CARGAR DATOS
# =====================================================

df = cargar_datos()

# =====================================================
# HEADER
# =====================================================

st.title("⚽ Álbum Panini Mundial 2026")

# =====================================================
# KPIS
# =====================================================

total = len(df)

tengo = int(df["lo_tengo"].sum())

faltan = total - tengo

repetidos_total = int(df["repetidos"].sum())

porcentaje = round((tengo / total) * 100, 2)

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total", total)
c2.metric("Tengo", tengo)
c3.metric("Faltan", faltan)
c4.metric("Repetidos", repetidos_total)

st.progress(tengo / total)

st.write(f"Álbum completado al **{porcentaje}%**")

st.divider()

# =====================================================
# FILTROS
# =====================================================

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

# =====================================================
# FILTRADO
# =====================================================

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

# =====================================================
# BUSCADOR SIN TILDES
# =====================================================

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

# =====================================================
# ORDEN REAL DEL ÁLBUM
# =====================================================

df_filtrado = df_filtrado.sort_values("orden_album")

st.write(f"Mostrando **{len(df_filtrado)}** cromos")

st.divider()

# =====================================================
# GRID RESPONSIVE
# =====================================================

COLUMNAS = 5

for inicio in range(0, len(df_filtrado), COLUMNAS):

    fila = df_filtrado.iloc[inicio:inicio + COLUMNAS]

    cols = st.columns(COLUMNAS)

    for col, (i, row) in zip(cols, fila.iterrows()):

        with col:

            st.markdown(
                f"""
                <div class="{clase_card(row)}">
                    <div class="code">{row['codigo']}</div>
                    <div class="name">{row['nombre']}</div>
                    <div class="team">{row['seleccion']}</div>
                    <div class="badge">{estado_texto(row)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

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

                if st.button(
                    "Guardar",
                    key=f"save_{i}"
                ):

                    idx = df[
                        df["codigo"].astype(str) == str(row["codigo"])
                    ].index[0]

                    df.at[idx, "lo_tengo"] = lo_tengo
                    df.at[idx, "repetidos"] = repetidos
                    df.at[idx, "wishlist"] = wishlist

                    guardar_datos(df)

                    st.success("Guardado")

                    st.rerun()
