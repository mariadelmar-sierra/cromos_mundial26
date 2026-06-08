import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


COLUMNAS_BASE = [
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


def convertir_bool(valor):
    """Convierte TRUE/FALSE, 0/1, sí/no, etc. a booleano."""
    if isinstance(valor, bool):
        return valor

    if pd.isna(valor):
        return False

    valor = str(valor).strip().lower()
    return valor in ["true", "1", "yes", "sí", "si", "x"]


def preparar_df(df):
    """
    Normaliza columnas y tipos igual que en la app.
    Mantiene el orden mediante orden_original.
    """
    df = df.copy()

    for col in COLUMNAS_BASE:
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

    df["repetidos"] = pd.to_numeric(df["repetidos"], errors="coerce").fillna(0).astype(int)
    df.loc[df["repetidos"] < 0, "repetidos"] = 0

    df["orden_original"] = pd.to_numeric(df["orden_original"], errors="coerce")
    mask = df["orden_original"].isna()
    df.loc[mask, "orden_original"] = df.index[mask]
    df["orden_original"] = df["orden_original"].astype(int)

    return df[COLUMNAS_BASE].sort_values("orden_original").reset_index(drop=True)


def crear_pdf_repetidos(df, titulo="Lista de cromos repetidos"):
    """
    Crea un PDF en memoria con los cromos repetidos.

    Recibe:
        df: DataFrame con los datos del álbum.

    Devuelve:
        bytes del PDF, listo para usar con st.download_button.
    """
    df = preparar_df(df)
    repetidos = df[df["repetidos"] > 0].copy()

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=8,
    )

    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=14,
    )

    section_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#222222"),
        spaceBefore=12,
        spaceAfter=6,
    )

    normal_style = ParagraphStyle(
        "NormalSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )

    story = []

    total_repetidos = int(repetidos["repetidos"].sum())
    total_cromos_distintos = len(repetidos)

    story.append(Paragraph(titulo, title_style))
    story.append(
        Paragraph(
            f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - "
            f"{total_cromos_distintos} cromo(s) distinto(s), {total_repetidos} repetido(s) en total",
            subtitle_style,
        )
    )

    if repetidos.empty:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("No hay cromos repetidos actualmente.", styles["Normal"]))
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    # Orden de selecciones exactamente como aparece en la app/dataset.
    selecciones_ordenadas = list(dict.fromkeys(repetidos["seleccion"].dropna().tolist()))

    for seleccion in selecciones_ordenadas:
        bloque = repetidos[repetidos["seleccion"] == seleccion].copy()
        bloque = bloque.sort_values("orden_original")

        total_sel = int(bloque["repetidos"].sum())

        story.append(
            Paragraph(
                f"{seleccion} - {total_sel} repetido(s)",
                section_style,
            )
        )

        data = [["Código", "Nombre", "Tipo", "Repetidos"]]

        for _, row in bloque.iterrows():
            data.append(
                [
                    Paragraph(str(row["codigo"]), normal_style),
                    Paragraph(str(row["nombre"]), normal_style),
                    Paragraph(str(row["tipo"]), normal_style),
                    Paragraph(str(int(row["repetidos"])), normal_style),
                ]
            )

        table = Table(
            data,
            colWidths=[2.2 * cm, 9.0 * cm, 3.0 * cm, 2.4 * cm],
            repeatRows=1,
        )

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#222222")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        story.append(table)
        story.append(Spacer(1, 0.2 * cm))

    doc.build(story)

    buffer.seek(0)
    return buffer.getvalue()


def guardar_pdf_repetidos_desde_csv(
    csv_path="album_guardado.csv",
    output_path="repetidos_album.pdf",
):
    """
    Uso como script independiente:
        python generar_repetidos_pdf.py

    Lee album_guardado.csv y crea repetidos_album.pdf.
    """
    df = pd.read_csv(csv_path)
    pdf_bytes = crear_pdf_repetidos(df)

    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    return output_path


if __name__ == "__main__":
    ruta = guardar_pdf_repetidos_desde_csv()
    print(f"PDF generado: {ruta}")
