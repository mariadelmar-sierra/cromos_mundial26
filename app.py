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
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}

/* =========================
   CARDS
========================= */

.card {
    border-radius: 18px;
    padding: 12px;
    margin-bottom: 12px;
    background-color: white;
    min-height: 150px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.06);
    transition: 0.2s;
}

.card:hover {
    transform: translateY(-2px);
}

/* =========================
   ESTADOS
========================= */

.card-owned {
    border: 2px solid #2ecc71;
    background-color: #f4fff8;
}

.card-missing {
    border: 2px solid #ff6b6b;
    background-color: #fff5f5;
}

.card-repeated {
    border: 2px solid #f7b731;
    background-color: #fff9ed;
}

/* =========================
   TEXTOS
========================= */

.code {
    font-size: 22px;
    font-weight: 800;
    margin-bottom: 10px;
}

.name {
    font-size: 15px;
    font-weight: 700;
    line-height: 1.2;
}

.team {
    color: #666;
    font-size: 13px;
    margin-top: 6px;
}

.badge {
    display: inline-block;
    margin-top: 12px;
    padding: 5px 10px;
    border-radius: 999px;
    background-color: rgba(0,0,0,0.06);
    font-size: 12px;
    font-weight: 600;
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

    df = df.dropna(subset=["codigo", "nombre"])

    df["codigo"] = df["codigo"].astype(str)

    df = df.reset_index(drop=True)

    df["orden_original"] = df.index

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
        return f"✅ Tengo · 🔁 {row['repetidos']}"

    if row["lo_tengo"]:
        return "✅ Lo tengo"

    return "❌ Me falta"


# =====================================================
# CARGAR DATOS
# =====================================================

df = cargar_datos()

# =====================================================
# HEADER
# =====================================================

st.title("⚽ Álbum Panini Mundial 2026")

st.write("Gestiona tus cromos de forma visual.")

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
# PILLS DE SELECCIONES
# =====================================================

# mantener orden ORIGINAL del dataset
selecciones_final = list(dict.fromkeys(df["seleccion"].dropna().tolist()))

pill_labels = ["TODOS"]
selecciones_final = ["TODOS"] + selecciones_final

for seleccion in selecciones_final[1:]:

    codigo_ejemplo = (
        df[df["seleccion"] == seleccion]["codigo"]
        .astype(str)
        .iloc[0]
    )

    label = codigo_ejemplo[:3].upper()

    # cambiar 000 por FWC
    if label == "000":
        label = "FWC"

    # evitar duplicados
    original = label
    contador = 2

    while label in pill_labels:
        label = f"{original}{contador}"
        contador += 1

    pill_labels.append(label)

pill_map = {
    pill_labels[i]: selecciones_final[i]
    for i in range(len(selecciones_final))
}

pill = st.pills(
    "Selección",
    pill_labels,
    selection_mode="single",
    default="TODOS"
)

seleccion_actual = pill_map[pill]

st.divider()

# =====================================================
# FILTROS
# =====================================================

f1, f2 = st.columns([1, 2])

with f1:

    estado = st.selectbox(
        "Estado",
        [
            "Todos",
            "Los tengo",
            "Me faltan",
            "Repetidos"
        ]
    )

with f2:

    busqueda = st.text_input("Buscar cromo")

# =====================================================
# FILTRADO
# =====================================================

df_filtrado = df.copy()

# selección
if seleccion_actual != "TODOS":

    df_filtrado = df_filtrado[
        df_filtrado["seleccion"] == seleccion_actual
    ]

# buscador
if busqueda:

    busqueda_normalizada = quitar_tildes(busqueda)

    mask_codigo = (
        df_filtrado["codigo"]
        .astype(str)
        .apply(quitar_tildes)
        .str.contains(busqueda_normalizada, na=False)
    )

    mask_nombre = (
        df_filtrado["nombre"]
        .astype(str)
        .apply(quitar_tildes)
        .str.contains(busqueda_normalizada, na=False)
    )

    mask_seleccion = (
        df_filtrado["seleccion"]
        .astype(str)
        .apply(quitar_tildes)
        .str.contains(busqueda_normalizada, na=False)
    )

    df_filtrado = df_filtrado[
        mask_codigo | mask_nombre | mask_seleccion
    ]

# estado
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

# mantener orden ORIGINAL
df_filtrado = df_filtrado.sort_values("orden_original")

st.write(f"Mostrando **{len(df_filtrado)}** cromos")

st.divider()

# =====================================================
# GRID DE CROMOS
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
                    "Número de repetidos",
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

                    st.rerun()
