import base64
import io
import unicodedata
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

st.set_page_config(
    page_title="Álbum Mundial 2026",
    page_icon="⚽",
    layout="wide"
)

# =====================================================
# SECRETS / CONFIG GITHUB
# =====================================================

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "") 
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
GITHUB_DATA_PATH = st.secrets.get("GITHUB_DATA_PATH", "album_guardado.csv")

GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_DATA_PATH}"

COLUMNAS_ESPERADAS = [
    "codigo",
    "nombre",
    "seleccion",
    "tipo",
    "seccion",
    "orden_original",
    "lo_tengo",
    "repetidos",
    "wishlist",
]

# =====================================================
# CSS
# =====================================================

st.markdown(
    """
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}

.card {
    border-radius: 18px;
    padding: 12px;
    margin-bottom: 8px;
    background-color: white;
    min-height: 155px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.06);
    transition: 0.2s;
}

.card:hover {
    transform: translateY(-2px);
}

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

.card-wishlist {
    border: 2px solid #6c5ce7;
    background-color: #f7f5ff;
}

.code {
    font-size: 21px;
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

.small-muted {
    color: #777;
    font-size: 13px;
}

.stButton button {
    width: 100%;
}
</style>
""",
    unsafe_allow_html=True,
)

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================


def comprobar_configuracion():
    faltan = []
    if not GITHUB_TOKEN:
        faltan.append("GITHUB_TOKEN")
    if not GITHUB_REPO:
        faltan.append("GITHUB_REPO")
    if not GITHUB_BRANCH:
        faltan.append("GITHUB_BRANCH")
    if not GITHUB_DATA_PATH:
        faltan.append("GITHUB_DATA_PATH")

    if faltan:
        st.error("Faltan secrets de Streamlit: " + ", ".join(faltan))
        st.stop()


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def quitar_tildes(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto)
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    ).lower()


def convertir_bool(valor):
    """Convierte valores frecuentes de CSV a booleano real."""
    if isinstance(valor, bool):
        return valor
    if pd.isna(valor):
        return False

    texto = str(valor).strip().lower()
    return texto in {"true", "1", "sí", "si", "yes", "y", "t"}


def preparar_df(df):
    """Normaliza columnas y tipos para evitar errores al leer desde GitHub."""
    df = df.copy()

    # Normalizar nombres por si vienen con espacios
    df.columns = [str(c).strip() for c in df.columns]

    # Crear columnas ausentes
    for col in COLUMNAS_ESPERADAS:
        if col not in df.columns:
            if col in {"lo_tengo", "wishlist"}:
                df[col] = False
            elif col == "repetidos":
                df[col] = 0
            elif col == "orden_original":
                df[col] = range(len(df))
            else:
                df[col] = ""

    # Mantener solo columnas esperadas primero y luego cualquier extra al final
    extras = [c for c in df.columns if c not in COLUMNAS_ESPERADAS]
    df = df[COLUMNAS_ESPERADAS + extras]

    # Tipos de texto
    for col in ["codigo", "nombre", "seleccion", "tipo", "seccion"]:
        df[col] = df[col].fillna("").astype(str)

    # Tipo orden_original robusto
    df["orden_original"] = pd.to_numeric(df["orden_original"], errors="coerce")
    mask_orden = df["orden_original"].isna()
    df.loc[mask_orden, "orden_original"] = df.index[mask_orden]
    df["orden_original"] = df["orden_original"].astype(int)

    # Booleanos robustos
    df["lo_tengo"] = df["lo_tengo"].apply(convertir_bool).astype(bool)
    df["wishlist"] = df["wishlist"].apply(convertir_bool).astype(bool)

    # Repetidos robusto
    df["repetidos"] = pd.to_numeric(df["repetidos"], errors="coerce").fillna(0).astype(int)
    df.loc[df["repetidos"] < 0, "repetidos"] = 0

    # Evitar filas vacías accidentales
    df = df[df["codigo"].str.strip() != ""].copy()

    # Orden estable
    df = df.sort_values("orden_original").reset_index(drop=True)

    return df


def leer_csv_desde_github():
    """Lee el CSV actual desde GitHub y devuelve df + sha del archivo."""
    comprobar_configuracion()

    response = requests.get(
        GITHUB_API_URL,
        headers=github_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=30,
    )

    if response.status_code == 404:
        st.error(
            "No encuentro el CSV en GitHub. Revisa que GITHUB_REPO, "
            "GITHUB_BRANCH y GITHUB_DATA_PATH sean exactos."
        )
        st.code(
            f"Repo: {GITHUB_REPO}\n"
            f"Rama: {GITHUB_BRANCH}\n"
            f"Ruta CSV: {GITHUB_DATA_PATH}",
            language="text",
        )
        st.stop()

    response.raise_for_status()
    data = response.json()

    sha = data["sha"]
    contenido_b64 = data["content"]
    contenido_csv = base64.b64decode(contenido_b64).decode("utf-8-sig")

    df = pd.read_csv(io.StringIO(contenido_csv))
    df = preparar_df(df)

    return df, sha


def df_a_csv(df):
    """Convierte el dataframe a CSV limpio para guardar en GitHub."""
    df_guardar = preparar_df(df)

    # Guardamos booleanos como TRUE/FALSE para que el CSV sea claro
    df_guardar["lo_tengo"] = df_guardar["lo_tengo"].map({True: "TRUE", False: "FALSE"})
    df_guardar["wishlist"] = df_guardar["wishlist"].map({True: "TRUE", False: "FALSE"})

    return df_guardar.to_csv(index=False)


def guardar_csv_en_github(df, sha_actual):
    """Sobrescribe el CSV en GitHub creando un commit."""
    csv_text = df_a_csv(df)
    contenido_b64 = base64.b64encode(csv_text.encode("utf-8")).decode("utf-8")

    mensaje = "Actualizar checklist de cromos"
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "message": f"{mensaje} - {fecha}",
        "content": contenido_b64,
        "sha": sha_actual,
        "branch": GITHUB_BRANCH,
    }

    response = requests.put(
        GITHUB_API_URL,
        headers=github_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code == 409:
        st.error(
            "GitHub ha detectado un conflicto porque el CSV cambió desde que abriste la app. "
            "Recarga la página y vuelve a guardar."
        )
        st.stop()

    response.raise_for_status()
    return response.json()["content"]["sha"]


def clase_card(row):
    if bool(row.get("wishlist", False)):
        return "card card-wishlist"
    if int(row.get("repetidos", 0)) > 0:
        return "card card-repeated"
    if bool(row.get("lo_tengo", False)):
        return "card card-owned"
    return "card card-missing"


def estado_texto(row):
    lo_tengo = bool(row.get("lo_tengo", False))
    repetidos = int(row.get("repetidos", 0))
    wishlist = bool(row.get("wishlist", False))

    partes = []
    partes.append("✅ Tengo" if lo_tengo else "❌ Falta")
    if repetidos > 0:
        partes.append(f"🔁 {repetidos}")
    if wishlist:
        partes.append("⭐ Wishlist")
    return " · ".join(partes)


def get_sha_actual():
    return st.session_state.get("github_sha")


def set_sha_actual(sha):
    st.session_state["github_sha"] = sha


def cargar_datos():
    df, sha = leer_csv_desde_github()
    set_sha_actual(sha)
    return df


def guardar_cambio(df, idx, lo_tengo, repetidos, wishlist):
    df = df.copy()
    df.at[idx, "lo_tengo"] = bool(lo_tengo)
    df.at[idx, "repetidos"] = int(repetidos)
    df.at[idx, "wishlist"] = bool(wishlist)

    sha_nuevo = guardar_csv_en_github(df, get_sha_actual())
    set_sha_actual(sha_nuevo)

    st.success("Guardado en GitHub correctamente.")
    st.cache_data.clear()
    st.rerun()

# =====================================================
# CARGA DE DATOS
# =====================================================

try:
    df = cargar_datos()
except Exception as e:
    st.error("No he podido leer el CSV desde GitHub.")
    st.exception(e)
    st.stop()

# =====================================================
# HEADER
# =====================================================

st.title("⚽ Álbum Panini Mundial 2026")
st.write("Checklist compartida de cromos guardada directamente en GitHub.")

with st.expander("⚙️ Configuración actual", expanded=False):
    st.code(
        f"Repo: {GITHUB_REPO}\n"
        f"Rama: {GITHUB_BRANCH}\n"
        f"CSV: {GITHUB_DATA_PATH}\n"
        f"Cromos cargados: {len(df)}",
        language="text",
    )

# =====================================================
# KPIS
# =====================================================

total = len(df)
tengo = int(df["lo_tengo"].sum())
faltan = total - tengo
repetidos_total = int(df["repetidos"].sum())
wishlist_total = int(df["wishlist"].sum())
porcentaje = round((tengo / total) * 100, 2) if total else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", total)
c2.metric("Tengo", tengo)
c3.metric("Faltan", faltan)
c4.metric("Repetidos", repetidos_total)
c5.metric("Wishlist", wishlist_total)

st.progress(tengo / total if total else 0)
st.write(f"Álbum completado al **{porcentaje}%**")
st.divider()

# =====================================================
# PILLS / FILTROS
# =====================================================

selecciones_en_orden = list(dict.fromkeys(df["seleccion"].dropna().astype(str).tolist()))
selecciones_final = ["TODOS"] + selecciones_en_orden

pill_labels = ["TODOS"]
for seleccion in selecciones_en_orden:
    codigo_ejemplo = df[df["seleccion"] == seleccion]["codigo"].astype(str).iloc[0]
    label = codigo_ejemplo[:3].upper()

    if label == "00":
        label = "FWC"

    original = label
    contador = 2
    while label in pill_labels:
        label = f"{original}{contador}"
        contador += 1

    pill_labels.append(label)

pill_map = {pill_labels[i]: selecciones_final[i] for i in range(len(selecciones_final))}

if hasattr(st, "pills"):
    pill = st.pills(
        "Selección",
        pill_labels,
        selection_mode="single",
        default="TODOS",
    )
else:
    pill = st.selectbox("Selección", pill_labels, index=0)

seleccion_actual = pill_map.get(pill, "TODOS")

st.divider()

f1, f2, f3 = st.columns([1, 2, 1])

with f1:
    estado = st.selectbox(
        "Estado",
        ["Todos", "Los tengo", "Me faltan", "Repetidos", "Wishlist"],
    )

with f2:
    busqueda = st.text_input("Buscar por código, nombre o selección")

with f3:
    if st.button("🔄 Recargar desde GitHub"):
        st.cache_data.clear()
        st.rerun()

# =====================================================
# FILTRADO
# =====================================================

df_filtrado = df.copy()

if seleccion_actual != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["seleccion"] == seleccion_actual]

if busqueda:
    busqueda_normalizada = quitar_tildes(busqueda)

    mask_codigo = df_filtrado["codigo"].astype(str).apply(quitar_tildes).str.contains(
        busqueda_normalizada, na=False
    )
    mask_nombre = df_filtrado["nombre"].astype(str).apply(quitar_tildes).str.contains(
        busqueda_normalizada, na=False
    )
    mask_seleccion = df_filtrado["seleccion"].astype(str).apply(quitar_tildes).str.contains(
        busqueda_normalizada, na=False
    )

    df_filtrado = df_filtrado[mask_codigo | mask_nombre | mask_seleccion]

if estado == "Los tengo":
    df_filtrado = df_filtrado[df_filtrado["lo_tengo"]]
elif estado == "Me faltan":
    df_filtrado = df_filtrado[~df_filtrado["lo_tengo"]]
elif estado == "Repetidos":
    df_filtrado = df_filtrado[df_filtrado["repetidos"] > 0]
elif estado == "Wishlist":
    df_filtrado = df_filtrado[df_filtrado["wishlist"]]

df_filtrado = df_filtrado.sort_values("orden_original")

st.write(f"Mostrando **{len(df_filtrado)}** cromos")
st.divider()

# =====================================================
# GRID DE CROMOS
# =====================================================

COLUMNAS = 5

if df_filtrado.empty:
    st.info("No hay cromos que coincidan con los filtros.")
else:
    for inicio in range(0, len(df_filtrado), COLUMNAS):
        fila = df_filtrado.iloc[inicio: inicio + COLUMNAS]
        cols = st.columns(COLUMNAS)

        for col, (idx, row) in zip(cols, fila.iterrows()):
            with col:
                st.markdown(
                    f"""
                    <div class=\"{clase_card(row)}\">
                        <div class=\"code\">{row['codigo']}</div>
                        <div class=\"name\">{row['nombre']}</div>
                        <div class=\"team\">{row['seleccion']} · {row['tipo']}</div>
                        <div class=\"badge\">{estado_texto(row)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                with st.popover("⚙️ Editar"):
                    lo_tengo = st.checkbox(
                        "Lo tengo",
                        value=bool(row["lo_tengo"]),
                        key=f"tengo_{idx}_{row['codigo']}",
                    )

                    repetidos = st.number_input(
                        "Número de repetidos",
                        min_value=0,
                        value=int(row["repetidos"]),
                        step=1,
                        key=f"rep_{idx}_{row['codigo']}",
                    )

                    wishlist = st.checkbox(
                        "Wishlist",
                        value=bool(row["wishlist"]),
                        key=f"wish_{idx}_{row['codigo']}",
                    )

                    if st.button("Guardar", key=f"save_{idx}_{row['codigo']}"):
                        try:
                            guardar_cambio(df, idx, lo_tengo, repetidos, wishlist)
                        except Exception as e:
                            st.error("No se ha podido guardar el cambio en GitHub.")
                            st.exception(e)
                            st.stop()

# =====================================================
# DESCARGA OPCIONAL
# =====================================================

st.divider()
with st.expander("📥 Descargar copia actual del CSV", expanded=False):
    st.download_button(
        "Descargar album_guardado.csv",
        data=df_a_csv(df),
        file_name="album_guardado.csv",
        mime="text/csv",
    )
