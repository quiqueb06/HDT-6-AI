"""Fabricas de agentes especialistas.

Cada funcion construye un `Agent` del SDK de OpenAI Agents con las
herramientas y el prompt que le corresponden a ese rol. Las tres
arquitecturas usan estas mismas fabricas: lo unico que cambia es el cableado
(`as_tool()` para centralizada/jerarquica, `handoffs` para descentralizada).

Los parametros `extra_instructions` y `handoffs` permiten adaptar un agente a
una arquitectura sin duplicar su logica ni su prompt base.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

from agents import Agent

from . import prompts, tools
from .config import DEFAULT_MODEL


def _instructions(base: str, extra: Optional[str], prefix: Optional[str] = None) -> str:
    partes = [p for p in (prefix, base, extra) if p]
    return "\n\n".join(partes)


def make_faq_agent(
    extra_instructions: Optional[str] = None,
    handoffs: Optional[Sequence[Agent]] = None,
    prompt_prefix: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    name: str = "Agente FAQ",
) -> Agent:
    """Especialista en la base de conocimientos (preguntas frecuentes)."""

    return Agent(
        name=name,
        handoff_description="Responde preguntas sobre precios, requisitos, logistica y politicas de Parachute S.A.",
        instructions=_instructions(prompts.FAQ_AGENT, extra_instructions, prompt_prefix),
        tools=list(tools.FAQ_TOOLS),
        handoffs=list(handoffs or []),
        model=model,
    )


def make_weather_agent(
    extra_instructions: Optional[str] = None,
    handoffs: Optional[Sequence[Agent]] = None,
    prompt_prefix: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    name: str = "Agente Clima",
) -> Agent:
    """Especialista en Open-Meteo y en los criterios de seguridad de salto."""

    return Agent(
        name=name,
        handoff_description="Consulta Open-Meteo y dictamina si una fecha es IDEAL, MARGINAL o NO_SEGURA para saltar.",
        instructions=_instructions(prompts.WEATHER_AGENT, extra_instructions, prompt_prefix),
        tools=list(tools.WEATHER_TOOLS),
        handoffs=list(handoffs or []),
        model=model,
    )


def make_scheduling_agent(
    extra_instructions: Optional[str] = None,
    handoffs: Optional[Sequence[Agent]] = None,
    prompt_prefix: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    name: str = "Agente Agenda",
    incluir_herramienta_clima: bool = True,
) -> Agent:
    """Especialista en agendar, listar y cancelar citas.

    `incluir_herramienta_clima` le da acceso directo a la evaluacion de clima.
    En la arquitectura descentralizada esto es necesario porque no hay un jefe
    que le pase el veredicto; en las otras dos se mantiene como red de
    seguridad (la herramienta `agendar_cita` revalida el clima de todos modos).
    """

    herramientas: List[Any] = list(tools.SCHEDULING_TOOLS)
    if incluir_herramienta_clima:
        herramientas.append(tools.evaluar_condiciones_de_salto)

    return Agent(
        name=name,
        handoff_description="Agenda, consulta y cancela citas de salto respetando cupos y veredicto de clima.",
        instructions=_instructions(prompts.SCHEDULING_AGENT, extra_instructions, prompt_prefix),
        tools=herramientas,
        handoffs=list(handoffs or []),
        model=model,
    )
