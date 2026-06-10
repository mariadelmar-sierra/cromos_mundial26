import base64
import io
import unicodedata

import pandas as pd
import requests
import streamlit as st
from generar_repetidos_pdf import crear_pdf_repetidos
from generar_faltantes_pdf import crear_pdf_faltantes


# =====================================================
# CONFIGURACIÓN STREAMLIT
# =====================================================

st.set_page_config(
    page_title="Álbum Mundial 2026",
    page_icon="⚽",
    layout="wide",
)


# =====================================================
# CONFIGURACIÓN GITHUB
# =====================================================

def get_config():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        branch = st.secrets.get("GITHUB_BRANCH", "main")
        data_path = st.secrets.get("GITHUB_DATA_PATH", "album_guardado.csv")
    except Exception:
        st.error(
            "Faltan secrets de GitHub. Revisa GITHUB_TOKEN, GITHUB_REPO, "
            "GITHUB_BRANCH y GITHUB_DATA_PATH en Streamlit Cloud."
        )
        st.stop()

    return token, repo, branch, data_path


def github_headers():
    token, _, _, _ = get_config()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url():
    _, repo, _, data_path = get_config()
    return f"https://api.github.com/repos/{repo}/contents/{data_path}"


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

.stButton > button {
    border-radius: 12px;
    font-weight: 600;
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
    border: 2px solid #8e44ad;
    background-color: #faf5ff;
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

.save-box {
    border: 1px solid #eee;
    padding: 14px;
    border-radius: 16px;
    background-color: #fafafa;
    margin-bottom: 18px;
}

.pending {
    font-weight: 700;
    color: #c0392b;
}

.saved {
    font-weight: 700;
    color: #27ae60;
}

</style>
""",
    unsafe_allow_html=True,
)


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def quitar_tildes(texto):
    if pd.isna(texto):
        return ""

    texto = str(texto)

    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    ).lower()


def convertir_bool(valor):
    if isinstance(valor, bool):
        return valor

    if pd.isna(valor):
        return False

    valor = str(valor).strip().lower()

    return valor in ["true", "1", "yes", "sí", "si", "x"]


def preparar_df(df):
    df = df.copy()

    columnas_necesarias = [
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

    for col in columnas_necesarias:
        if col not in df.columns:
            if col in ["lo_tengo", "wishlist"]:
                df[col] = False
            elif col == "repetidos":
                df[col] = 0
            elif col == "orden_original":
                df[col] = range(len(df))
            else:
                df[col] = ""

    df["codigo"] = df["codigo"].astype(str)
    df["nombre"] = df["nombre"].fillna("").astype(str)
    df["seleccion"] = df["seleccion"].fillna("").astype(str)
    df["tipo"] = df["tipo"].fillna("").astype(str)
    df["seccion"] = df["seccion"].fillna("").astype(str)

    df["lo_tengo"] = df["lo_tengo"].apply(convertir_bool)
    df["wishlist"] = df["wishlist"].apply(convertir_bool)

    df["repetidos"] = pd.to_numeric(
        df["repetidos"],
        errors="coerce",
    ).fillna(0).astype(int)

    df.loc[df["repetidos"] < 0, "repetidos"] = 0

    df["orden_original"] = pd.to_numeric(
        df["orden_original"],
        errors="coerce",
    )

    mask = df["orden_original"].isna()
    df.loc[mask, "orden_original"] = df.index[mask]
    df["orden_original"] = df["orden_original"].astype(int)

    return df[columnas_necesarias].sort_values("orden_original").reset_index(drop=True)


def df_to_csv_text(df):
    df_guardar = preparar_df(df)

    df_guardar["lo_tengo"] = df_guardar["lo_tengo"].astype(bool)
    df_guardar["wishlist"] = df_guardar["wishlist"].astype(bool)
    df_guardar["repetidos"] = df_guardar["repetidos"].astype(int)
    df_guardar["orden_original"] = df_guardar["orden_original"].astype(int)

    return df_guardar.to_csv(index=False)


def clase_card(row):
    if bool(row["wishlist"]):
        return "card card-wishlist"

    if int(row["repetidos"]) > 0:
        return "card card-repeated"

    if bool(row["lo_tengo"]):
        return "card card-owned"

    return "card card-missing"


def estado_texto(row):
    partes = []

    if bool(row["lo_tengo"]):
        partes.append("✅ Tengo")
    else:
        partes.append("❌ Falta")

    if int(row["repetidos"]) > 0:
        partes.append(f"🔁 {int(row['repetidos'])}")

    if bool(row["wishlist"]):
        partes.append("⭐ Wishlist")

    return " · ".join(partes)


# =====================================================
# FUNCIONES GITHUB
# =====================================================

def leer_csv_desde_github():
    _, _, branch, _ = get_config()

    response = requests.get(
        github_file_url(),
        headers=github_headers(),
        params={"ref": branch},
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    sha = data["sha"]
    contenido_base64 = data["content"]
    contenido = base64.b64decode(contenido_base64).decode("utf-8")

    df = pd.read_csv(io.StringIO(contenido))

    return preparar_df(df), sha


def guardar_csv_en_github(df, sha_actual):
    _, _, branch, _ = get_config()

    csv_text = df_to_csv_text(df)
    contenido_base64 = base64.b64encode(
        csv_text.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": "Actualizar checklist de cromos",
        "content": contenido_base64,
        "sha": sha_actual,
        "branch": branch,
    }

    response = requests.put(
        github_file_url(),
        headers=github_headers(),
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()["content"]["sha"]


# =====================================================
# ESTADO DE SESIÓN
# =====================================================

def inicializar_estado():
    if "df" not in st.session_state or "sha" not in st.session_state:
        try:
            df, sha = leer_csv_desde_github()
            st.session_state.df = df
            st.session_state.sha = sha
            st.session_state.cambios_pendientes = False
            st.session_state.cromos_pendientes = set()
        except Exception as e:
            st.error("No he podido leer el CSV desde GitHub.")
            st.exception(e)
            st.stop()

    if "cambios_pendientes" not in st.session_state:
        st.session_state.cambios_pendientes = False

    if "cromos_pendientes" not in st.session_state:
        st.session_state.cromos_pendientes = set()


def recargar_desde_github():
    try:
        df, sha = leer_csv_desde_github()
        st.session_state.df = df
        st.session_state.sha = sha
        st.session_state.cambios_pendientes = False
        st.session_state.cromos_pendientes = set()
        st.success("Datos recargados desde GitHub.")
    except Exception as e:
        st.error("No he podido recargar desde GitHub.")
        st.exception(e)


def guardar_todos_los_cambios():
    try:
        nuevo_sha = guardar_csv_en_github(
            st.session_state.df,
            st.session_state.sha,
        )

        st.session_state.sha = nuevo_sha
        st.session_state.cambios_pendientes = False
        st.session_state.cromos_pendientes = set()
        st.success("Cambios guardados correctamente en GitHub.")

    except requests.exceptions.HTTPError as e:
        st.error(
            "No he podido guardar en GitHub. Puede que el archivo haya cambiado "
            "desde otra sesión. Pulsa 'Recargar desde GitHub' y vuelve a intentarlo."
        )
        st.exception(e)

    except Exception as e:
        st.error("No he podido guardar los cambios.")
        st.exception(e)


def aplicar_cambio_por_codigo(codigo, lo_tengo, repetidos, wishlist):
    df = st.session_state.df.copy()

    idx_list = df[df["codigo"].astype(str) == str(codigo)].index

    if len(idx_list) == 0:
        return False

    idx = idx_list[0]

    valor_actual_tengo = bool(df.at[idx, "lo_tengo"])
    valor_actual_rep = int(df.at[idx, "repetidos"])
    valor_actual_wish = bool(df.at[idx, "wishlist"])

    hay_cambio = (
        valor_actual_tengo != bool(lo_tengo)
        or valor_actual_rep != int(repetidos)
        or valor_actual_wish != bool(wishlist)
    )

    if hay_cambio:
        df.at[idx, "lo_tengo"] = bool(lo_tengo)
        df.at[idx, "repetidos"] = int(repetidos)
        df.at[idx, "wishlist"] = bool(wishlist)

        st.session_state.df = df
        st.session_state.cambios_pendientes = True
        st.session_state.cromos_pendientes.add(str(codigo))

    return hay_cambio


# =====================================================
# INICIO APP
# =====================================================

inicializar_estado()

df = st.session_state.df


# =====================================================
# HEADER
# =====================================================

st.title("⚽ Álbum Panini Mundial 2026")

st.write("Checklist compartida de cromos guardada directamente en GitHub.")

with st.expander("⚙️ Configuración actual"):
    _, repo, branch, data_path = get_config()
    st.write(f"**Repositorio:** `{repo}`")
    st.write(f"**Rama:** `{branch}`")
    st.write(f"**Archivo de datos:** `{data_path}`")


# =====================================================
# KPIS
# =====================================================

total = len(df)
tengo = int(df["lo_tengo"].sum())
faltan = total - tengo
repetidos_total = int(df["repetidos"].sum())
wishlist_total = int(df["wishlist"].sum())

porcentaje = round((tengo / total) * 100, 2) if total > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Total", total)
c2.metric("Tengo", tengo)
c3.metric("Faltan", faltan)
c4.metric("Repetidos", repetidos_total)
c5.metric("Wishlist", wishlist_total)

if total > 0:
    st.progress(tengo / total)

st.write(f"Álbum completado al **{porcentaje}%**")


# =====================================================
# BOTONES GENERALES
# =====================================================

st.divider()

st.markdown('<div class="save-box">', unsafe_allow_html=True)

g1, g2, g3, g4, g5 = st.columns([1.35, 1.35, 1.45, 1.45, 3.2])

with g1:
    if st.button("💾 Guardar todos", use_container_width=True):
        guardar_todos_los_cambios()
        st.rerun()

with g2:
    if st.button("🔄 Recargar", use_container_width=True):
        recargar_desde_github()
        st.rerun()

with g3:
    try:
        pdf_repetidos = crear_pdf_repetidos(st.session_state.df)
        st.download_button(
            label="📄 Repetidos PDF",
            data=pdf_repetidos,
            file_name="repetidos_album.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.error("No se pudo generar el PDF de repetidos.")
        st.exception(e)

with g4:
    try:
        pdf_faltantes = crear_pdf_faltantes(st.session_state.df)
        st.download_button(
            label="📄 Faltantes PDF",
            data=pdf_faltantes,
            file_name="faltantes_album.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.error("No se pudo generar el PDF de faltantes.")
        st.exception(e)

with g5:
    n_pendientes = len(st.session_state.cromos_pendientes)

    if st.session_state.cambios_pendientes:
        st.markdown(
            f'<span class="pending">Hay {n_pendientes} cromo(s) pendiente(s) de guardar en GitHub.</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="saved">No hay cambios pendientes.</span>',
            unsafe_allow_html=True,
        )

st.markdown("</div>", unsafe_allow_html=True)


# =====================================================
# PILLS DE SELECCIONES
# =====================================================

st.divider()

selecciones_final = list(dict.fromkeys(df["seleccion"].dropna().tolist()))

pill_labels = ["TODOS"]
selecciones_final = ["TODOS"] + selecciones_final

for seleccion in selecciones_final[1:]:
    subset = df[df["seleccion"] == seleccion]

    if len(subset) == 0:
        label = seleccion[:3].upper()
    else:
        codigo_ejemplo = subset["codigo"].astype(str).iloc[0]
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
    default="TODOS",
)

seleccion_actual = pill_map[pill]


# =====================================================
# FILTROS
# =====================================================

st.divider()

f1, f2, f3 = st.columns([1.2, 2.5, 1.2])

with f1:
    estado = st.selectbox(
        "Estado",
        [
            "Todos",
            "Los tengo",
            "Me faltan",
            "Repetidos",
            "Wishlist",
        ],
    )

with f2:
    busqueda = st.text_input("Buscar por código, nombre o selección")

with f3:
    st.write("")
    st.write("")
    ver_repetidos = st.button("🔁 Ver repetidos", use_container_width=True)


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

elif estado == "Wishlist":
    df_filtrado = df_filtrado[
        df_filtrado["wishlist"] == True
    ]

df_filtrado = df_filtrado.sort_values("orden_original")

st.write(f"Mostrando **{len(df_filtrado)}** cromos")

st.divider()


# =====================================================
# GRID DE CROMOS
# =====================================================

COLUMNAS = 4

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
                unsafe_allow_html=True,
            )

            with st.popover("⚙️ Editar"):
                key_base = str(row["codigo"])

                lo_tengo = st.checkbox(
                    "Lo tengo",
                    value=bool(row["lo_tengo"]),
                    key=f"tengo_{key_base}",
                )

                repetidos = st.number_input(
                    "Número de repetidos",
                    min_value=0,
                    value=int(row["repetidos"]),
                    step=1,
                    key=f"rep_{key_base}",
                )

                wishlist = st.checkbox(
                    "Wishlist",
                    value=bool(row["wishlist"]),
                    key=f"wish_{key_base}",
                )

                if st.button(
                    "✅ Guardar cromo",
                    key=f"guardar_cromo_{key_base}",
                    use_container_width=True,
                ):
                    hay_cambio = aplicar_cambio_por_codigo(
                        row["codigo"],
                        lo_tengo,
                        repetidos,
                        wishlist,
                    )

                    if hay_cambio:
                        st.success("Cromo guardado como cambio pendiente.")
                    else:
                        st.info("No había cambios en este cromo.")

                    st.rerun()


# =====================================================
# BOTONES ABAJO
# =====================================================

st.divider()

b1, b2, b3, b4, b5 = st.columns([1.35, 1.35, 1.45, 1.45, 3.2])

with b1:
    if st.button(
        "💾 Guardar todos",
        key="guardar_abajo",
        use_container_width=True,
    ):
        guardar_todos_los_cambios()
        st.rerun()

with b2:
    if st.button(
        "🔄 Recargar",
        key="recargar_abajo",
        use_container_width=True,
    ):
        recargar_desde_github()
        st.rerun()

with b3:
    try:
        pdf_repetidos_abajo = crear_pdf_repetidos(st.session_state.df)
        st.download_button(
            label="📄 Repetidos PDF",
            data=pdf_repetidos_abajo,
            file_name="repetidos_album.pdf",
            mime="application/pdf",
            key="download_repetidos_abajo",
            use_container_width=True,
        )
    except Exception as e:
        st.error("No se pudo generar el PDF de repetidos.")
        st.exception(e)

with b4:
    try:
        pdf_faltantes_abajo = crear_pdf_faltantes(st.session_state.df)
        st.download_button(
            label="📄 Faltantes PDF",
            data=pdf_faltantes_abajo,
            file_name="faltantes_album.pdf",
            mime="application/pdf",
            key="download_faltantes_abajo",
            use_container_width=True,
        )
    except Exception as e:
        st.error("No se pudo generar el PDF de faltantes.")
        st.exception(e)

with b5:
    n_pendientes = len(st.session_state.cromos_pendientes)

    if st.session_state.cambios_pendientes:
        st.warning(f"Hay {n_pendientes} cromo(s) pendiente(s) de guardar en GitHub.")
    else:
        st.success("No hay cambios pendientes.")
