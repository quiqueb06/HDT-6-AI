"""Genera los diagramas SVG de las tres arquitecturas de orquestacion.

    python diagrams/generar_diagramas.py

Se generan SVG (vectoriales, se ven bien en GitHub y en el PDF) a partir de
esta definicion, para que el diagrama y el codigo no se desincronicen.
"""

from __future__ import annotations

import os
from typing import List, Tuple

W, H = 980, 660

# Diagramas en blanco y negro: todo se dibuja con lineas negras sobre fondo blanco.
NEGRO = "#000000"
COLORS = {
    "bg": "#ffffff",
    "usuario": NEGRO,
    "orquestador": NEGRO,
    "gerente": NEGRO,
    "especialista": NEGRO,
    "tool": NEGRO,
    "linea": NEGRO,
    "linea_suave": NEGRO,
    "texto": NEGRO,
}


def _wrap(texto: str, ancho: int) -> List[str]:
    palabras, lineas, actual = texto.split(), [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if len(prueba) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def box(x, y, w, h, titulo, subtitulo="", color="#1565c0", relleno="#ffffff", dash=False) -> str:
    """Caja redondeada. La altura crece sola si el texto no cabe en `h`."""

    ancho_titulo = max(12, int(w / 9.5))
    ancho_sub = max(16, int(w / 6.2))
    lineas_titulo = _wrap(titulo, ancho_titulo)
    lineas_sub = _wrap(subtitulo, ancho_sub) if subtitulo else []
    necesario = 26 + 17 * (len(lineas_titulo) - 1) + 14 * len(lineas_sub) + 14
    h = max(h, necesario)

    partes = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" '
        f'fill="{relleno}" stroke="{color}" stroke-width="2.5"'
        + (' stroke-dasharray="6 4"' if dash else "")
        + " />",
    ]
    ty = y + 26
    for linea in lineas_titulo:
        partes.append(
            f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" '
            f'font-size="14" font-weight="bold" fill="{COLORS["texto"]}">{linea}</text>'
        )
        ty += 17
    if lineas_sub:
        for linea in lineas_sub:
            partes.append(
                f'<text x="{x + w / 2}" y="{ty + 2}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" '
                f'font-size="11" fill="{COLORS["texto"]}">{linea}</text>'
            )
            ty += 14
    return "\n  ".join(partes)


def arrow(x1, y1, x2, y2, etiqueta="", color=None, doble=False, dash=False, offset=0) -> str:
    color = color or COLORS["linea"]
    marcador = "url(#flecha)" if not dash else "url(#flecha_suave)"
    extra = f' marker-start="{marcador}"' if doble else ""
    linea = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" '
        f'marker-end="{marcador}"{extra}' + (' stroke-dasharray="5 4"' if dash else "") + " />"
    )
    if not etiqueta:
        return linea
    mx, my = (x1 + x2) / 2 + offset, (y1 + y2) / 2 - 6
    ancho = 7 * len(etiqueta) + 10
    return (
        linea
        + f'\n  <rect x="{mx - ancho / 2}" y="{my - 12}" width="{ancho}" height="17" rx="4" fill="{COLORS["bg"]}" />'
        + f'\n  <text x="{mx}" y="{my}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="11" fill="{color}">{etiqueta}</text>'
    )


def tool_list(x, y, w, items: List[str]) -> str:
    alto = 20 + 15 * len(items)
    partes = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{alto}" rx="8" fill="#ffffff" '
        f'stroke="{COLORS["tool"]}" stroke-width="1.5" stroke-dasharray="4 3" />'
    ]
    ty = y + 16
    for item in items:
        partes.append(
            f'<text x="{x + 10}" y="{ty}" font-family="Menlo,Consolas,monospace" font-size="10.5" '
            f'fill="{COLORS["texto"]}">{item}</text>'
        )
        ty += 15
    return "\n  ".join(partes)


def svg(titulo: str, subtitulo: str, cuerpo: str, leyenda: List[Tuple[str, str]]) -> str:
    items = []
    lx = 40
    for color, texto in leyenda:
        items.append(
            f'<rect x="{lx}" y="{H - 42}" width="13" height="13" rx="3" fill="{color}" />'
            f'<text x="{lx + 19}" y="{H - 31}" font-family="Helvetica,Arial,sans-serif" font-size="11.5" '
            f'fill="{COLORS["texto"]}">{texto}</text>'
        )
        lx += 30 + 7.3 * len(texto)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="{COLORS["linea"]}" />
    </marker>
    <marker id="flecha_suave" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="{COLORS["linea_suave"]}" />
    </marker>
  </defs>
  <rect width="{W}" height="{H}" fill="{COLORS["bg"]}" />
  <text x="{W / 2}" y="40" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="22"
        font-weight="bold" fill="{COLORS["texto"]}">{titulo}</text>
  <text x="{W / 2}" y="63" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="13"
        fill="{COLORS["texto"]}">{subtitulo}</text>
  {cuerpo}
  {''.join(items)}
</svg>
"""


FAQ_TOOLS = ["buscar_en_faqs()", "listar_temas_faq()"]
CLIMA_TOOLS = ["fecha_de_hoy()", "consultar_clima()", "evaluar_condiciones_de_salto()"]
AGENDA_TOOLS = ["consultar_disponibilidad()", "agendar_cita()", "listar_citas()", "cancelar_cita()"]

#: Sin leyenda de colores: el diagrama es en blanco y negro.
LEYENDA: List[Tuple[str, str]] = []


def diagrama_centralizada() -> str:
    c = []
    c.append(box(400, 85, 180, 50, "Usuario", color=COLORS["usuario"], relleno="#ffffff"))
    c.append(arrow(490, 135, 490, 175, "consulta"))
    c.append(
        box(330, 175, 320, 74, "Coordinador Parachute", "Unico agente que habla con el cliente", color=COLORS["orquestador"])
    )
    c.append(arrow(400, 249, 175, 320, "as_tool()", offset=-30))
    c.append(arrow(490, 249, 490, 320, "as_tool()"))
    c.append(arrow(580, 249, 805, 320, "as_tool()", offset=30))
    c.append(box(70, 320, 210, 66, "Agente FAQ", "Base de conocimientos", color=COLORS["especialista"]))
    c.append(box(385, 320, 210, 66, "Agente Clima", "Open-Meteo + criterios", color=COLORS["especialista"]))
    c.append(box(700, 320, 210, 66, "Agente Agenda", "Citas y cupos", color=COLORS["especialista"]))
    c.append(arrow(175, 386, 175, 416, color=COLORS["tool"]))
    c.append(arrow(490, 386, 490, 416, color=COLORS["tool"]))
    c.append(arrow(805, 386, 805, 416, color=COLORS["tool"]))
    c.append(tool_list(70, 416, 210, FAQ_TOOLS))
    c.append(tool_list(385, 416, 210, CLIMA_TOOLS))
    c.append(tool_list(700, 416, 210, AGENDA_TOOLS))
    c.append(
        f'<text x="{W / 2}" y="612" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12.5" '
        f'fill="{COLORS["texto"]}">Los especialistas NUNCA hablan con el usuario: devuelven su resultado al coordinador '
        f'(patron manager con as_tool()).</text>'
    )
    c.append(
        f'<text x="{W / 2}" y="633" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12.5" '
        f'fill="{COLORS["texto"]}">Regla de negocio: el coordinador llama primero a evaluar_clima_salto y solo despues a gestionar_cita.</text>'
    )
    return svg("Arquitectura 1 - Orquestacion centralizada", "architectures/centralized.py", "\n  ".join(c), LEYENDA)


def diagrama_jerarquica() -> str:
    c = []
    c.append(box(400, 78, 180, 44, "Usuario", color=COLORS["usuario"], relleno="#ffffff"))
    c.append(arrow(490, 122, 490, 152, "consulta"))
    c.append(box(340, 152, 300, 62, "Director de Servicio", "Nivel 1 - estrategico: clasifica y delega", color=COLORS["orquestador"]))
    c.append(arrow(420, 214, 235, 268, "as_tool()", offset=-25))
    c.append(arrow(560, 214, 700, 268, "as_tool()", offset=25))
    c.append(box(95, 268, 280, 66, "Gerente de Informacion", "Nivel 2 - tactico", color=COLORS["gerente"]))
    c.append(box(600, 268, 300, 66, "Gerente de Operaciones de Vuelo", "Nivel 2 - tactico: exige clima antes de agendar", color=COLORS["gerente"]))
    c.append(arrow(235, 334, 235, 386, "as_tool()"))
    c.append(arrow(690, 334, 600, 386, "as_tool()", offset=-22))
    c.append(arrow(810, 334, 855, 386, "as_tool()", offset=26))
    c.append(box(130, 386, 210, 60, "Agente FAQ", "Nivel 3 - operativo", color=COLORS["especialista"]))
    c.append(box(495, 386, 210, 60, "Agente Clima", "Nivel 3 - operativo", color=COLORS["especialista"]))
    c.append(box(750, 386, 210, 60, "Agente Agenda", "Nivel 3 - operativo", color=COLORS["especialista"]))
    c.append(arrow(235, 446, 235, 472, color=COLORS["tool"]))
    c.append(arrow(600, 446, 600, 472, color=COLORS["tool"]))
    c.append(arrow(855, 446, 855, 472, color=COLORS["tool"]))
    c.append(tool_list(130, 472, 210, FAQ_TOOLS))
    c.append(tool_list(495, 472, 210, CLIMA_TOOLS))
    c.append(tool_list(750, 472, 210, AGENDA_TOOLS))
    c.append(
        f'<text x="{W / 2}" y="612" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12.5" '
        f'fill="{COLORS["texto"]}">El Director no conoce Open-Meteo ni la agenda: solo sabe a que gerencia mandar cada caso.</text>'
    )
    c.append(
        f'<text x="{W / 2}" y="633" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12.5" '
        f'fill="{COLORS["texto"]}">La regla "primero clima, despues cita" vive en el Gerente de Operaciones, duenio de ambos especialistas.</text>'
    )
    return svg("Arquitectura 2 - Orquestacion jerarquica", "architectures/hierarchical.py", "\n  ".join(c), LEYENDA)


def diagrama_descentralizada() -> str:
    c = []
    c.append(box(400, 80, 180, 44, "Usuario", color=COLORS["usuario"], relleno="#ffffff"))
    c.append(arrow(490, 124, 490, 156, "consulta"))
    c.append(box(355, 156, 270, 58, "Recepcion", "Triage inicial, no responde contenido", color=COLORS["orquestador"]))
    c.append(arrow(420, 214, 200, 300, "handoff()", offset=-20))
    c.append(arrow(490, 214, 490, 300, "handoff()"))
    c.append(arrow(560, 214, 780, 300, "handoff()", offset=20))
    c.append(box(90, 300, 220, 64, "Agente FAQ", "Atiende y transfiere", color=COLORS["especialista"]))
    c.append(box(380, 300, 220, 64, "Agente Clima", "Open-Meteo + veredicto", color=COLORS["especialista"]))
    c.append(box(670, 300, 220, 64, "Agente Agenda", "Citas y cupos", color=COLORS["especialista"]))
    # handoffs bidireccionales entre pares
    c.append(arrow(310, 332, 380, 332, "handoff", doble=True))
    c.append(arrow(600, 332, 670, 332, "handoff", doble=True))
    c.append(
        f'<path d="M 90 332 H 42 V 566 H 938 V 332 H 890" fill="none" stroke="{COLORS["linea"]}" stroke-width="2" '
        f'stroke-linejoin="round" marker-end="url(#flecha)" marker-start="url(#flecha)" />'
        f'<rect x="440" y="553" width="100" height="18" rx="4" fill="{COLORS["bg"]}" />'
        f'<text x="490" y="566" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="11" '
        f'fill="{COLORS["linea"]}">handoff</text>'
    )
    c.append(arrow(200, 364, 200, 440, color=COLORS["tool"]))
    c.append(arrow(490, 364, 490, 440, color=COLORS["tool"]))
    c.append(arrow(780, 364, 780, 440, color=COLORS["tool"]))
    c.append(tool_list(90, 440, 220, FAQ_TOOLS))
    c.append(tool_list(380, 440, 220, CLIMA_TOOLS))
    c.append(tool_list(670, 440, 220, AGENDA_TOOLS + ["evaluar_condiciones_de_salto()"]))
    c.append(
        f'<text x="{W / 2}" y="606" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12.5" '
        f'fill="{COLORS["texto"]}">No hay jefe: el agente que recibe el handoff toma el control de la conversacion y habla directo con el usuario.</text>'
    )
    c.append(
        f'<text x="{W / 2}" y="627" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12.5" '
        f'fill="{COLORS["texto"]}">La regla de seguridad se garantiza en codigo: agendar_cita() revalida Open-Meteo y rechaza fechas NO_SEGURAS.</text>'
    )
    return svg("Arquitectura 3 - Orquestacion descentralizada", "architectures/decentralized.py", "\n  ".join(c), LEYENDA)


def _exportar_png(ruta_svg: str) -> None:
    """Exporta una copia PNG si cairosvg esta instalado (opcional)."""

    try:
        import cairosvg  # type: ignore
    except ImportError:
        return
    ruta_png = ruta_svg.replace(".svg", ".png")
    cairosvg.svg2png(url=ruta_svg, write_to=ruta_png, scale=1.5)
    print(f"generado: {ruta_png}")


def main() -> None:
    destino = os.path.dirname(os.path.abspath(__file__))
    archivos = {
        "arquitectura_centralizada.svg": diagrama_centralizada(),
        "arquitectura_jerarquica.svg": diagrama_jerarquica(),
        "arquitectura_descentralizada.svg": diagrama_descentralizada(),
    }
    for nombre, contenido in archivos.items():
        ruta = os.path.join(destino, nombre)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(contenido)
        print(f"generado: {ruta}")
        _exportar_png(ruta)


if __name__ == "__main__":
    main()
