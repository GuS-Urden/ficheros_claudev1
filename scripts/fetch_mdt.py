#!/usr/bin/env python3
"""
Descarga el MDT05 del IGN por teselas (API de coberturas, EPSG:25830) en binario.

Dos niveles:
  base:   paso 25 m, teselas de 5 km, cubren el área de data/roads.json
  detail: paso 5 m, teselas de 250 m, solo donde hay calzadas o agua (+ 50 m de margen)

Salida:
  data/mdt/index.json            índice de teselas (con el formato de cada una)
  data/mdt/<nivel>_<x0>_<y0>.f32 Float32 little-endian, filas de norte a sur,
                                 columnas de oeste a este, coordenadas UTM 30N

Reanudable: las teselas ya guardadas se saltan. Solo biblioteca estándar.
Uso (raíz del proyecto):  python scripts/fetch_mdt.py
"""
import array
import json
from collections import deque
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import ORIGIN_E, ORIGIN_N  # noqa: E402
from utm30n import latlon_to_utm30n  # noqa: E402

API = "https://api-coverages.idee.es"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mdt"

LEVELS = {
    "base": {"collection": "EL.ElevationGridCoverage_25830_25_PB", "tile_m": 5000, "step_m": 25},
    "detail": {"collection": "EL.ElevationGridCoverage_25830_5_PB", "tile_m": 250, "step_m": 5},
}
CORRIDOR_M = 50         # margen alrededor de calzadas y agua para el nivel detail
SAMPLE_EVERY_M = 50     # muestreo de trazados para detectar las teselas que tocan
BBOX_PAD_M = 1000       # margen extra alrededor del área base
PAUSE_S = 1.0
MAX_RETRIES = 5
MAX_WAIT_S = 900        # si el servidor pide esperar más, se detiene y guarda progreso


def local_to_utm(x, z):
    """Coordenadas locales (UTM relativas al origen) -> UTM 30N. Es una traslación."""
    return x + ORIGIN_E, ORIGIN_N - z


def polyline_utm(points):
    """Puntos UTM a lo largo de un trazado, muestreados cada SAMPLE_EVERY_M metros."""
    out = []
    for (x0, z0), (x1, z1) in zip(points, points[1:]):
        n = max(1, math.ceil(math.hypot(x1 - x0, z1 - z0) / SAMPLE_EVERY_M))
        for k in range(n):
            t = k / n
            out.append(local_to_utm(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
    if points:
        out.append(local_to_utm(*points[-1]))
    return out


def bbox_utm(b):
    corners = [latlon_to_utm30n(la, lo) for la in (b["south"], b["north"]) for lo in (b["west"], b["east"])]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return min(xs) - BBOX_PAD_M, min(ys) - BBOX_PAD_M, max(xs) + BBOX_PAD_M, max(ys) + BBOX_PAD_M


def grid_tiles(bb, tile_m):
    xmin, ymin, xmax, ymax = bb
    keys = set()
    x = math.floor(xmin / tile_m) * tile_m
    while x < xmax:
        y = math.floor(ymin / tile_m) * tile_m
        while y < ymax:
            keys.add((x, y))
            y += tile_m
        x += tile_m
    return keys


def corridor_tiles(features, tile_m):
    """Teselas que tocan calzadas o agua. Un vecino se añade solo si el punto
    está a menos de CORRIDOR_M metros de su borde."""
    keys = set()
    for feat in features:
        for e, n in polyline_utm(feat["points"]):
            ix, iy = math.floor(e / tile_m), math.floor(n / tile_m)
            fx, fy = e - ix * tile_m, n - iy * tile_m
            dxs = [0] + ([-1] if fx < CORRIDOR_M else []) + ([1] if fx > tile_m - CORRIDOR_M else [])
            dys = [0] + ([-1] if fy < CORRIDOR_M else []) + ([1] if fy > tile_m - CORRIDOR_M else [])
            for dx in dxs:
                for dy in dys:
                    keys.add(((ix + dx) * tile_m, (iy + dy) * tile_m))
    return keys


def fetch_tile(collection, x0, y0, tile_m):
    """Devuelve el JSON de la teselita, o None si hay que detenerse."""
    query = f"subset=x({x0}:{x0 + tile_m}),y({y0}:{y0 + tile_m})&f=json"
    url = f"{API}/collections/{collection}/coverage?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "simulador-valencia/0.4"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                ra = exc.headers.get("Retry-After", "")
                wait = int(ra) if ra.isdigit() else 60 * (attempt + 1)
                if wait > MAX_WAIT_S:
                    print(f"  límite de peticiones: el servidor pide esperar {wait} s. Se detiene.")
                    return None
            else:
                wait = 10 * (attempt + 1)
            print(f"  HTTP {exc.code}; espero {wait} s")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            wait = 10 * (attempt + 1)
            print(f"  error ({exc}); espero {wait} s")
        time.sleep(wait)
    return None


def parse_tile(data):
    """Devuelve (nx, ny, valores) con filas de norte a sur y columnas de oeste a este."""
    cov = data["ranges"]["null"]
    if cov["axisNames"] != ["y", "x"]:
        raise ValueError(f"orden de ejes inesperado: {cov['axisNames']}")
    ny, nx = cov["shape"]
    values = cov["values"]
    if len(values) != nx * ny:
        raise ValueError(f"nº de valores {len(values)} distinto de {nx}x{ny}")

    rows = [values[j * nx:(j + 1) * nx] for j in range(ny)]
    axes = data["domain"]["axes"]
    if axes["y"]["start"] < axes["y"]["stop"]:   # y creciente: invertir a norte->sur
        rows.reverse()
    if axes["x"]["start"] > axes["x"]["stop"]:   # x decreciente: invertir a oeste->este
        rows = [r[::-1] for r in rows]
    return nx, ny, [v for r in rows for v in r]


def fill_nulls(flat, nx, ny):
    """Rellena los nulos con la media de los vecinos válidos, iterando hasta cubrirlos."""
    grid = list(flat)
    nulls = sum(v is None for v in grid)
    passes = 0
    while any(v is None for v in grid) and passes < 200:
        passes += 1
        new = list(grid)
        for j in range(ny):
            for i in range(nx):
                k = j * nx + i
                if grid[k] is not None:
                    continue
                nb = []
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < nx and 0 <= jj < ny:
                        v = grid[jj * nx + ii]
                        if v is not None:
                            nb.append(v)
                if nb:
                    new[k] = sum(nb) / len(nb)
        grid = new
    if any(v is None for v in grid):
        print("  aviso: teselita sin datos; se rellena con 0 m")
    grid = [0.0 if v is None else float(v) for v in grid]
    return grid, nulls


def load_index():
    path = OUT / "index.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"crs": "EPSG:25830", "byte_order": "little-endian float32",
            "row_order": "north_to_south", "levels": LEVELS, "tiles": []}


def save_index(index):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")


def fmt_time(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m {sec:02d}s" if h else f"{m}m {sec:02d}s"


def main():
    roads = json.loads((ROOT / "data" / "roads.json").read_text(encoding="utf-8"))
    index = load_index()
    done = {t["file"] for t in index["tiles"]}

    base = grid_tiles(bbox_utm(roads["bbox"]), LEVELS["base"]["tile_m"])
    detail = corridor_tiles(roads["roads"] + roads.get("water", []), LEVELS["detail"]["tile_m"])
    plan = [("base", k) for k in sorted(base)] + [("detail", k) for k in sorted(detail)]
    pending = [(lv, k) for lv, k in plan if f"{lv}_{k[0]}_{k[1]}.f32" not in done]
    print(f"Teselas: base {len(base)}, detalle {len(detail)}. Pendientes: {len(pending)} de {len(plan)}")
    OUT.mkdir(parents=True, exist_ok=True)

    total = len(plan)
    done_before = total - len(pending)
    durations = deque(maxlen=20)   # duración de las últimas teselas, para el tiempo estimado
    t_start = time.time()

    for n, (level, (x0, y0)) in enumerate(pending, start=1):
        cfg = LEVELS[level]
        fname = f"{level}_{x0}_{y0}.f32"
        t_tile = time.time()

        data = fetch_tile(cfg["collection"], x0, y0, cfg["tile_m"])
        if data is None:
            save_index(index)
            raise SystemExit(
                f"Progreso guardado ({done_before + n - 1}/{total}). Vuelve a ejecutar el script más tarde."
            )

        nx, ny, flat = parse_tile(data)
        grid, nulls = fill_nulls(flat, nx, ny)
        with open(OUT / fname, "wb") as f:
            array.array("f", grid).tofile(f)

        index["tiles"].append({"level": level, "x0": x0, "y0": y0, "tile_m": cfg["tile_m"],
                               "step_m": cfg["step_m"], "nx": nx, "ny": ny,
                               "file": fname, "nulls_filled": nulls})
        save_index(index)
        time.sleep(PAUSE_S)

        durations.append(time.time() - t_tile)
        done = done_before + n
        remaining = len(pending) - n
        elapsed = time.time() - t_start
        if len(durations) < 3:
            eta = "calculando…"
        else:
            eta = "~" + fmt_time(sum(durations) / len(durations) * remaining)
        print(f"[{done}/{total}] {100 * done / total:5.1f}% | {level:6s} {fname} | "
              f"nulos {nulls} | transcurrido {fmt_time(elapsed)} | restante {eta}")

    print(f"Completado: {len(index['tiles'])} teselas en {OUT}")


if __name__ == "__main__":
    main()
