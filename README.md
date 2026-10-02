# Hoja de trabajo #6 - Evals (CC3116)

**Universidad del Valle de Guatemala**  
AI ENGINEERING CREATIVITY - Cuarto Semestre  
Quique Bran - Carnet 25302

Evals con [promptfoo](https://www.promptfoo.dev/) del asistente multiagente de la hoja #5,
usando la arquitectura **jerarquica** (la arquitectura objetivo segun
[`docs/respuestas.md`](docs/respuestas.md)). El codigo de la hoja #5 se mantiene igual y se
documenta mas abajo.

## Que se evalua

`promptfooconfig.yaml` tiene 8 casos: 4 de preguntas frecuentes y 4 de agenda de citas. Cada
caso combina los cuatro tipos de eval que pide la hoja:

| Tipo | Assertion de promptfoo | Que verifica |
|---|---|---|
| Factuality | `factuality` | La respuesta coincide con el dato de referencia (precio, requisitos, horarios, cita confirmada, rechazo por clima, ventana de 16 dias). |
| Deterministico | `contains`, `contains-all`, `icontains`, `regex`, `not-regex` | Montos (`Q2,200`), horarios, codigo de cita `PCH-XXXXXX`, mencion de los 16 dias, que no se emita un codigo cuando no se agenda. |
| Latencia | `latency` | 30 s para FAQ y 5 min para agenda (ver nota de Groq). |
| Ejecucion de herramientas | `javascript` | Que se llamo `buscar_en_faqs`; que `evaluar_condiciones_de_salto` se llamo con la fecha correcta **antes** de `agendar_cita`; que `agendar_cita` recibio fecha, hora y cliente correctos; que no se agenda en dias inseguros ni fuera de la ventana. |

Casos:

- FAQ: precio del salto tandem, requisitos de edad y peso, horarios, y una pregunta que no
  esta en la base (venta de comida).
- Agenda: cita en un dia con clima ideal, intento en un dia con lluvia, fecha fuera de los 16
  dias de pronostico y consulta de clima sin agendar.

## Como funciona

- `evals/provider.py`: provider de Python para promptfoo. Arma el agente de
  `architectures/hierarchical.py`, corre la consulta y devuelve la respuesta junto con las
  herramientas de `core/tools.py` que se ejecutaron (`metadata.herramientas`: nombre,
  argumentos y si devolvieron `ok`). Las assertions `javascript` leen esa lista.
- Para que los resultados sean reproducibles, el provider usa el clima simulado
  (`PARACHUTE_WEATHER_MODE=mock`) y una agenda vacia en cada consulta.
- `evals/fechas.py`: calcula las fechas de los casos de agenda (la primera fecha con clima
  IDEAL y la primera con lluvia dentro de los 16 dias, y una fecha a 30 dias), asi los casos
  no dependen del dia en que se corren.

### Nota sobre Groq

Los agentes y el grader corren en el tier gratuito de [Groq](https://console.groq.com/keys)
(`openai/gpt-oss-20b` para los agentes, definido en `PARACHUTE_MODEL`, y `qwen/qwen3.8-27b`
para calificar factuality). El provider apunta el SDK de agentes a Groq con un `RunConfig`,
sin cambiar el codigo de la hoja #5.

El tier gratuito limita a 8,000 tokens por minuto y 200,000 tokens por dia por modelo, y el
flujo de agenda pasa por tres niveles de agentes. Por eso esas consultas tardan minutos y los
casos se corren uno por uno con una pausa de 30 s.

## Resultados

El reporte entregado ([`evals/reporte.html`](evals/reporte.html)) se genero con
`openai/gpt-oss-120b` para los agentes y `openai/gpt-oss-20b` como grader:

- **3 casos pasaron** todas sus assertions (factuality, deterministicas, herramientas y
  latencia de 3 a 16 s): precio, requisitos de edad y peso, y horarios.
- **5 casos quedaron en ERROR** (la pregunta fuera de la base y los 4 de agenda): no llegaron
  a evaluarse porque se agoto la cuota diaria gratuita de Groq para `openai/gpt-oss-120b`
  (200,000 tokens) a mitad de la corrida. No son fallas del agente.

Despues se cambio la configuracion a `openai/gpt-oss-20b` (agentes) y `qwen/qwen3.8-27b`
(grader), que es la que queda en el repositorio, para poder reintentar los casos con
`npx promptfoo@latest retry <evalId> -c promptfooconfig.yaml`. Ese reintento no se incluyo en
el reporte entregado.

## Correr los evals

Requiere Node.js 20 o superior.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Crear un `.env` con:

```
GROQ_API_KEY=...
BASE_URL=https://api.groq.com/openai/v1
PARACHUTE_MODEL=openai/gpt-oss-20b
PROMPTFOO_PYTHON=C:\ruta\al\repo\.venv\Scripts\python.exe
```

`PROMPTFOO_PYTHON` (ruta absoluta) hace que promptfoo use el Python del entorno virtual.

Y correr:

```
npx promptfoo@latest eval -c promptfooconfig.yaml --env-file .env --no-cache -j 1 -o evals/reporte.html -o evals/reporte.json
```

`--no-cache` es necesario para que promptfoo mida la latencia. El reporte queda en
[`evals/reporte.html`](evals/reporte.html) (y en JSON en `evals/reporte.json`); tambien se
puede ver con `npx promptfoo@latest view`.

---

# Hoja de trabajo #5 - Orquestacion de sistemas multiagentes (CC3116)

Asistente multiagente para **Parachute S.A.** implementado **tres veces**, cambiando
unicamente la arquitectura de orquestacion: **centralizada**, **jerarquica** y
**descentralizada**.

Los tres programas resuelven exactamente el mismo problema:

1. Responder preguntas frecuentes desde una base de conocimientos.
2. Consultar el clima de la zona de aterrizaje en la API gratuita de
   [Open-Meteo](https://open-meteo.com/) para la fecha que pide el cliente.
3. Calendarizar la cita **solo si** las condiciones de ese dia son seguras para saltar,
   y corregir al usuario cuando pide una fecha a mas de 16 dias (limite del pronostico).

Las respuestas a las preguntas de la hoja de trabajo estan en
[`docs/respuestas.pdf`](docs/respuestas.pdf) (fuente en [`docs/respuestas.md`](docs/respuestas.md)).

---

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."     # Windows: set OPENAI_API_KEY=sk-...
```

## Ejecucion

Cada arquitectura es un programa independiente con la misma interfaz:

```bash
python -m architectures.centralized       # modo conversacion
python -m architectures.hierarchical
python -m architectures.decentralized
```

Opciones disponibles en los tres:

| Opcion | Descripcion |
|---|---|
| `--demo` | Corre un guion de preguntas que ejercita los tres requerimientos |
| `--ask "texto"` | Hace una sola pregunta y termina |
| `--mock-weather` | Usa clima simulado, sin llamar a Open-Meteo |
| `--sin-traza` | Oculta la traza de agentes y herramientas |

Ejemplo:

```bash
python -m architectures.hierarchical --ask "Quiero saltar el proximo sabado, se puede?"
```

Durante la ejecucion se imprime la traza para poder comparar arquitecturas:

```
   [agente] -> Director de Servicio
   [tool]   Director de Servicio llama a gerencia_operaciones
   [agente] -> Gerente de Operaciones de Vuelo
   [tool]   Gerente de Operaciones de Vuelo llama a agente_clima
   [agente] -> Agente Clima
   [tool]   Agente Clima llama a evaluar_condiciones_de_salto
```

### Sin API key

La logica de negocio se puede verificar sin gastar tokens:

```bash
python -m core.selftest --mock    # FAQs, ventana de 16 dias, clima, reglas y agenda
pytest -q                         # 24 pruebas unitarias
```

---

## Las tres arquitecturas

### 1. Centralizada - `architectures/centralized.py`

![Arquitectura centralizada](diagrams/arquitectura_centralizada.png)

Un solo **Coordinador** conversa con el cliente y usa a los tres especialistas como
herramientas mediante `as_tool()`. Los especialistas nunca hablan con el usuario:
devuelven su resultado al coordinador, que redacta la respuesta final.

### 2. Jerarquica - `architectures/hierarchical.py`

![Arquitectura jerarquica](diagrams/arquitectura_jerarquica.png)

Tres niveles: **Director de Servicio** -> **gerencias de area** (Informacion y
Operaciones de Vuelo) -> **especialistas**. La regla critica "primero clima, despues
cita" vive en el Gerente de Operaciones, que es duenio de los dos agentes involucrados.

### 3. Descentralizada - `architectures/decentralized.py`

![Arquitectura descentralizada](diagrams/arquitectura_descentralizada.png)

Sin jefe: **Recepcion** hace el triage y transfiere el control con `handoff()`.
Cada especialista habla directo con el cliente y puede transferir a otro par.
Como ningun agente puede garantizar una regla global, la restriccion de seguridad
se aplica en codigo dentro de `agendar_cita()`.

Los diagramas se regeneran con `python diagrams/generar_diagramas.py`.

---

## Estructura del proyecto

```
core/                      capa compartida (no sabe nada de agentes)
  config.py                coordenadas, umbrales, horarios, modelo
  weather.py               cliente Open-Meteo (current / daily, ventana de 16 dias)
  rules.py                 motor de reglas: IDEAL / MARGINAL / NO_SEGURO
  faq.py                   base de conocimientos + recuperacion
  knowledge/faqs.json      contenido de las FAQs
  scheduling.py            agenda de citas con cupos por horario
  tools.py                 las 9 function_tool que usan las 3 arquitecturas
  prompts.py               instrucciones por rol
  specialists.py           fabricas de los agentes FAQ / Clima / Agenda
  cli.py                   runner comun (REPL, demo, traza)
  selftest.py              prueba de la logica sin LLM

architectures/             lo unico que cambia entre entregables
  centralized.py           orquestacion centralizada
  hierarchical.py          orquestacion jerarquica
  decentralized.py         orquestacion descentralizada

diagrams/                  diagramas SVG/PNG/Mermaid + su generador
docs/                      respuestas.md, respuestas.pdf y el generador de PDF
tests/                     pruebas unitarias de la capa compartida
```

### Por que esta separacion

Parachute S.A. advirtio que seguira agregando requerimientos funcionales. Por eso toda
la logica de integracion vive en `core/` y se expone una sola vez como herramientas:

- Agregar un requerimiento = agregar una herramienta en `core/tools.py` y colgarla del
  especialista que corresponda. Las tres arquitecturas la heredan sin cambios.
- Cambiar de arquitectura = cambiar el cableado de agentes, sin tocar integraciones
  ni reglas de negocio.

---

## Integracion con Open-Meteo

- Coordenadas fijas de la zona de aterrizaje: **14.013722, -90.771611**.
- Para **hoy** se usa el bloque `current`; para fechas futuras, el bloque `daily`
  (maximos de viento y rafagas del dia, acumulado de lluvia y promedio de nubosidad).
- Variables obtenidas: `wind_gusts_10m`, `temperature_2m`, `precipitation`,
  `cloud_cover` y `wind_speed_10m`.
- Open-Meteo pronostica hasta **16 dias**; si el cliente pide una fecha posterior,
  el sistema lo corrige y le indica la ultima fecha con pronostico disponible.

## Criterios para autorizar un salto

| Variable | Ideal | Marginal | No seguro / prohibido |
|---|---|---|---|
| Viento en superficie (`wind_speed_10m`) | < 20 km/h | 20 - 28 km/h (solo tandem experimentado) | > 28 km/h |
| Rafagas (`wind_gusts_10m`) | <= 35 km/h | - | > 35 km/h |
| Precipitacion (`precipitation`) | 0.0 mm | - | > 0.0 mm |
| Cobertura de nubes (`cloud_cover`) | < 30% | 30 - 75% | > 75% |
| Temperatura (`temperature_2m`) | informativa | informativa | no bloquea |

El veredicto global es el **peor** de los criterios. Si Open-Meteo no devuelve alguna de
las cuatro variables criticas, el resultado es `SIN_DATO` y tampoco se autoriza el salto.

## Configuracion opcional

Ver [`.env.example`](.env.example): `PARACHUTE_MODEL`, `PARACHUTE_WEATHER_MODE`
(`live` o `mock`) y `PARACHUTE_APPOINTMENTS_FILE`.
