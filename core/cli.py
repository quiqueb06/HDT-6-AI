"""Runner comun para las tres arquitecturas.

Cada programa (`architectures/centralized.py`, `hierarchical.py`,
`decentralized.py`) solo arma su grafo de agentes y llama a `run_cli()`.
De esa forma la experiencia de usuario, la memoria de conversacion, el
modo demo y la traza de ejecucion son identicos y la comparacion entre
arquitecturas es justa.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, List, Optional

from agents import Agent, RunHooks, Runner, SQLiteSession, set_tracing_disabled

from . import config

BANNER = """
==============================================================
  Parachute S.A. - Asistente multiagente
  Arquitectura: {arquitectura}
==============================================================
{descripcion}

Escribe tu consulta (o 'salir' para terminar).
""".strip()

#: Guion de demostracion que ejercita los tres requerimientos funcionales.
DEMO_PREGUNTAS = [
    "Hola, cuanto cuesta un salto tandem y que necesito llevar?",
    "Como estara el clima en 3 dias para saltar?",
    "Perfecto, quiero agendar para esa fecha a las 10:00. Soy Ana Lopez, mi telefono es 5555-1111.",
    "Y se puede para dentro de 30 dias?",
]


class TrazaHooks(RunHooks):
    """Imprime que agente actua y que herramienta usa (util para comparar arquitecturas)."""

    def __init__(self, activo: bool = True) -> None:
        self.activo = activo
        self.eventos: List[str] = []

    def _log(self, texto: str) -> None:
        self.eventos.append(texto)
        if self.activo:
            print(f"   \033[90m{texto}\033[0m", flush=True)

    async def on_agent_start(self, context, agent) -> None:  # type: ignore[override]
        self._log(f"[agente] -> {agent.name}")

    async def on_tool_start(self, context, agent, tool) -> None:  # type: ignore[override]
        self._log(f"[tool]   {agent.name} llama a {tool.name}")

    async def on_handoff(self, context, from_agent, to_agent) -> None:  # type: ignore[override]
        self._log(f"[handoff] {from_agent.name} ==> {to_agent.name}")


def _check_api_key() -> bool:
    if os.getenv("OPENAI_API_KEY"):
        return True
    print(
        "\nFalta la variable de entorno OPENAI_API_KEY.\n"
        "  export OPENAI_API_KEY='sk-...'\n"
        "Si solo quieres verificar la logica de negocio sin LLM, corre:\n"
        "  python -m core.selftest\n",
        file=sys.stderr,
    )
    return False


def build_parser(arquitectura: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Asistente de Parachute S.A. - orquestacion {arquitectura}."
    )
    parser.add_argument("--ask", metavar="TEXTO", help="Hace una sola pregunta y termina.")
    parser.add_argument("--demo", action="store_true", help="Corre un guion de preguntas de demostracion.")
    parser.add_argument(
        "--mock-weather",
        action="store_true",
        help="Usa datos de clima simulados (sin llamar a Open-Meteo).",
    )
    parser.add_argument("--sin-traza", action="store_true", help="Oculta la traza de agentes y herramientas.")
    parser.add_argument(
        "--session",
        default=None,
        help="Nombre de la sesion de memoria (por defecto una por arquitectura).",
    )
    return parser


def _responder(agente: Agent, pregunta: str, session: Any, hooks: TrazaHooks) -> str:
    resultado = Runner.run_sync(agente, pregunta, session=session, hooks=hooks, max_turns=15)
    ultimo = getattr(resultado, "last_agent", None)
    if ultimo is not None and hooks.activo:
        print(f"   \033[90m[cierra]  {ultimo.name}\033[0m", flush=True)
    return str(resultado.final_output)


def run_cli(
    agente_entrada: Agent,
    arquitectura: str,
    descripcion: str,
    argv: Optional[List[str]] = None,
) -> int:
    """Punto de entrada compartido por los tres programas."""

    args = build_parser(arquitectura).parse_args(argv)

    if args.mock_weather:
        os.environ["PARACHUTE_WEATHER_MODE"] = "mock"
        config.WEATHER_MODE = "mock"  # type: ignore[misc]

    if not _check_api_key():
        return 2

    if not os.getenv("OPENAI_AGENTS_TRACING", ""):
        set_tracing_disabled(True)

    hooks = TrazaHooks(activo=not args.sin_traza)
    session = SQLiteSession(args.session or f"parachute-{arquitectura.lower()}")

    print(BANNER.format(arquitectura=arquitectura, descripcion=descripcion))
    if config.WEATHER_MODE == "mock":
        print("\n[modo clima simulado: los datos no vienen de Open-Meteo]")

    if args.ask:
        print(f"\n> {args.ask}")
        print(f"\n{_responder(agente_entrada, args.ask, session, hooks)}\n")
        return 0

    preguntas = DEMO_PREGUNTAS if args.demo else None
    if preguntas:
        for pregunta in preguntas:
            print(f"\n> {pregunta}")
            print(f"\n{_responder(agente_entrada, pregunta, session, hooks)}")
        print()
        return 0

    while True:
        try:
            pregunta = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego, cielos despejados!")
            return 0
        if not pregunta:
            continue
        if pregunta.lower() in {"salir", "exit", "quit", "q"}:
            print("Hasta luego, cielos despejados!")
            return 0
        try:
            print(f"\n{_responder(agente_entrada, pregunta, session, hooks)}")
        except Exception as exc:  # pragma: no cover - errores de red/LLM
            print(f"\n[error] {exc}")
