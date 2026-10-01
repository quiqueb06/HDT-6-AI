"""Provider de promptfoo para la arquitectura jerarquica de Parachute S.A.

Corre una consulta completa contra el Director de Servicio y devuelve la
respuesta final junto con las herramientas de `core.tools` que se ejecutaron
(nombre, argumentos y si devolvieron ok), para que las assertions de
promptfoo puedan verificar la ejecucion de herramientas.

Para que los evals sean reproducibles se usa el clima simulado (mock) y una
agenda vacia en cada consulta. Los agentes corren en Groq (tier gratuito).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv(RAIZ / ".env")
os.environ["PARACHUTE_WEATHER_MODE"] = "mock"
os.environ["PARACHUTE_APPOINTMENTS_FILE"] = str(Path(tempfile.gettempdir()) / "parachute_citas_evals.json")

from agents import OpenAIProvider, RunConfig, Runner, set_tracing_disabled
from openai import AsyncOpenAI

from architectures.hierarchical import build_agent
from core import config, tools

set_tracing_disabled(True)

# Todos los agentes (tambien los anidados con as_tool, que heredan el RunConfig)
# usan Groq, una API compatible con OpenAI, con el modelo de PARACHUTE_MODEL.
RUN_CONFIG = RunConfig(
    model_provider=OpenAIProvider(
        openai_client=AsyncOpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url=os.getenv("BASE_URL", "https://api.groq.com/openai/v1"),
            max_retries=8,
        ),
        use_responses=False,
    )
)

#: Herramientas ejecutadas durante la consulta en curso.
LLAMADAS: list[dict] = []


def _registrar(herramienta) -> None:
    """Envuelve la herramienta para anotar cada ejecucion en LLAMADAS."""

    original = herramienta.on_invoke_tool

    async def invocar(ctx, argumentos):
        resultado = await original(ctx, argumentos)
        LLAMADAS.append(
            {
                "nombre": herramienta.name,
                "argumentos": json.loads(argumentos or "{}"),
                "ok": resultado.get("ok") if isinstance(resultado, dict) else None,
            }
        )
        return resultado

    herramienta.on_invoke_tool = invocar


for _herramienta in tools.ALL_TOOLS:
    _registrar(_herramienta)
    # Groq rechaza el esquema de las herramientas sin parametros si trae "required": [].
    if not _herramienta.params_json_schema.get("required"):
        _herramienta.params_json_schema.pop("required", None)


def call_api(prompt, options, context):
    LLAMADAS.clear()
    Path(config.APPOINTMENTS_FILE).unlink(missing_ok=True)

    resultado = Runner.run_sync(build_agent(), prompt, max_turns=15, run_config=RUN_CONFIG)

    return {
        "output": str(resultado.final_output),
        "metadata": {"herramientas": list(LLAMADAS)},
    }
