"""Script CLI — Collecte exhaustive France Travail (Phases 1 + 1bis + 1ter).

Lance :
    python -m scripts.collect_offres            # collecte initiale (~2-6h)
    python -m scripts.collect_offres --idf      # complète l'IDF avec axe ROME
    python -m scripts.collect_offres --paris    # haute résolution Paris (arrondissements)

Reprenable : checkpoint régulier dans ~/.jobflow/assets/checkpoint_offres.pkl
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from jobflow_core import config

# ─── Vérifs clés ────────────────────────────────────────────────────
if not config.has_france_travail_keys():
    sys.exit(
        "Clés France Travail manquantes. Ajoute FRANCE_TRAVAIL_CLIENT_ID et "
        "FRANCE_TRAVAIL_CLIENT_SECRET dans .env (créer un compte développeur sur "
        "https://francetravail.io)."
    )

CLIENT_ID     = config.FRANCE_TRAVAIL_CLIENT_ID
CLIENT_SECRET = config.FRANCE_TRAVAIL_CLIENT_SECRET

# ─── Endpoints ──────────────────────────────────────────────────────
TOKEN_URL  = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
ROME_URL   = "https://api.francetravail.io/partenaire/rome-metiers/v1/metiers/metier"

SCOPE_FULL = "api_offresdemploiv2 o2dsoffre api_rome-metiersv1 nomenclatureRome"
SCOPE_MIN  = "api_offresdemploiv2 o2dsoffre"

BATCH      = 150
MAX_RANGE  = 3000
SLEEP      = 0.12
CHECKPOINT_EVERY = 200

# Chemins (dans le dossier assets pour qu'ils soient à côté de la DB)
CHECKPOINT_FILE = config.ASSETS_DIR / "checkpoint_offres.pkl"
PROGRESS_FILE   = config.ASSETS_DIR / "progress_combos.pkl"
PROGRESS_IDF    = config.ASSETS_DIR / "progress_combos_IDF.pkl"
PROGRESS_PARIS  = config.ASSETS_DIR / "progress_combos_PARIS.pkl"

DEPTS = (
    [f"{i:02d}" for i in range(1, 20)] + ["2A", "2B"]
    + [f"{i:02d}" for i in range(21, 96)]
    + ["971", "972", "973", "974", "976"]
)
GRAND_DOMAINES = list("ABCDEFGHIJKLMN")
TYPES_CONTRAT = ["CDI", "CDD", "MIS", "SAI", "LIB", "FRA", "CCE", "DDI", "DIN"]
IDF_DEPTS = ["75", "77", "78", "91", "92", "93", "94", "95"]
PARIS_COMMUNES = [f"751{i:02d}" for i in range(1, 21)]


# ─── Token manager ──────────────────────────────────────────────────
class TokenManager:
    def __init__(self):
        self.token = None
        self.expires_at = 0
        self.scope = SCOPE_FULL
        self.has_rome_access = True

    def _request(self, scope):
        return requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials",
                  "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                  "scope": scope},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )

    def get(self):
        if time.time() < self.expires_at - 60:
            return self.token
        r = self._request(self.scope)
        if r.status_code != 200 and self.scope == SCOPE_FULL:
            print("⚠️ Scope ROME refusé, fallback sur scope minimal.")
            self.scope = SCOPE_MIN
            self.has_rome_access = False
            r = self._request(self.scope)
        r.raise_for_status()
        data = r.json()
        self.token = data["access_token"]
        self.expires_at = time.time() + data.get("expires_in", 1499)
        return self.token


def fetch_search(tm: TokenManager, params: dict) -> list:
    """Récupère toutes les offres pour des params donnés (paginé)."""
    offres = []
    errors = 0
    for start in range(0, MAX_RANGE, BATCH):
        headers = {"Authorization": f"Bearer {tm.get()}", "Accept": "application/json"}
        full = {**params, "range": f"{start}-{start + BATCH - 1}"}
        try:
            r = requests.get(SEARCH_URL, headers=headers, params=full, timeout=25)
            if r.status_code in (200, 206):
                res = r.json().get("resultats", [])
                offres.extend(res)
                if len(res) < BATCH:
                    break
            elif r.status_code == 204:
                break
            elif r.status_code == 429:
                time.sleep(2); continue
            else:
                errors += 1
                if errors > 3: break
        except requests.RequestException:
            errors += 1; time.sleep(1)
            if errors > 3: break
        time.sleep(SLEEP)
    return offres


def fetch_combo_with_subsplit(tm: TokenManager, split_value: str, dept: str, split_param: str) -> list:
    """Combo avec sub-split par type de contrat si saturé."""
    base = {split_param: split_value, "departement": dept}
    offres = fetch_search(tm, base)
    if len(offres) >= MAX_RANGE - BATCH:
        d = {o["id"]: o for o in offres if o.get("id")}
        for tc in TYPES_CONTRAT:
            for o in fetch_search(tm, {**base, "typeContrat": tc}):
                if o.get("id"):
                    d[o["id"]] = o
        offres = list(d.values())
    return offres


def load_offres() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "rb") as f:
            return pickle.load(f)
    return {}


def save_offres(offres: dict):
    with open(CHECKPOINT_FILE, "wb") as f:
        pickle.dump(offres, f)


# ─── Mode principal : collecte initiale ─────────────────────────────
def main_initial(tm: TokenManager):
    if tm.has_rome_access:
        try:
            r = requests.get(ROME_URL,
                             headers={"Authorization": f"Bearer {tm.get()}", "Accept": "application/json"},
                             timeout=30)
            r.raise_for_status()
            ROME_CODES = [m["code"] for m in r.json() if "code" in m]
            SPLIT_PARAM, SPLIT_VALUES = "codeROME", ROME_CODES
            print(f"✅ {len(ROME_CODES)} codes ROME récupérés")
        except Exception as e:
            print(f"⚠️ ROME fail ({e}) → fallback grand domaine")
            SPLIT_PARAM, SPLIT_VALUES = "grandDomaine", GRAND_DOMAINES
    else:
        SPLIT_PARAM, SPLIT_VALUES = "grandDomaine", GRAND_DOMAINES

    all_combos = [(sv, d) for sv in SPLIT_VALUES for d in DEPTS]
    done = set()
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "rb") as f:
            done = pickle.load(f)
    remaining = [c for c in all_combos if c not in done]
    all_offres = load_offres()
    print(f"🎯 {len(all_combos):,} combos · ✅ {len(done):,} faits · ⏳ {len(remaining):,} restants")
    print(f"💼 Offres déjà collectées : {len(all_offres):,}")

    for i, (sv, dept) in enumerate(tqdm(remaining, desc="Collecte", unit="combo")):
        try:
            offres = fetch_combo_with_subsplit(tm, sv, dept, SPLIT_PARAM)
            for o in offres:
                if o.get("id"):
                    all_offres[o["id"]] = o
            done.add((sv, dept))
        except Exception as e:
            tqdm.write(f"⚠️ {sv}/{dept} : {e}")
        if (i + 1) % CHECKPOINT_EVERY == 0:
            save_offres(all_offres)
            with open(PROGRESS_FILE, "wb") as f:
                pickle.dump(done, f)
            tqdm.write(f"💾 checkpoint @ {i+1}/{len(remaining)} · {len(all_offres):,} offres")
    save_offres(all_offres)
    with open(PROGRESS_FILE, "wb") as f:
        pickle.dump(done, f)
    print(f"🎉 Collecte initiale terminée — {len(all_offres):,} offres uniques")


# ─── Complétion IDF (axe ROME) ─────────────────────────────────────
def main_idf(tm: TokenManager):
    all_offres = load_offres()
    if not all_offres:
        sys.exit("checkpoint_offres.pkl introuvable — lance la collecte initiale d'abord")
    rome_codes = sorted({o.get("romeCode") for o in all_offres.values() if o.get("romeCode")})
    print(f"🎯 {len(rome_codes)} codes ROME × {len(IDF_DEPTS)} dépts IDF")

    done = set()
    if PROGRESS_IDF.exists():
        with open(PROGRESS_IDF, "rb") as f:
            done = pickle.load(f)
    combos = [(r, d) for r in rome_codes for d in IDF_DEPTS if (r, d) not in done]
    print(f"⏳ {len(combos):,} combos restants")

    new = 0
    for i, (rome, dept) in enumerate(tqdm(combos, desc="IDF", unit="combo")):
        try:
            offres = fetch_combo_with_subsplit(tm, rome, dept, "codeROME")
            for o in offres:
                if o.get("id"):
                    if o["id"] not in all_offres:
                        new += 1
                    all_offres[o["id"]] = o
            done.add((rome, dept))
        except Exception as e:
            tqdm.write(f"⚠️ {rome}/{dept} : {e}")
        if (i + 1) % 100 == 0:
            save_offres(all_offres)
            with open(PROGRESS_IDF, "wb") as f:
                pickle.dump(done, f)
            tqdm.write(f"💾 +{new:,} nouvelles · total {len(all_offres):,}")
    save_offres(all_offres)
    with open(PROGRESS_IDF, "wb") as f:
        pickle.dump(done, f)
    print(f"🎉 IDF terminée — +{new:,} nouvelles offres")


# ─── Haute résolution Paris (arrondissements) ──────────────────────
def main_paris(tm: TokenManager):
    all_offres = load_offres()
    if not all_offres:
        sys.exit("checkpoint_offres.pkl introuvable")
    done = set()
    if PROGRESS_PARIS.exists():
        with open(PROGRESS_PARIS, "rb") as f:
            done = pickle.load(f)
    combos = [(c, tc) for c in PARIS_COMMUNES for tc in TYPES_CONTRAT if (c, tc) not in done]
    print(f"⏳ {len(combos)} combos arrondissement × contrat")

    new = 0
    for i, (commune, tc) in enumerate(tqdm(combos, desc="Paris", unit="combo")):
        try:
            offres = fetch_search(tm, {"commune": commune, "typeContrat": tc})
            for o in offres:
                if o.get("id"):
                    if o["id"] not in all_offres:
                        new += 1
                    all_offres[o["id"]] = o
            done.add((commune, tc))
        except Exception as e:
            tqdm.write(f"⚠️ {commune}/{tc} : {e}")
        if (i + 1) % 30 == 0:
            save_offres(all_offres)
            with open(PROGRESS_PARIS, "wb") as f:
                pickle.dump(done, f)
    save_offres(all_offres)
    with open(PROGRESS_PARIS, "wb") as f:
        pickle.dump(done, f)
    print(f"🎉 Paris terminée — +{new:,} nouvelles offres · total {len(all_offres):,}")


# ─── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Collecte France Travail")
    ap.add_argument("--idf",   action="store_true", help="Complétion IDF (axe ROME)")
    ap.add_argument("--paris", action="store_true", help="Haute résolution Paris (arrondissements)")
    args = ap.parse_args()

    tm = TokenManager()
    tm.get()
    print(f"✅ Token OK (scope = {tm.scope})")

    if args.paris:
        main_paris(tm)
    elif args.idf:
        main_idf(tm)
    else:
        main_initial(tm)
