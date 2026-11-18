#!/usr/bin/env python3
"""
Prueba de la API de coberturas del IGN (MDT05, EPSG:25830).

Descarga una teselita de lado 2 km alrededor de Valencia, guarda la respuesta
completa en data/probe_coverage.json y muestra su estructura.
Solo usa la biblioteca estándar de Python.

Uso (desde la raíz del proyecto):
    python scripts/probe_ign_mdt.py
    python scripts/probe_ign_mdt.py --size 1000   # lado de la teselita en metros
"""
import argparse
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api-coverages.idee.es"
COLLECTION = "EL.ElevationGridCoverage_25830_5_PB"  # MDT05, UTM 30N, Península e Islas Baleares
ROOT = Path(__file__).resolve().parent.parent

# Centro de prueba: centro aproximado de la zona (lat, lon)
CENTER_LAT, CENTER_LON = 39.47, -0.38


def latlon_to_utm30n(lat, lon):
    """WGS84 lat/lon -> UTM zona 30N (EPSG:25830). Fórmulas estándar de Krüger."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996
    lon0 = math.radians(-3.0)  # meridiano central de la zona 30

    phi = math.radians(lat)
    lam = math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    A = math.cos(phi) * (lam - lon0)
    m = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * phi)
    )
    x = k0 * n * (A + (1 - t + c) * A ** 3 / 6
                  + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * A ** 5 / 120) + 500000
    y = k0 * (m + n * math.tan(phi) * (A * A / 2
                  + (5 - t + 9 * c + 4 * c * c) * A ** 4 / 24
                  + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * A ** 6 / 720))
    return x, y


def describe(obj, depth=0, max_depth=3):
    """Resumen legible de la estructura JSON, sin volcar los valores."""
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and depth < max_depth:
                print(f"{pad}{k}: {type(v).__name__} ({len(v)} elementos)")
                describe(v, depth + 1, max_depth)
            else:
                preview = repr(v)
                print(f"{pad}{k}: {preview[:80]}")
    elif isinstance(obj, list):
        print(f"{pad}[lista de {len(obj)}] primer elemento: {repr(obj[0])[:80] if obj else 'vacía'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=2000.0, help="lado de la teselita (m)")
    args = ap.parse_args()

    xc, yc = latlon_to_utm30n(CENTER_LAT, CENTER_LON)
    half = args.size / 2
    x0, x1 = round(xc - half), round(xc + half)
    y0, y1 = round(yc - half), round(yc + half)
    print(f"Centro UTM 30N: x={xc:.0f}, y={yc:.0f}")
    print(f"Teselita: x({x0}:{x1}), y({y0}:{y1})")

    query = f"subset=x({x0}:{x1}),y({y0}:{y1})&f=json"
    url = f"{API}/collections/{COLLECTION}/coverage?{query}"
    print(f"Petición: {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "simulador-valencia/0.4"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            print(f"HTTP {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
    except urllib.error.HTTPError as exc:
        body = exc.read()[:500].decode("utf-8", "replace")
        raise SystemExit(f"HTTP {exc.code}: {body}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Error de red: {exc.reason}")

    print(f"Descargados {len(raw) / 1024:.1f} KB en {time.time() - t0:.1f} s")

    out = ROOT / "data" / "probe_coverage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    print(f"Respuesta completa guardada en {out}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("La respuesta no es JSON. Primeros 300 caracteres:")
        print(raw[:300])
        return

    print("\nEstructura:")
    describe(data)


if __name__ == "__main__":
    main()