"""Base de conocimientos de FAQs de Parachute S.A.

Recuperacion simple por solapamiento de terminos (sin dependencias externas):
normaliza el texto, quita acentos y palabras vacias, y puntua cada FAQ segun
coincidencias en pregunta, respuesta, categoria y keywords.

La base vive en `core/knowledge/faqs.json`, asi que agregar o editar FAQs no
requiere tocar codigo ni ninguna de las tres arquitecturas.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List

KNOWLEDGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "faqs.json")

_STOPWORDS = {
    "a", "al", "algo", "como", "con", "cual", "cuales", "cuando", "cuanto", "cuanta",
    "de", "del", "donde", "el", "ella", "en", "es", "esta", "hay", "la", "las", "lo",
    "los", "me", "mi", "para", "pero", "por", "porque", "que", "quien", "se", "si",
    "sobre", "su", "un", "una", "uno", "y", "yo", "tengo", "puedo", "debo", "quiero",
    "necesito", "ustedes", "hacer", "sus", "les", "the", "of",
}


@dataclass
class FaqMatch:
    """Una FAQ recuperada junto con su puntaje de relevancia."""

    id: str
    categoria: str
    pregunta: str
    respuesta: str
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "categoria": self.categoria,
            "pregunta": self.pregunta,
            "respuesta": self.respuesta,
            "score": round(self.score, 3),
        }


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", text)


def _same_root(a: str, b: str) -> bool:
    """Heuristica de stemming: comparten raiz si coinciden en los primeros 5 caracteres."""

    if len(a) < 4 or len(b) < 4:
        return False
    if a in b or b in a:
        return True
    return a[:5] == b[:5]


def _field_score(token: str, campo, exacto: float, raiz: float) -> float:
    """Puntua un token contra un campo de la FAQ (coincidencia exacta o por raiz)."""

    if token in campo:
        return exacto
    if any(_same_root(token, palabra) for palabra in campo):
        return raiz
    return 0.0


def _tokens(text: str) -> List[str]:
    return [t for t in _normalize(text).split() if len(t) > 2 and t not in _STOPWORDS]


@lru_cache(maxsize=1)
def load_knowledge_base() -> Dict[str, Any]:
    """Carga (y cachea) el JSON de FAQs."""

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def list_categories() -> List[str]:
    return sorted({faq["categoria"] for faq in load_knowledge_base()["faqs"]})


def list_questions() -> List[Dict[str, str]]:
    return [
        {"id": f["id"], "categoria": f["categoria"], "pregunta": f["pregunta"]}
        for f in load_knowledge_base()["faqs"]
    ]


def search(query: str, top_k: int = 3, min_score: float = 0.05) -> List[FaqMatch]:
    """Devuelve las FAQs mas relevantes para la consulta."""

    q_tokens = _tokens(query)
    if not q_tokens:
        return []

    resultados: List[FaqMatch] = []
    for faq in load_knowledge_base()["faqs"]:
        keywords = {_normalize(k).strip() for k in faq.get("keywords", [])}
        campo_pregunta = set(_tokens(faq["pregunta"]))
        campo_respuesta = set(_tokens(faq["respuesta"]))
        campo_categoria = set(_tokens(faq["categoria"]))

        score = 0.0
        for token in q_tokens:
            score += _field_score(token, keywords, exacto=3.0, raiz=1.5)
            score += _field_score(token, campo_pregunta, exacto=2.0, raiz=1.0)
            score += _field_score(token, campo_categoria, exacto=1.0, raiz=0.5)
            score += _field_score(token, campo_respuesta, exacto=0.5, raiz=0.25)

        if score > 0:
            resultados.append(
                FaqMatch(
                    id=faq["id"],
                    categoria=faq["categoria"],
                    pregunta=faq["pregunta"],
                    respuesta=faq["respuesta"],
                    score=score / len(q_tokens),
                )
            )

    resultados.sort(key=lambda m: m.score, reverse=True)
    return [r for r in resultados if r.score >= min_score][:top_k]
