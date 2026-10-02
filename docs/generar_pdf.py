"""Genera docs/respuestas.pdf a partir de docs/respuestas.md.

Se mantiene una sola fuente de verdad (el Markdown) y este script lo
convierte a PDF con ReportLab, soportando el subconjunto que usa el
documento: titulos, parrafos, listas, tablas, imagenes y bloques de codigo.

    pip install reportlab
    python docs/generar_pdf.py
"""

from __future__ import annotations

import os
import re
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(BASE, "respuestas.md")
SALIDA = os.path.join(BASE, "respuestas.pdf")

# Documento en blanco y negro, sin colores ni adornos.
NEGRO = colors.black
ANCHO_UTIL = LETTER[0] - 2 * inch


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base["Title"], fontSize=18, leading=22, textColor=NEGRO, spaceAfter=14
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=14, leading=18, textColor=NEGRO,
            spaceBefore=16, spaceAfter=7, keepWithNext=1,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12, leading=15,
            textColor=NEGRO, spaceBefore=12, spaceAfter=5, keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontSize=11, leading=14, textColor=NEGRO,
            fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4, keepWithNext=1,
        ),
        "cuerpo": ParagraphStyle(
            "cuerpo", parent=base["BodyText"], fontSize=10, leading=14.5,
            alignment=TA_JUSTIFY, spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontSize=10, leading=14, alignment=TA_JUSTIFY,
            spaceAfter=2,
        ),
        "celda": ParagraphStyle("celda", parent=base["BodyText"], fontSize=8.5, leading=11, spaceAfter=0),
        "celda_head": ParagraphStyle(
            "celda_head", parent=base["BodyText"], fontSize=8.5, leading=11, spaceAfter=0,
            textColor=NEGRO, fontName="Helvetica-Bold",
        ),
        "codigo": ParagraphStyle("codigo", parent=base["Code"], fontSize=8.5, leading=11.5),
        "pie": ParagraphStyle("pie", parent=base["BodyText"], fontSize=9, textColor=NEGRO),
        "encabezado": ParagraphStyle(
            "encabezado", parent=base["BodyText"], fontSize=10, leading=13, spaceAfter=0
        ),
        "encabezado_der": ParagraphStyle(
            "encabezado_der", parent=base["BodyText"], fontSize=10, leading=13, spaceAfter=0,
            alignment=TA_RIGHT,
        ),
    }


def inline(texto: str) -> str:
    """Convierte el formato inline de Markdown a las etiquetas de ReportLab."""

    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', texto)
    texto = re.sub(r"\*(.+?)\*", r"<i>\1</i>", texto)
    # Links de Markdown y URLs sueltas quedan clickeables (en negro, sin subrayado).
    texto = re.sub(r"\[(.+?)\]\((https?://[^)]+)\)", r'<link href="\2">\1</link>', texto)
    texto = re.sub(r'(?<![">])(https?://[^\s<)]+)', r'<link href="\1">\1</link>', texto)
    return texto


def front_matter(lineas: List[str]):
    """Separa el bloque de metadatos (entre ---) del cuerpo del documento."""

    if not lineas or lineas[0].strip() != "---":
        return {}, lineas

    meta = {}
    i = 1
    while i < len(lineas) and lineas[i].strip() != "---":
        if ":" in lineas[i]:
            clave, valor = lineas[i].split(":", 1)
            meta[clave.strip()] = valor.strip()
        i += 1
    return meta, lineas[i + 1:]


def encabezado(meta: dict, st) -> Table:
    """Encabezado a dos columnas: universidad a la izquierda, estudiante a la derecha."""

    izquierda = "<br/>".join(
        inline(meta[c]) for c in ("universidad", "curso", "semestre") if meta.get(c)
    )
    derecha = "<br/>".join(inline(meta[c]) for c in ("estudiante", "carnet") if meta.get(c))

    t = Table(
        [[Paragraph(izquierda, st["encabezado"]), Paragraph(derecha, st["encabezado_der"])]],
        colWidths=[ANCHO_UTIL * 0.58, ANCHO_UTIL * 0.42],
        hAlign="LEFT",
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.7, NEGRO),
            ]
        )
    )
    return t


def tabla(filas: List[List[str]], st) -> Table:
    encabezado = [Paragraph(inline(c), st["celda_head"]) for c in filas[0]]
    cuerpo = [[Paragraph(inline(c), st["celda"]) for c in fila] for fila in filas[1:]]
    columnas = len(filas[0])
    # La primera columna un poco mas ancha: suele llevar el nombre del criterio.
    if columnas > 2:
        primera = ANCHO_UTIL * 0.28
        resto = (ANCHO_UTIL - primera) / (columnas - 1)
        anchos = [primera] + [resto] * (columnas - 1)
    else:
        anchos = [ANCHO_UTIL / columnas] * columnas

    t = Table([encabezado] + cuerpo, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, NEGRO),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, NEGRO),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def imagen(ruta: str) -> Image:
    from reportlab.lib.utils import ImageReader

    ancho_px, alto_px = ImageReader(ruta).getSize()
    ancho = min(ANCHO_UTIL, 6.2 * inch)
    return Image(ruta, width=ancho, height=ancho * alto_px / ancho_px)


def construir(lineas: List[str], st) -> List:
    flujo: List = []
    i = 0
    parrafo: List[str] = []
    bullets: List[str] = []

    def cerrar_parrafo():
        if parrafo:
            flujo.append(Paragraph(inline(" ".join(parrafo)), st["cuerpo"]))
            parrafo.clear()

    def cerrar_bullets():
        if bullets:
            flujo.append(
                ListFlowable(
                    [ListItem(Paragraph(inline(b), st["bullet"]), leftIndent=14) for b in bullets],
                    bulletType="bullet",
                    bulletFontSize=7,
                    leftIndent=14,
                    spaceAfter=8,
                )
            )
            bullets.clear()

    while i < len(lineas):
        linea = lineas[i].rstrip()

        if linea.startswith("```"):
            cerrar_parrafo(); cerrar_bullets()
            i += 1
            codigo = []
            while i < len(lineas) and not lineas[i].startswith("```"):
                codigo.append(lineas[i].rstrip())
                i += 1
            flujo.append(Preformatted("\n".join(codigo), st["codigo"]))
            flujo.append(Spacer(1, 8))
            i += 1
            continue

        if linea.startswith("|"):
            cerrar_parrafo(); cerrar_bullets()
            filas = []
            while i < len(lineas) and lineas[i].strip().startswith("|"):
                celdas = [c.strip() for c in lineas[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in celdas):
                    filas.append(celdas)
                i += 1
            flujo.append(tabla(filas, st))
            flujo.append(Spacer(1, 10))
            continue

        img = re.match(r"!\[(.*?)\]\((.+?)\)", linea)
        if img:
            cerrar_parrafo(); cerrar_bullets()
            ruta = os.path.normpath(os.path.join(BASE, img.group(2)))
            if os.path.exists(ruta):
                flujo.append(imagen(ruta))
                flujo.append(Spacer(1, 10))
            i += 1
            continue

        if linea.startswith("### "):
            cerrar_parrafo(); cerrar_bullets()
            flujo.append(Paragraph(inline(linea[4:]), st["h3"]))
        elif linea.startswith("## "):
            cerrar_parrafo(); cerrar_bullets()
            flujo.append(Paragraph(inline(linea[3:]), st["h2"]))
        elif linea.startswith("# "):
            cerrar_parrafo(); cerrar_bullets()
            flujo.append(Paragraph(inline(linea[2:]), st["titulo"]))
        elif linea.startswith("- "):
            cerrar_parrafo()
            bullets.append(linea[2:])
        elif not linea.strip():
            cerrar_parrafo(); cerrar_bullets()
        else:
            cerrar_bullets()
            parrafo.append(linea.strip())
        i += 1

    cerrar_parrafo()
    cerrar_bullets()
    return flujo


def _pie_de_pagina(canvas, doc):
    """Numero de pagina centrado, sin mas."""

    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(NEGRO)
    canvas.drawCentredString(LETTER[0] / 2, 0.6 * inch, str(doc.page))
    canvas.restoreState()


def main() -> None:
    with open(ENTRADA, "r", encoding="utf-8") as fh:
        lineas = fh.read().splitlines()

    st = _estilos()
    meta, cuerpo = front_matter(lineas)

    flujo: List = []
    if meta:
        flujo.append(encabezado(meta, st))
        flujo.append(Spacer(1, 16))
    flujo.extend(construir(cuerpo, st))

    doc = SimpleDocTemplate(
        SALIDA,
        pagesize=LETTER,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title="Hoja de trabajo #5 - Orquestacion de sistemas multiagentes",
        author="Parachute S.A. - CC3116",
    )
    doc.build(flujo, onFirstPage=_pie_de_pagina, onLaterPages=_pie_de_pagina)
    print(f"generado: {SALIDA}")


if __name__ == "__main__":
    main()
