"""Wrapper autour du SDK Cerebras avec retry, backoff adaptatif et parsing JSON tolérant."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from cerebras.cloud.sdk import Cerebras

from . import config


_RETRY_REGEX = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s")
_client: Cerebras | None = None


def get_client() -> Cerebras:
    global _client
    if not config.has_cerebras_key():
        raise RuntimeError(
            "Clé API Cerebras manquante. Ajoute CEREBRAS_API_KEY dans ton .env "
            "(inscription gratuite sur https://cloud.cerebras.ai)."
        )
    if _client is None:
        _client = Cerebras(api_key=config.CEREBRAS_API_KEY)
    return _client


def _parse_retry_after(error_msg: str) -> float:
    m = _RETRY_REGEX.search(error_msg)
    if not m:
        return 30.0
    mins = int(m.group(1)) if m.group(1) else 0
    secs = float(m.group(2))
    return mins * 60 + secs


def _extract_json(raw: str | None) -> Any:
    """Parse JSON tolérant : retire les fences ```json et tente d'extraire un objet à défaut."""
    if not raw:
        raise RuntimeError(
            "Le modèle n'a rien renvoyé (réponse vide). "
            "Essaie de réduire la taille du prompt ou d'augmenter max_tokens."
        )
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise RuntimeError(f"JSON invalide ou tronqué :\n{raw[-500:]}")


def call_llm(
    messages: list[dict],
    max_tokens: int = 4000,
    temperature: float = 0.3,
    json_mode: bool = True,
    reasoning_effort: str = "low",
    max_retries: int = 3,
) -> Any:
    """Appelle Cerebras avec retry adaptatif sur les rate limits.

    json_mode=True : force response_format JSON et retourne un objet parsé.
    json_mode=False : retourne le texte brut tel quel.

    NB : si le modèle renvoie content=None (peut arriver quand reasoning_effort est élevé
    et que tout le budget tokens passe en reasoning interne), on lève une RuntimeError
    explicite plutôt que de retourner None.
    """
    client = get_client()
    last_err: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": config.CEREBRAS_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "reasoning_effort": reasoning_effort,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)

            # Cerebras peut renvoyer content=None (ex: tout le budget tokens consommé
            # par le reasoning interne avant l'output). On normalise en "".
            raw = resp.choices[0].message.content or ""

            if json_mode:
                return _extract_json(raw)

            # Mode texte : si vide, on lève une erreur claire plutôt que retourner ""
            if not raw.strip():
                finish_reason = getattr(resp.choices[0], "finish_reason", "?")
                raise RuntimeError(
                    f"Le modèle a renvoyé une réponse vide (finish_reason={finish_reason}). "
                    "Probable cause : le reasoning interne a consommé tout le budget tokens. "
                    "Essaie d'augmenter max_tokens, ou de baisser reasoning_effort."
                )
            return raw.strip()

        except Exception as e:
            err_str = str(e)
            last_err = e

            if "rate_limit" in err_str.lower() or "429" in err_str:
                # Quota journalier épuisé → on remonte une erreur explicite
                if "tokens per day" in err_str or "TPD" in err_str:
                    wait = _parse_retry_after(err_str)
                    raise RuntimeError(
                        f"Quota Cerebras journalier épuisé. Réessaie dans {wait/60:.1f} min. "
                        "L'état est sauvegardé, relance pour reprendre."
                    )
                wait = _parse_retry_after(err_str) + 0.5
                time.sleep(wait)
                continue
            raise

    if last_err:
        raise last_err
    raise RuntimeError("call_llm : échec inattendu")
