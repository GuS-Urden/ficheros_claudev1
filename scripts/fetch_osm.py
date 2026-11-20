#!/usr/bin/env python3
"""
Descarga de OpenStreetMap (Overpass API) para la V-30, V-31 y V-15, ríos incluidos.

Las coordenadas locales son directamente UTM 30N (EPSG:25830), relativas a un origen:
    x = E - E0          (este)
    z = -(N - N0)       (sur positivo, convención de Three.js)
Así el visor, el MDT del IGN y la ortofoto PNOA comparten sistema sin transformaciones.

Salida: data/roads.json (con utm_origin, utm_bbox, bbox, bounds, roads, barriers, water).

Uso (desde la raíz del proyecto):
    python scripts/fetch_osm.py

Datos de OpenStreetMap: © colaboradores de OpenStreetMap, licencia ODbL.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utm30n import latlon_to_utm30n  # noqa: E402

# Servidores Overpass. Si uno devuelve 502/503/504 o 429, el script prueba el siguiente.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
MAX_ROUNDS = 3   # vueltas completas a la lista de servidores

# Caja geográfica: sur, oeste, norte, este
BBOX = "39.35,-0.60,39.60,-0.20"

# Origen de coordenadas locales (centro aproximado de la zona)
ORIGIN_LAT, ORIGIN_LON = 39.47, -0.38
ORIGIN_E, ORIGIN_N = latlon_to_utm30n(ORIGIN_LAT, ORIGIN_LON)

UTM_PAD_M = 1000  # margen alrededor del área para ortofoto y terreno

BARRIER_TYPES = "jersey|concrete|wall|retaining_wall|guard_rail"

QUERY = f"""
[out:json][timeout:120];
(
  way["ref"~"V-(30|31|15)|CV-500"]({BBOX});
  way["barrier"~"^({BARRIER_TYPES})$"]({BBOX});
  way["waterway"~"^(river|canal)$"]({BBOX});
  way["natural"="water"]["water"="river"]({BBOX});
);
out geom tags;
"""


def to_local(lat, lon):
    """Lat/lon -> metros locales relativos al origen, en UTM 30N."""
    e, n = latlon_to_utm30n(lat, lon)
    return [round(e - ORIGIN_E, 2), round(-(n - ORIGIN_N), 2)]


def bbox_dict():
    south, west, north, east = (float(v) for v in BBOX.split(","))
    return {"south": south, "west": west, "north": north, "east": east}


def utm_bbox():
    """[E_min, N_min, E_max, N_max] del área, con margen, en UTM 30N."""
    b = bbox_dict()
    corners = [latlon_to_utm30n(la, lo) for la in (b["south"], b["north"]) for lo in (b["west"], b["east"])]
    es = [c[0] for c in corners]
    ns = [c[1] for c in corners]
    return [min(es) - UTM_PAD_M, min(ns) - UTM_PAD_M, max(es) + UTM_PAD_M, max(ns) + UTM_PAD_M]


def bounds_local(ub):
    """[x_min, z_min, x_max, z_max] en el marco local a partir del rectángulo UTM."""
    e_min, n_min, e_max, n_max = ub
    return [round(e_min - ORIGIN_E, 2), round(-(n_max - ORIGIN_N), 2),
            round(e_max - ORIGIN_E, 2), round(-(n_min - ORIGIN_N), 2)]


def fetch_overpass():
    """Consulta Overpass probando varios servidores y reintentando con espera creciente."""
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last_error = None
    for round_no in range(1, MAX_ROUNDS + 1):
        for url in OVERPASS_URLS:
            req = urllib.request.Request(
                url, data=body, headers={"User-Agent": "simulador-valencia/0.5"}
            )
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code} en {url}"
                if exc.code not in (429, 502, 503, 504):
                    raise
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = f"{exc} en {url}"
            print(f"  {last_error}; pruebo el siguiente servidor")
        if round_no < MAX_ROUNDS:
            wait = 30 * round_no
            print(f"  ningún servidor respondió; espero {wait} s (vuelta {round_no + 1}/{MAX_ROUNDS})")
            time.sleep(wait)
    raise SystemExit(f"Overpass no respondió tras {MAX_ROUNDS} vueltas (último error: {last_error}). "
                     "Vuelve a ejecutar el script en unos minutos.")


def parse_lanes(tags):
    lanes = tags.get("lanes", "")
    if lanes.isdigit():
        return int(lanes)
    return 1 if tags.get("oneway") in ("yes", "true", "1") else 2


def convert(raw):
    roads, barriers, water, river_areas = [], [], [], []
    for el in raw.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        tags = el.get("tags", {})
        points = [to_local(g["lat"], g["lon"]) for g in el["geometry"]]
        if len(points) < 2:
            continue

        # Cauces como superficie (polígono cerrado): se usan para hundir el terreno
        if tags.get("natural") == "water" and tags.get("water") == "river":
            g = el["geometry"]
            if len(g) >= 4 and g[0]["lat"] == g[-1]["lat"] and g[0]["lon"] == g[-1]["lon"]:
                river_areas.append({
                    "id": el["id"],
                    "name": tags.get("name", ""),
                    "intermittent": tags.get("intermittent", "no"),
                    "points": points[:-1],
                })
            continue

        if "highway" in tags and "ref" in tags:
            roads.append({
                "id": el["id"],
                "ref": tags["ref"],
                "name": tags.get("name", ""),
                "highway": tags["highway"],
                "lanes": parse_lanes(tags),
                "oneway": tags.get("oneway") in ("yes", "true", "1"),
                "maxspeed": tags.get("maxspeed", ""),
                "layer": tags.get("layer", "0"),
                "bridge": tags.get("bridge", "no"),
                "points": points,
            })
        elif "barrier" in tags:
            barriers.append({"id": el["id"], "type": tags["barrier"], "points": points})
        elif "waterway" in tags:
            water.append({"id": el["id"], "name": tags.get("name", ""), "points": points})
    return roads, barriers, water, river_areas


def main():
    print("Consultando Overpass API…")
    raw = fetch_overpass()
    roads, barriers, water, river_areas = convert(raw)

    ub = utm_bbox()
    out = Path(__file__).resolve().parent.parent / "data" / "roads.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "frame": "utm30n",
                "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON},
                "utm_origin": [round(ORIGIN_E, 3), round(ORIGIN_N, 3)],
                "utm_bbox": [round(v, 2) for v in ub],
                "bbox": bbox_dict(),
                "bounds": bounds_local(ub),
                "roads": roads,
                "barriers": barriers,
                "water": water,
                "river_areas": river_areas,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"{len(roads)} tramos, {len(barriers)} barreras, {len(water)} cursos de agua, "
          f"{len(river_areas)} áreas de río -> {out}")


if __name__ == "__main__":
    main()
