"""ARQUITECTURA 1: ORQUESTACION CENTRALIZADA.

    Usuario
       |
       v
  [Coordinador Parachute]  <-- unico agente que habla con el usuario
       |  as_tool()
       +--> consultar_faqs        (Agente FAQ)
       +--> evaluar_clima_salto   (Agente Clima)
       +--> gestionar_cita        (Agente Agenda)

Un solo agente orquestador recibe TODA la conversacion y decide a que
especialista llamar. Los especialistas se exponen como herramientas con
`as_tool()`, por lo que nunca hablan directamente con el usuario: devuelven
su resultado al coordinador y este redacta la respuesta final.

Ventajas: control total del flujo, un solo punto de politica de seguridad,
facil de auditar. Desventajas: el coordinador es cuello de botella y su
prompt crece con cada requerimiento nuevo.

Uso:
    python -m architectures.centralized                 # modo interactivo
    python -m architectures.centralized --demo          # guion de demostracion
    python -m architectures.centralized --ask "..."     # una sola pregunta
"""

from __future__ import annotations

import sys

from agents import Agent

from core import prompts
from core.cli import run_cli
from core.config import DEFAULT_MODEL
from core.specialists import make_faq_agent, make_scheduling_agent, make_weather_agent
from core.tools import fecha_de_hoy

DESCRIPCION = (
    "Un coordinador unico atiende al cliente y llama a los especialistas\n"
    "(FAQ, Clima y Agenda) como herramientas via as_tool()."
)

INSTRUCCIONES_COORDINADOR = f"""
{prompts.POLITICA_GENERAL}

Eres el Coordinador de Atencion de Parachute S.A. y el UNICO agente que habla
con el cliente. Tienes tres especialistas disponibles como herramientas:

- `consultar_faqs`: dudas sobre precios, requisitos, logistica, politicas.
- `evaluar_clima_salto`: pronostico de Open-Meteo y veredicto de seguridad.
- `gestionar_cita`: disponibilidad, agendar, listar y cancelar citas.

Como orquestas:
1. Identifica que necesita el cliente. Si necesita varias cosas, llama a
   varios especialistas (puedes llamarlos en secuencia en el mismo turno).
2. Para CUALQUIER solicitud de cita, el orden es obligatorio:
   primero `evaluar_clima_salto` y solo despues `gestionar_cita`.
   Nunca confirmes una cita sin el veredicto de clima.
3. Si el veredicto es NO_SEGURO, no agendes: explica el motivo con los valores
   concretos y ofrece evaluar otra fecha dentro de los 16 dias de pronostico.
4. Si el veredicto es MARGINAL, agenda pero advierte que sera tandem con
   instructor experimentado.
5. Si falta informacion del cliente (nombre, contacto, fecha u hora), pidesela
   tu mismo antes de llamar a `gestionar_cita`.
6. Integra todo en UNA sola respuesta al cliente. No menciones que existen
   agentes internos ni nombres de herramientas.
""".strip()


def build_agent() -> Agent:
    """Arma el grafo de la arquitectura centralizada."""

    agente_faq = make_faq_agent()
    agente_clima = make_weather_agent()
    agente_agenda = make_scheduling_agent()

    return Agent(
        name="Coordinador Parachute",
        instructions=INSTRUCCIONES_COORDINADOR,
        model=DEFAULT_MODEL,
        tools=[
            fecha_de_hoy,
            agente_faq.as_tool(
                tool_name="consultar_faqs",
                tool_description=(
                    "Consulta la base de conocimientos de Parachute S.A. sobre precios, requisitos, "
                    "horarios, logistica y politicas. Entrada: la pregunta del cliente."
                ),
            ),
            agente_clima.as_tool(
                tool_name="evaluar_clima_salto",
                tool_description=(
                    "Consulta Open-Meteo para una fecha y devuelve el veredicto de seguridad "
                    "(IDEAL / MARGINAL / NO_SEGURO) con los valores de viento, rafagas, "
                    "precipitacion, nubes y temperatura. Entrada: la fecha deseada."
                ),
            ),
            agente_agenda.as_tool(
                tool_name="gestionar_cita",
                tool_description=(
                    "Gestiona la agenda: consulta disponibilidad, agenda, lista o cancela citas. "
                    "Entrada: la solicitud completa con nombre, contacto, fecha, hora y el "
                    "veredicto de clima ya obtenido."
                ),
            ),
        ],
    )


def main() -> int:
    return run_cli(build_agent(), "Centralizada", DESCRIPCION)


if __name__ == "__main__":
    sys.exit(main())
