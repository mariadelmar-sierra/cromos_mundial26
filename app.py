import pandas as pd
import streamlit as st
import unicodedata
import gspread
from google.oauth2.service_account import Credentials


# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

st.set_page_config(
    page_title="Álbum Mundial 2026",
    page_icon="⚽",
    layout="wide"
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


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
# CONEXIÓN GOOGLE SHEETS
# =====================================================

def conectar_google_sheet():
    credentials = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=SCOPES
    )

    gc = gspread.authorize(credentials)

    spreadsheet = gc.open(
        st.secrets["google_sheet"]["spreadsheet_name"]
    )

    worksheet = spreadsheet.worksheet(
        st.secrets["google_sheet"]["worksheet_name"]
    )

    return worksheet


# =====================================================
# FUNCIONES DE DATOS
# =====================================================

def convertir_a_bool(valor):
    """
    Convierte valores de Google Sheets a booleanos reales.
    Acepta TRUE/FALSE, true/false, 1/0, sí/no, si/no.
    """

    if isinstance(valor, bool):
        return valor

    valor = str(valor).strip().lower()

    return valor in ["true", "1", "sí", "si", "yes", "x"]


def cargar_datos():
    """
    Lee siempre los datos desde Google Sheets.
    No usa Excel ni CSV local.
    """

    worksheet = conectar_google_sheet()

    records = worksheet.get_all_records()

    if not records:
        st.error(
            "La hoja de Google Sheets está vacía. "
            "Debes crear primero las columnas: codigo, nombre, seleccion, tipo, seccion, orden_original, lo_tengo, repetidos, wishlist."
        )
        st.stop()

    df = pd.DataFrame(records)

    columnas_necesarias = [
        "codigo",
        "nombre",
        "seleccion",
        "tipo",
        "seccion",
        "orden_original",
        "lo_tengo",
        "repetidos",
        "wishlist"
    ]

    faltantes = [
        col for col in columnas_necesarias
        if col not in df.columns
    ]

    if faltantes:
        st.error(
            f"Faltan columnas en Google Sheets: {faltantes}"
        )
        st.stop()

    df = df[columnas_necesarias].copy()

    df["codigo"] = df["codigo"].astype(str)
    df["nombre"] = df["nombre"].astype(str)
    df["seleccion"] = df["seleccion"].astype(str)
    df["tipo"] = df["tipo"].astype(str)
    df["seccion"] = df["seccion"].astype(str)

    df["orden_original"] = pd.to_numeric(
        df["orden_original"],
        errors="coerce"
    ).fillna(0).astype(int)

    df["repetidos"] = pd.to_numeric(
        df["repetidos"],
        errors="coerce"
    ).fillna(0).astype(int)

    df["lo_tengo"] = df["lo_tengo"].apply(convertir_a_bool)
    df["wishlist"] = df["wishlist"].apply(convertir_a_bool)

    df = df.sort_values("orden_original").reset_index(drop=True)

    return df


def guardar_datos(df):
    """
    Guarda todo el DataFrame en Google Sheets.
    Mantiene lo_tengo y wishlist como 0/1.
    """

    worksheet = conectar_google_sheet()

    df_guardar = df.copy()

    df_guardar["codigo"] = df_guardar["codigo"].astype(str)
    df_guardar["nombre"] = df_guardar["nombre"].astype(str)
    df_guardar["seleccion"] = df_guardar["seleccion"].astype(str)
    df_guardar["tipo"] = df_guardar["tipo"].astype(str)
    df_guardar["seccion"] = df_guardar["seccion"].astype(str)

    df_guardar["orden_original"] = df_guardar["orden_original"].astype(int)
    df_guardar["repetidos"] = df_guardar["repetidos"].astype(int)

    df_guardar["lo_tengo"] = df_guardar["lo_tengo"].apply(lambda x: 1 if bool(x) else 0)
    df_guardar["wishlist"] = df_guardar["wishlist"].apply(lambda x: 1 if bool(x) else 0)

    worksheet.clear()

    worksheet.update(
        [df_guardar.columns.tolist()] +
        df_guardar.values.tolist()
    )


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def quitar_tildes(texto):

    if pd.isna(texto):
        return ""

    texto = str(texto)

    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower()


def clase_card(row):

    if int(row["repetidos"]) > 0:
        return "card card-repeated"

    if bool(row["lo_tengo"]):
        return "card card-owned"

    return "card card-missing"


def estado_texto(row):

    if bool(row["lo_tengo"]) and int(row["repetidos"]) > 0:
        return f"✅ Tengo · 🔁 {int(row['repetidos'])}"

    if bool(row["lo_tengo"]):
        return "✅ Lo tengo"

    return "❌ Me falta"


# =====================================================
# CARGAR DATOS DESDE GOOGLE SHEETS
# =====================================================

df = cargar_datos()


# =====================================================
# HEADER
# =====================================================

st.title("⚽ Álbum Panini Mundial 2026")

st.write("Gestiona tus cromos de forma visual.")

st.caption("Los cambios se guardan directamente en Google Sheets.")


# =====================================================
# KPIS
# =====================================================

total = len(df)

tengo = int(df["lo_tengo"].sum())

faltan = total - tengo

repetidos_total = int(df["repetidos"].sum())

porcentaje = round((tengo / total) * 100, 2) if total > 0 else 0

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total", total)
c2.metric("Tengo", tengo)
c3.metric("Faltan", faltan)
c4.metric("Repetidos", repetidos_total)

if total > 0:
    st.progress(tengo / total)

st.write(f"Álbum completado al **{porcentaje}%**")

st.divider()


# =====================================================
# PILLS DE SELECCIONES
# =====================================================

selecciones_final = list(
    dict.fromkeys(
        df["seleccion"].dropna().tolist()
    )
)

pill_labels = ["TODOS"]
selecciones_final = ["TODOS"] + selecciones_final

for seleccion in selecciones_final[1:]:

    codigo_ejemplo = (
        df[df["seleccion"] == seleccion]["codigo"]
        .astype(str)
        .iloc[0]
    )

    label = codigo_ejemplo[:3].upper()

    if label == "00":
        label = "FWC"

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
# ATAJOS
# =====================================================

a1, a2 = st.columns([1, 5])

with a1:
    ver_repetidos = st.button("🔁 Repetidos")


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

if seleccion_actual != "TODOS":

    df_filtrado = df_filtrado[
        df_filtrado["seleccion"] == seleccion_actual
    ]

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

if ver_repetidos:

    df_filtrado = df_filtrado[
        df_filtrado["repetidos"] > 0
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
                    key=f"tengo_{row['codigo']}"
                )

                repetidos = st.number_input(
                    "Número de repetidos",
                    min_value=0,
                    value=int(row["repetidos"]),
                    step=1,
                    key=f"rep_{row['codigo']}"
                )

                wishlist = st.checkbox(
                    "Wishlist",
                    value=bool(row["wishlist"]),
                    key=f"wish_{row['codigo']}"
                )

                if st.button(
                    "Guardar",
                    key=f"save_{row['codigo']}"
                ):

                    idx = df[
                        df["codigo"].astype(str) == str(row["codigo"])
                    ].index[0]

                    df.at[idx, "lo_tengo"] = lo_tengo
                    df.at[idx, "repetidos"] = int(repetidos)
                    df.at[idx, "wishlist"] = wishlist

                    guardar_datos(df)

                    st.success("Guardado en Google Sheets")

                    st.rerun()
