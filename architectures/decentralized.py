"""ARQUITECTURA 3: ORQUESTACION DESCENTRALIZADA (handoffs entre pares).

    Usuario
       |
       v
  [Recepcion] --handoff--> [Agente FAQ]
       |  \\                   ^   |
       |   \\                  |   v
       |    +--handoff--> [Agente Clima] <--handoff--> [Agente Agenda]
       |                      ^                             |
       +----------------------+-----------------------------+

No hay jefe. La Recepcion hace el triage inicial y transfiere el control
(`handoff`) al par adecuado; a partir de ahi cada agente conversa
directamente con el cliente y decide por si mismo si debe transferir a otro
par. Los handoffs son bidireccionales entre los tres especialistas.

La regla critica del negocio se mantiene de dos formas:
  * por prompt: el Agente Agenda debe transferir al Agente Clima si no tiene
    veredicto para la fecha;
  * por codigo: la herramienta `agendar_cita` revalida Open-Meteo y rechaza
    fechas NO_SEGURAS, de modo que el sistema es seguro aunque un agente
    se salte el protocolo.

Ventajas: menos saltos, respuestas mas naturales y especializadas, sin cuello
de botella. Desventajas: control disperso, trazabilidad mas dificil y el
cumplimiento de reglas globales depende de cada agente (o de guardrails en
las herramientas).

Uso:
    python -m architectures.decentralized --demo
"""

from __future__ import annotations

import sys

from agents import Agent
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from core import prompts
from core.cli import run_cli
from core.config import DEFAULT_MODEL
from core.specialists import make_faq_agent, make_scheduling_agent, make_weather_agent
from core.tools import fecha_de_hoy

DESCRIPCION = (
    "Agentes pares que se transfieren el control con handoff().\n"
    "Recepcion hace triage y cada especialista puede pasar el caso a otro."
)

PROTOCOLO_HANDOFF = """
Trabajas en un equipo de pares sin jefe. Cuando la consulta deja de ser de tu
especialidad, transfiere la conversacion al companiero que corresponda en
lugar de improvisar una respuesta:

- Dudas sobre precios, requisitos, logistica o politicas -> Agente FAQ.
- Clima de una fecha o factibilidad de saltar -> Agente Clima.
- Agendar, consultar o cancelar una cita -> Agente Agenda.

Antes de transferir, deja escrito en tu ultima respuesta el contexto relevante
(fecha en formato YYYY-MM-DD, veredicto de clima, nombre y contacto del
cliente) para que el companiero no tenga que volver a preguntarlo.
Nunca transfieras sin haber avanzado en lo que si te toca a ti.
""".strip()

EXTRA_FAQ = f"""
{PROTOCOLO_HANDOFF}

Ademas eres la cara visible del equipo: si el cliente solo saluda o hace una
pregunta general, atiendelo tu y luego transfiere si hace falta.
""".strip()

EXTRA_CLIMA = f"""
{PROTOCOLO_HANDOFF}

Regla propia de tu rol: si el cliente quiere agendar y tu veredicto es IDEAL o
MARGINAL, transfiere al Agente Agenda indicando explicitamente la fecha y el
veredicto. Si el veredicto es NO_SEGURO, NO transfieras a la agenda: explica el
motivo y ofrece evaluar otra fecha dentro de los 16 dias.
""".strip()

EXTRA_AGENDA = f"""
{PROTOCOLO_HANDOFF}

Regla propia de tu rol: solo puedes confirmar una cita si en la conversacion ya
existe un veredicto de clima IDEAL o MARGINAL para esa fecha exacta. Si no lo
hay, transfiere al Agente Clima antes de agendar (o, si el cliente ya te dio
todos los datos, usa tu herramienta `evaluar_condiciones_de_salto` y continua tu).
""".strip()

INSTRUCCIONES_RECEPCION = f"""
{RECOMMENDED_PROMPT_PREFIX}

{prompts.POLITICA_GENERAL}

Eres Recepcion de Parachute S.A. Tu unico trabajo es dar la bienvenida, hacer
una pregunta de aclaracion si de verdad hace falta, y transferir al par
correcto lo antes posible:

- Precios, requisitos, horarios, logistica, politicas -> Agente FAQ.
- Clima de una fecha o si se puede saltar ese dia -> Agente Clima.
- Agendar, reprogramar, consultar o cancelar una cita -> Agente Agenda.

Si el cliente pide agendar sin haber verificado el clima, transfiere primero
al Agente Clima. No respondas preguntas de contenido tu mismo y no anuncies la
transferencia con frases tecnicas: simplemente hazla.
""".strip()


def build_agent() -> Agent:
    """Arma la red de agentes pares con handoffs bidireccionales."""

    agente_faq = make_faq_agent(
        extra_instructions=EXTRA_FAQ,
        prompt_prefix=RECOMMENDED_PROMPT_PREFIX,
    )
    agente_clima = make_weather_agent(
        extra_instructions=EXTRA_CLIMA,
        prompt_prefix=RECOMMENDED_PROMPT_PREFIX,
    )
    agente_agenda = make_scheduling_agent(
        extra_instructions=EXTRA_AGENDA,
        prompt_prefix=RECOMMENDED_PROMPT_PREFIX,
        incluir_herramienta_clima=True,
    )

    recepcion = Agent(
        name="Recepcion",
        handoff_description="Recibe al cliente y lo dirige al especialista adecuado.",
        instructions=INSTRUCCIONES_RECEPCION,
        model=DEFAULT_MODEL,
        tools=[fecha_de_hoy],
    )

    # Handoffs entre pares: cada agente puede transferir a cualquier otro.
    agente_faq.handoffs = [agente_clima, agente_agenda, recepcion]
    agente_clima.handoffs = [agente_agenda, agente_faq, recepcion]
    agente_agenda.handoffs = [agente_clima, agente_faq, recepcion]
    recepcion.handoffs = [agente_faq, agente_clima, agente_agenda]

    return recepcion


def main() -> int:
    return run_cli(build_agent(), "Descentralizada", DESCRIPCION)


if __name__ == "__main__":
    sys.exit(main())
