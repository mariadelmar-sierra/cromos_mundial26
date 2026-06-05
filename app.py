import base64
import io
import unicodedata
from typing import Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# =====================================================
# CONFIGURACIÓN BÁSICA
# =====================================================

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
    background-color: #f5f3ff;
}

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

.small-note {
    color: #777;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# UTILIDADES
# =====================================================

def quitar_tildes(texto) -> str:
    if pd.isna(texto):
        return ""
    texto = str(texto)
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    ).lower()


def limpiar_bool(valor) -> bool:
    """Convierte valores tipo TRUE/FALSE, 0/1, Sí/No a bool real."""
    if isinstance(valor, bool):
        return valor
    if pd.isna(valor):
        return False
    texto = str(valor).strip().lower()
    return texto in {"true", "1", "sí", "si", "yes", "y", "x"}


def preparar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Asegura columnas, tipos y orden estable."""
    df = df.copy()

    columnas_necesarias = {
        "codigo": "",
        "nombre": "",
        "seleccion": "",
        "tipo": "",
        "seccion": "",
        "orden_original": None,
        "lo_tengo": False,
        "repetidos": 0,
        "wishlist": False,
    }

    for columna, valor_defecto in columnas_necesarias.items():
        if columna not in df.columns:
            if columna == "orden_original":
                df[columna] = range(len(df))
            else:
                df[columna] = valor_defecto

    df["codigo"] = df["codigo"].astype(str)
    df["nombre"] = df["nombre"].astype(str)
    df["seleccion"] = df["seleccion"].astype(str)
    df["tipo"] = df["tipo"].astype(str)
    df["seccion"] = df["seccion"].astype(str)

    df["orden_original"] = pd.to_numeric(df["orden_original"], errors="coerce")
    df["orden_original"] = df["orden_original"].fillna(range(len(df))).astype(int)

    df["lo_tengo"] = df["lo_tengo"].apply(limpiar_bool)
    df["wishlist"] = df["wishlist"].apply(limpiar_bool)

    df["repetidos"] = pd.to_numeric(df["repetidos"], errors="coerce")
    df["repetidos"] = df["repetidos"].fillna(0).astype(int)
    df.loc[df["repetidos"] < 0, "repetidos"] = 0

    columnas_finales = [
        "codigo", "nombre", "seleccion", "tipo", "seccion",
        "orden_original", "lo_tengo", "repetidos", "wishlist"
    ]

    return df[columnas_finales].sort_values("orden_original").reset_index(drop=True)


def github_config_ok() -> bool:
    requeridos = ["GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_BRANCH", "GITHUB_DATA_PATH"]
    return all(k in st.secrets and str(st.secrets[k]).strip() for k in requeridos)


def get_github_headers() -> dict:
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url() -> str:
    repo = st.secrets["GITHUB_REPO"]
    path = st.secrets["GITHUB_DATA_PATH"]
    return f"https://api.github.com/repos/{repo}/contents/{path}"


def leer_csv_desde_github() -> Tuple[pd.DataFrame, Optional[str]]:
    """Lee el CSV desde GitHub y devuelve df + sha actual del archivo."""
    url = github_file_url()
    branch = st.secrets["GITHUB_BRANCH"]

    response = requests.get(
        url,
        headers=get_github_headers(),
        params={"ref": branch},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    contenido_b64 = data["content"]
    sha = data["sha"]

    contenido = base64.b64decode(contenido_b64).decode("utf-8")
    df = pd.read_csv(io.StringIO(contenido))

    return preparar_df(df), sha


def guardar_csv_en_github(df: pd.DataFrame, sha_actual: Optional[str]) -> None:
    """Sobrescribe el CSV en GitHub creando un commit."""
    url = github_file_url()
    branch = st.secrets["GITHUB_BRANCH"]

    df_limpio = preparar_df(df)
    csv_text = df_limpio.to_csv(index=False)
    contenido_b64 = base64.b64encode(csv_text.encode("utf-8")).decode("utf-8")

    # Por seguridad, si no tenemos SHA en sesión, lo pedimos justo antes de guardar.
    if not sha_actual:
        _, sha_actual = leer_csv_desde_github()

    payload = {
        "message": "Actualizar checklist de cromos",
        "content": contenido_b64,
        "sha": sha_actual,
        "branch": branch,
    }

    response = requests.put(
        url,
        headers=get_github_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()

    nuevo_sha = response.json()["content"]["sha"]
    st.session_state["github_sha"] = nuevo_sha
    st.session_state["df"] = df_limpio


def cargar_datos() -> pd.DataFrame:
    """Carga datos una sola vez por sesión desde GitHub. El botón Recargar fuerza nueva lectura."""
    if "df" not in st.session_state:
        df, sha = leer_csv_desde_github()
        st.session_state["df"] = df
        st.session_state["github_sha"] = sha
    return st.session_state["df"].copy()


def clase_card(row) -> str:
    if bool(row["wishlist"]):
        return "card card-wishlist"
    if int(row["repetidos"]) > 0:
        return "card card-repeated"
    if bool(row["lo_tengo"]):
        return "card card-owned"
    return "card card-missing"


def estado_texto(row) -> str:
    partes = []

    if bool(row["lo_tengo"]):
        partes.append("✅ Lo tengo")
    else:
        partes.append("❌ Me falta")

    if int(row["repetidos"]) > 0:
        partes.append(f"🔁 {int(row['repetidos'])}")

    if bool(row["wishlist"]):
        partes.append("⭐ Wishlist")

    return " · ".join(partes)


def guardar_cambio_cromo(codigo: str, lo_tengo: bool, repetidos: int, wishlist: bool) -> None:
    """Actualiza un único cromo en el df de sesión y guarda todo el CSV en GitHub."""
    df = st.session_state["df"].copy()

    mask = df["codigo"].astype(str) == str(codigo)
    if not mask.any():
        st.error(f"No se encontró el cromo {codigo}.")
        return

    idx = df[mask].index[0]
    df.at[idx, "lo_tengo"] = bool(lo_tengo)
    df.at[idx, "repetidos"] = int(repetidos)
    df.at[idx, "wishlist"] = bool(wishlist)

    guardar_csv_en_github(df, st.session_state.get("github_sha"))

# =====================================================
# APP
# =====================================================

st.title("⚽ Álbum Panini Mundial 2026")
st.write("Checklist compartida de cromos. Los cambios se guardan en GitHub al pulsar **Guardar**.")

if not github_config_ok():
    st.error("Faltan secretos de GitHub en Streamlit Cloud.")
    st.markdown(
        """
        En **Settings > Secrets** añade algo así:

        ```toml
        GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxx"
        GITHUB_REPO = "tu_usuario/tu_repositorio"
        GITHUB_BRANCH = "main"
        GITHUB_DATA_PATH = "album_guardado.csv"
        ```
        """
    )
    st.stop()

try:
    df = cargar_datos()
except Exception as e:
    st.error("No he podido leer el CSV desde GitHub.")
    st.exception(e)
    st.stop()

# =====================================================
# BOTONES SUPERIORES
# =====================================================

b1, b2 = st.columns([1, 5])

with b1:
    if st.button("🔄 Recargar datos"):
        try:
            df_recargado, sha = leer_csv_desde_github()
            st.session_state["df"] = df_recargado
            st.session_state["github_sha"] = sha
            st.rerun()
        except Exception as e:
            st.error("No he podido recargar los datos desde GitHub.")
            st.exception(e)

with b2:
    st.markdown(
        "<div class='small-note'>Usa este botón si otra persona ha guardado cambios antes de abrir tú la app.</div>",
        unsafe_allow_html=True,
    )

st.divider()

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

if total:
    st.progress(tengo / total)
st.write(f"Álbum completado al **{porcentaje}%**")

st.divider()

# =====================================================
# PILLS DE SELECCIONES
# =====================================================

selecciones_final = list(dict.fromkeys(df["seleccion"].dropna().tolist()))
selecciones_final = ["TODOS"] + selecciones_final

pill_labels = ["TODOS"]

for seleccion in selecciones_final[1:]:
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

pill = st.pills(
    "Selección",
    pill_labels,
    selection_mode="single",
    default="TODOS",
)

seleccion_actual = pill_map.get(pill, "TODOS")

st.divider()

# =====================================================
# FILTROS
# =====================================================

f1, f2 = st.columns([1, 2])

with f1:
    estado = st.selectbox(
        "Estado",
        ["Todos", "Los tengo", "Me faltan", "Repetidos", "Wishlist"],
    )

with f2:
    busqueda = st.text_input("Buscar cromo", placeholder="Ej: ESP15, Lamine, España...")

# =====================================================
# FILTRADO
# =====================================================

df_filtrado = df.copy()

if seleccion_actual != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["seleccion"] == seleccion_actual]

if busqueda:
    busqueda_normalizada = quitar_tildes(busqueda)

    mask_codigo = df_filtrado["codigo"].astype(str).apply(quitar_tildes).str.contains(busqueda_normalizada, na=False)
    mask_nombre = df_filtrado["nombre"].astype(str).apply(quitar_tildes).str.contains(busqueda_normalizada, na=False)
    mask_seleccion = df_filtrado["seleccion"].astype(str).apply(quitar_tildes).str.contains(busqueda_normalizada, na=False)

    df_filtrado = df_filtrado[mask_codigo | mask_nombre | mask_seleccion]

if estado == "Los tengo":
    df_filtrado = df_filtrado[df_filtrado["lo_tengo"] == True]
elif estado == "Me faltan":
    df_filtrado = df_filtrado[df_filtrado["lo_tengo"] == False]
elif estado == "Repetidos":
    df_filtrado = df_filtrado[df_filtrado["repetidos"] > 0]
elif estado == "Wishlist":
    df_filtrado = df_filtrado[df_filtrado["wishlist"] == True]

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

    for col, (_, row) in zip(cols, fila.iterrows()):
        codigo = str(row["codigo"])

        with col:
            st.markdown(
                f"""
                <div class="{clase_card(row)}">
                    <div class="code">{codigo}</div>
                    <div class="name">{row['nombre']}</div>
                    <div class="team">{row['seleccion']} · {row['tipo']}</div>
                    <div class="badge">{estado_texto(row)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.popover("⚙️ Editar"):
                lo_tengo = st.checkbox(
                    "Lo tengo",
                    value=bool(row["lo_tengo"]),
                    key=f"tengo_{codigo}",
                )

                repetidos = st.number_input(
                    "Número de repetidos",
                    min_value=0,
                    value=int(row["repetidos"]),
                    step=1,
                    key=f"rep_{codigo}",
                )

                wishlist = st.checkbox(
                    "Wishlist",
                    value=bool(row["wishlist"]),
                    key=f"wish_{codigo}",
                )

                if st.button("Guardar", key=f"save_{codigo}"):
                    try:
                        guardar_cambio_cromo(codigo, lo_tengo, repetidos, wishlist)
                        st.success("Guardado en GitHub")
                        st.rerun()
                    except requests.HTTPError as e:
                        st.error("GitHub no ha aceptado el guardado. Pulsa Recargar datos y vuelve a intentarlo.")
                        st.exception(e)
                    except Exception as e:
                        st.error("No se han podido guardar los cambios.")
                        st.exception(e)
