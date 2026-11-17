#!/usr/bin/env python3
"""
Descarga una rejilla de elevaciones para el área de data/roads.json y la guarda
en data/terrain.json. Ejecutar después de fetch_osm.py.

Fuente actual: Open-Meteo Elevation API (Copernicus DEM GLO-90, resolución ~90 m).
Es un servicio gratuito con límite de peticiones. El script guarda el progreso en
data/terrain_partial.json: si se interrumpe o da error 429, vuelve a ejecutarlo y
continúa desde donde se quedó.

TODO (fidelidad): sustituir por el MDT05 del IGN (5 m) y reducir STEP_M a 25-50 m.
Con 250 m la carretera no sigue bien los desniveles locales.
"""
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import ORIGIN_LAT, ORIGIN_LON, M_PER_DEG_LAT, M_PER_DEG_LON  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
API_URL = "https://api.open-meteo.com/v1/elevation"
STEP_M = 250.0    # TODO: bajar a 25-50 m con el MDT05 del IGN
BATCH = 100       # coordenadas por petición (límite de la API)
DELAY_S = 3.0     # pausa entre peticiones correctas
MAX_RETRIES = 6


def to_latlon(x, z):
    return ORIGIN_LAT - z / M_PER_DEG_LAT, ORIGIN_LON + x / M_PER_DEG_LON


def fetch_batch(points):
    """Devuelve la lista de alturas, o None si se agotan los reintentos."""
    lats = ",".join(f"{la:.6f}" for la, _ in points)
    lons = ",".join(f"{lo:.6f}" for _, lo in points)
    url = f"{API_URL}?latitude={lats}&longitude={lons}"
    req = urllib.request.Request(url, headers={"User-Agent": "simulador-valencia/0.3"})

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)["elevation"]
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 60
                if wait > 900:
                    print(f"  límite de peticiones agotado: la API pide esperar {wait // 3600} h.")
                    return None
            else:
                wait = 10 * (attempt + 1)
            print(f"  error HTTP {exc.code}; espero {wait} s")
        except Exception as exc:
            wait = 10 * (attempt + 1)
            print(f"  error ({exc}); espero {wait} s")
        time.sleep(wait)
    return None


def load_checkpoint(grid):
    path = DATA / "terrain_partial.json"
    if path.exists():
        cp = json.loads(path.read_text(encoding="utf-8"))
        if cp.get("nx") == grid["nx"] and cp.get("nz") == grid["nz"] and cp.get("step") == STEP_M:
            return cp["heights"]
    return []


def save_checkpoint(grid, heights):
    path = DATA / "terrain_partial.json"
    path.write_text(json.dumps({**grid, "heights": heights}), encoding="utf-8")


def main():
    roads = json.loads((DATA / "roads.json").read_text(encoding="utf-8"))
    xmin, zmin, xmax, zmax = roads["bounds"]
    nx = math.ceil((xmax - xmin) / STEP_M) + 1
    nz = math.ceil((zmax - zmin) / STEP_M) + 1
    grid = {"bounds": roads["bounds"], "step": STEP_M, "nx": nx, "nz": nz}

    points = [to_latlon(xmin + i * STEP_M, zmin + j * STEP_M)
              for j in range(nz) for i in range(nx)]
    heights = load_checkpoint(grid)
    total = len(points)
    print(f"Rejilla {nx} x {nz} = {total} puntos. Ya descargados: {len(heights)}")

    while len(heights) < total:
        k = len(heights)
        chunk = fetch_batch(points[k:k + BATCH])
        if chunk is None:
            save_checkpoint(grid, heights)
            raise SystemExit(
                f"Se detiene en {len(heights)}/{total}. Progreso guardado en data/terrain_partial.json. "
                "Espera unos minutos (o hasta mañana si el límite es diario) y vuelve a ejecutar el script."
            )
        heights += [h if h is not None else 0.0 for h in chunk]
        save_checkpoint(grid, heights)
        print(f"  {len(heights)}/{total}")
        time.sleep(DELAY_S)

    out = DATA / "terrain.json"
    out.write_text(json.dumps({
        "bounds": roads["bounds"],
        "step": STEP_M,
        "nx": nx,
        "nz": nz,
        "heights": [round(h, 2) for h in heights],
        "source": "Open-Meteo / Copernicus DEM GLO-90",
    }), encoding="utf-8")
    (DATA / "terrain_partial.json").unlink(missing_ok=True)
    print(f"Guardado en {out}")


if __name__ == "__main__":
    main()