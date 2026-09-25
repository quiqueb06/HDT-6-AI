"""Prueba de humo de la logica de negocio, SIN usar LLM ni API key.

Ejercita las integraciones (FAQs, Open-Meteo, reglas de seguridad y agenda)
tal como las consumen los agentes, para verificar que la capa compartida
funciona antes de gastar tokens.

    python -m core.selftest              # usa Open-Meteo real
    python -m core.selftest --mock       # usa datos simulados (sin internet)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

from . import config, faq, scheduling, weather
from .rules import evaluate_conditions


def _titulo(texto: str) -> None:
    print(f"\n{'=' * 62}\n{texto}\n{'=' * 62}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--mock" in argv:
        os.environ["PARACHUTE_WEATHER_MODE"] = "mock"
        config.WEATHER_MODE = "mock"  # type: ignore[misc]

    hoy = weather.today_local()
    print(f"Hoy ({config.LANDING_ZONE.timezone}): {hoy.isoformat()}")
    print(f"Modo de clima: {config.WEATHER_MODE}")

    _titulo("1. Base de conocimientos (FAQs)")
    for consulta in ["cuanto cuesta un salto", "que pasa si llueve", "puedo saltar embarazada"]:
        resultados = faq.search(consulta)
        mejor = resultados[0] if resultados else None
        print(f"- '{consulta}' -> {mejor.id if mejor else 'sin resultados'}")
        if mejor:
            print(f"    {mejor.respuesta[:110]}...")

    _titulo("2. Validacion de la ventana de 16 dias de Open-Meteo")
    fuera = (hoy + timedelta(days=config.MAX_FORECAST_DAYS + 5)).isoformat()
    try:
        weather.validate_forecast_date(fuera)
        print("ERROR: deberia haber rechazado la fecha")
        return 1
    except weather.DateOutOfRangeError as exc:
        print(f"- {fuera} -> rechazada correctamente")
        print(f"    {exc}")

    _titulo("3. Clima + criterios de seguridad")
    for delta in (0, 2, 5, 10):
        fecha = (hoy + timedelta(days=delta)).isoformat()
        try:
            snap = weather.get_forecast(fecha)
        except weather.WeatherError as exc:
            print(f"- {fecha}: no disponible ({exc})")
            continue
        veredicto = evaluate_conditions(
            wind_speed_10m=snap.wind_speed_10m,
            wind_gusts_10m=snap.wind_gusts_10m,
            precipitation=snap.precipitation,
            cloud_cover=snap.cloud_cover,
            temperature_2m=snap.temperature_2m,
        )
        print(
            f"- {fecha} [{snap.fuente}] viento={snap.wind_speed_10m} km/h "
            f"rafagas={snap.wind_gusts_10m} km/h lluvia={snap.precipitation} mm "
            f"nubes={snap.cloud_cover}% temp={snap.temperature_2m}C"
        )
        print(f"    -> {veredicto.estado.value}: {veredicto.resumen}")

    _titulo("4. Agenda de citas")
    fecha_cita = (hoy + timedelta(days=2)).isoformat()
    print(f"- Disponibilidad {fecha_cita}: {scheduling.check_availability(fecha_cita)['horarios_libres']}")
    cita = scheduling.create_appointment(
        cliente="Cliente de prueba",
        contacto="5555-0000",
        fecha=fecha_cita,
        hora="13:00",
        nota_clima="selftest",
    )
    print(f"- Cita creada: {json.dumps(cita.to_dict(), ensure_ascii=False)}")
    print(f"- {scheduling.cancel_appointment(cita.id)['mensaje']}")

    print("\nTodo correcto: la capa compartida esta funcionando.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
