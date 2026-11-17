#!/usr/bin/env python3
"""
Descarga una rejilla de elevaciones para el área de data/roads.json y la guarda
en data/terrain.json. Ejecutar después de fetch_osm.py.

Fuente actual: Open-Meteo Elevation API (Copernicus DEM GLO-90, resolución ~90 m).
Los datos de Copernicus son de uso libre con atribución; comprueba sus condiciones.

TODO (fidelidad): sustituir por el MDT05 del IGN (5 m) descargado de CNIG o servido por
WCS, y reducir STEP_M a 25-50 m. Con 250 m la carretera no sigue bien los desniveles
locales, y el cauce del Turia no se distingue del terreno.
"""
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import ORIGIN_LAT, ORIGIN_LON, M_PER_DEG_LAT, M_PER_DEG_LON  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://api.open-meteo.com/v1/elevation"
STEP_M = 250.0   # TODO: bajar a 25-50 m con el MDT05 del IGN
BATCH = 100      # coordenadas por petición (límite de la API)


def to_latlon(x, z):
    return ORIGIN_LAT - z / M_PER_DEG_LAT, ORIGIN_LON + x / M_PER_DEG_LON


def fetch_batch(points):
    lats = ",".join(f"{la:.6f}" for la, _ in points)
    lons = ",".join(f"{lo:.6f}" for _, lo in points)
    url = f"{API_URL}?latitude={lats}&longitude={lons}"
    req = urllib.request.Request(url, headers={"User-Agent": "simulador-valencia/0.3"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)["elevation"]
        except Exception as exc:  # red o límite de peticiones
            wait = 5 * (attempt + 1)
            print(f"  error ({exc}); reintento en {wait} s")
            time.sleep(wait)
    raise SystemExit("No se pudo consultar la API de elevación.")


def main():
    roads = json.loads((ROOT / "data" / "roads.json").read_text(encoding="utf-8"))
    xmin, zmin, xmax, zmax = roads["bounds"]
    nx = math.ceil((xmax - xmin) / STEP_M) + 1
    nz = math.ceil((zmax - zmin) / STEP_M) + 1

    points = [to_latlon(xmin + i * STEP_M, zmin + j * STEP_M)
              for j in range(nz) for i in range(nx)]
    print(f"Rejilla {nx} x {nz} = {len(points)} puntos ({STEP_M:.0f} m)")

    heights = []
    for k in range(0, len(points), BATCH):
        heights += [h if h is not None else 0.0 for h in fetch_batch(points[k:k + BATCH])]
        print(f"  {min(k + BATCH, len(points))}/{len(points)}")
        time.sleep(0.5)

    out = ROOT / "data" / "terrain.json"
    out.write_text(json.dumps({
        "bounds": roads["bounds"],
        "step": STEP_M,
        "nx": nx,
        "nz": nz,
        "heights": [round(h, 2) for h in heights],
        "source": "Open-Meteo / Copernicus DEM GLO-90",
    }), encoding="utf-8")
    print(f"Guardado en {out}")


if __name__ == "__main__":
    main()
