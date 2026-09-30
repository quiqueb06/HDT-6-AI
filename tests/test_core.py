"""Pruebas de la capa de dominio compartida por las tres arquitecturas."""

from __future__ import annotations

import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, faq, scheduling, weather  # noqa: E402
from core.rules import Status, evaluate_conditions  # noqa: E402


# --- Reglas de seguridad ------------------------------------------------------

def test_condiciones_ideales():
    v = evaluate_conditions(wind_speed_10m=12, wind_gusts_10m=18, precipitation=0.0, cloud_cover=15, temperature_2m=26)
    assert v.estado is Status.IDEAL
    assert v.apto_para_saltar is True


@pytest.mark.parametrize("viento", [20.0, 24.0, 28.0])
def test_viento_marginal(viento):
    v = evaluate_conditions(wind_speed_10m=viento, wind_gusts_10m=30, precipitation=0.0, cloud_cover=20)
    assert v.estado is Status.MARGINAL
    assert v.requiere_tandem_experimentado is True


def test_viento_prohibido():
    v = evaluate_conditions(wind_speed_10m=28.1, wind_gusts_10m=30, precipitation=0.0, cloud_cover=10)
    assert v.estado is Status.NO_SEGURO
    assert v.apto_para_saltar is False


def test_rafagas_prohibidas():
    v = evaluate_conditions(wind_speed_10m=10, wind_gusts_10m=35.5, precipitation=0.0, cloud_cover=10)
    assert v.estado is Status.NO_SEGURO


def test_cualquier_precipitacion_prohibe():
    v = evaluate_conditions(wind_speed_10m=5, wind_gusts_10m=10, precipitation=0.1, cloud_cover=5)
    assert v.estado is Status.NO_SEGURO


@pytest.mark.parametrize("nubes,esperado", [(29, Status.IDEAL), (30, Status.MARGINAL), (75, Status.MARGINAL), (76, Status.NO_SEGURO)])
def test_cobertura_de_nubes(nubes, esperado):
    v = evaluate_conditions(wind_speed_10m=5, wind_gusts_10m=10, precipitation=0.0, cloud_cover=nubes)
    assert v.estado is esperado


def test_falta_de_dato_no_autoriza_el_salto():
    v = evaluate_conditions(wind_speed_10m=None, wind_gusts_10m=10, precipitation=0.0, cloud_cover=10)
    assert v.estado is Status.SIN_DATO
    assert v.apto_para_saltar is False


def test_temperatura_no_bloquea():
    v = evaluate_conditions(wind_speed_10m=5, wind_gusts_10m=10, precipitation=0.0, cloud_cover=10, temperature_2m=38)
    assert v.estado is Status.IDEAL


# --- Ventana de pronostico de Open-Meteo --------------------------------------

def test_fecha_dentro_de_la_ventana():
    fecha = (weather.today_local() + timedelta(days=config.MAX_FORECAST_DAYS)).isoformat()
    assert weather.validate_forecast_date(fecha).isoformat() == fecha


def test_fecha_fuera_de_la_ventana():
    fecha = (weather.today_local() + timedelta(days=config.MAX_FORECAST_DAYS + 1)).isoformat()
    with pytest.raises(weather.DateOutOfRangeError):
        weather.validate_forecast_date(fecha)


def test_fecha_pasada():
    fecha = (weather.today_local() - timedelta(days=1)).isoformat()
    with pytest.raises(weather.DateOutOfRangeError):
        weather.validate_forecast_date(fecha)


def test_formato_invalido():
    with pytest.raises(ValueError):
        weather.validate_forecast_date("30 de octubre")


def test_modo_mock_devuelve_las_cinco_variables():
    fecha = (weather.today_local() + timedelta(days=1)).isoformat()
    snap = weather.get_forecast(fecha, mode="mock")
    for campo in ("temperature_2m", "precipitation", "cloud_cover", "wind_speed_10m", "wind_gusts_10m"):
        assert getattr(snap, campo) is not None


# --- FAQs ---------------------------------------------------------------------

def test_faq_encuentra_precios():
    assert faq.search("cuanto cuesta un salto tandem")[0].id == "precios"


def test_faq_sin_resultados():
    assert faq.search("zzz") == []


# --- Agenda -------------------------------------------------------------------

@pytest.fixture()
def agenda_temporal(tmp_path, monkeypatch):
    archivo = tmp_path / "citas.json"
    monkeypatch.setattr(config, "APPOINTMENTS_FILE", str(archivo))
    return archivo


def test_agendar_y_cancelar(agenda_temporal):
    fecha = (weather.today_local() + timedelta(days=3)).isoformat()
    cita = scheduling.create_appointment("Ana Lopez", "5555-1111", fecha, "8 am")
    assert cita.hora == "08:00"
    assert scheduling.list_appointments(cliente="ana")[0]["id"] == cita.id
    assert scheduling.cancel_appointment(cita.id)["ok"] is True


def test_cupo_lleno(agenda_temporal):
    fecha = (weather.today_local() + timedelta(days=3)).isoformat()
    for i in range(config.SLOT_CAPACITY):
        scheduling.create_appointment(f"Cliente {i}", "5555", fecha, "10:00")
    with pytest.raises(scheduling.SchedulingError):
        scheduling.create_appointment("Sobrecupo", "5555", fecha, "10:00")


def test_horario_invalido(agenda_temporal):
    fecha = (weather.today_local() + timedelta(days=3)).isoformat()
    with pytest.raises(scheduling.SchedulingError):
        scheduling.create_appointment("Ana", "5555", fecha, "09:30")


def test_no_se_agenda_fuera_de_la_ventana(agenda_temporal):
    fecha = (weather.today_local() + timedelta(days=config.MAX_FORECAST_DAYS + 3)).isoformat()
    with pytest.raises(weather.DateOutOfRangeError):
        scheduling.create_appointment("Ana", "5555", fecha, "10:00")
