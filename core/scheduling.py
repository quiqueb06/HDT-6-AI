"""Agenda de citas de Parachute S.A.

Persistencia simple en JSON (`data/citas.json`) con control de cupos por
horario. Igual que el resto de `core`, no depende de agentes ni de LLMs:
las tres arquitecturas llaman a las mismas funciones.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import config
from .weather import validate_forecast_date


class SchedulingError(RuntimeError):
    """Error de negocio al agendar (cupo lleno, horario invalido, etc.)."""


@dataclass
class Appointment:
    """Una cita de salto confirmada."""

    id: str
    cliente: str
    contacto: str
    fecha: str
    hora: str
    tipo_salto: str
    estado: str  # "confirmada" | "cancelada"
    nota_clima: str
    creada_en: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Persistencia -------------------------------------------------------------

def _ensure_store() -> None:
    carpeta = os.path.dirname(config.APPOINTMENTS_FILE)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    if not os.path.exists(config.APPOINTMENTS_FILE):
        with open(config.APPOINTMENTS_FILE, "w", encoding="utf-8") as fh:
            json.dump({"citas": []}, fh, ensure_ascii=False, indent=2)


def _load() -> List[Dict[str, Any]]:
    _ensure_store()
    with open(config.APPOINTMENTS_FILE, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh).get("citas", [])
        except json.JSONDecodeError:
            return []


def _save(citas: List[Dict[str, Any]]) -> None:
    _ensure_store()
    with open(config.APPOINTMENTS_FILE, "w", encoding="utf-8") as fh:
        json.dump({"citas": citas}, fh, ensure_ascii=False, indent=2)


# --- Reglas de agenda ---------------------------------------------------------

def normalize_time(hora: str) -> str:
    """Normaliza '8', '8:00', '08:00 am' -> '08:00' y valida el horario."""

    texto = (hora or "").strip().lower().replace(".", "")
    am_pm = "pm" if "pm" in texto else ("am" if "am" in texto else "")
    texto = texto.replace("am", "").replace("pm", "").strip()

    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", texto)
    if not match:
        raise SchedulingError(
            f"Hora invalida: '{hora}'. Los horarios disponibles son {', '.join(config.AVAILABLE_SLOTS)}."
        )

    horas = int(match.group(1))
    minutos = int(match.group(2) or 0)
    if am_pm == "pm" and horas < 12:
        horas += 12
    if am_pm == "am" and horas == 12:
        horas = 0

    normalizada = f"{horas:02d}:{minutos:02d}"
    if normalizada not in config.AVAILABLE_SLOTS:
        raise SchedulingError(
            f"El horario {normalizada} no existe. Parachute S.A. opera unicamente a las "
            f"{', '.join(config.AVAILABLE_SLOTS)}."
        )
    return normalizada


def check_availability(fecha: str) -> Dict[str, Any]:
    """Cupos libres por horario para una fecha (valida la ventana de 16 dias)."""

    dia = validate_forecast_date(fecha).isoformat()
    citas = [c for c in _load() if c["fecha"] == dia and c["estado"] == "confirmada"]
    ocupados: Dict[str, int] = {}
    for cita in citas:
        ocupados[cita["hora"]] = ocupados.get(cita["hora"], 0) + 1

    disponibilidad = [
        {
            "hora": slot,
            "cupos_libres": config.SLOT_CAPACITY - ocupados.get(slot, 0),
            "capacidad": config.SLOT_CAPACITY,
        }
        for slot in config.AVAILABLE_SLOTS
    ]
    return {
        "fecha": dia,
        "disponibilidad": disponibilidad,
        "horarios_libres": [d["hora"] for d in disponibilidad if d["cupos_libres"] > 0],
    }


def create_appointment(
    cliente: str,
    contacto: str,
    fecha: str,
    hora: str,
    tipo_salto: str = "tandem",
    nota_clima: str = "",
) -> Appointment:
    """Crea una cita. Asume que el clima ya fue validado por el sistema."""

    dia = validate_forecast_date(fecha).isoformat()
    slot = normalize_time(hora)

    if not (cliente or "").strip():
        raise SchedulingError("Falta el nombre del cliente para confirmar la cita.")
    if not (contacto or "").strip():
        raise SchedulingError("Falta un telefono o correo de contacto para confirmar la cita.")

    disponibilidad = check_availability(dia)
    libres = {d["hora"]: d["cupos_libres"] for d in disponibilidad["disponibilidad"]}
    if libres.get(slot, 0) <= 0:
        raise SchedulingError(
            f"El horario {slot} del {dia} ya no tiene cupo. "
            f"Horarios libres: {', '.join(disponibilidad['horarios_libres']) or 'ninguno'}."
        )

    cita = Appointment(
        id=f"PCH-{uuid.uuid4().hex[:6].upper()}",
        cliente=cliente.strip(),
        contacto=contacto.strip(),
        fecha=dia,
        hora=slot,
        tipo_salto=tipo_salto.strip() or "tandem",
        estado="confirmada",
        nota_clima=nota_clima.strip(),
        creada_en=datetime.now().isoformat(timespec="seconds"),
    )

    citas = _load()
    citas.append(cita.to_dict())
    _save(citas)
    return cita


def list_appointments(cliente: Optional[str] = None, fecha: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista citas filtrando opcionalmente por cliente y/o fecha."""

    citas = _load()
    if cliente:
        objetivo = cliente.strip().lower()
        citas = [c for c in citas if objetivo in c["cliente"].lower()]
    if fecha:
        citas = [c for c in citas if c["fecha"] == fecha.strip()]
    return citas


def cancel_appointment(appointment_id: str) -> Dict[str, Any]:
    """Cancela una cita por su codigo."""

    citas = _load()
    objetivo = (appointment_id or "").strip().upper()
    for cita in citas:
        if cita["id"].upper() == objetivo:
            if cita["estado"] == "cancelada":
                return {"ok": True, "mensaje": f"La cita {cita['id']} ya estaba cancelada.", "cita": cita}
            cita["estado"] = "cancelada"
            _save(citas)
            return {"ok": True, "mensaje": f"Cita {cita['id']} cancelada.", "cita": cita}
    raise SchedulingError(f"No existe ninguna cita con el codigo {appointment_id}.")
