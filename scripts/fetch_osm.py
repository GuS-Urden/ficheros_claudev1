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
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utm30n import latlon_to_utm30n  # noqa: E402

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

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
  way["ref"~"V-(30|31|15)"]({BBOX});
  way["barrier"~"^({BARRIER_TYPES})$"]({BBOX});
  way["waterway"~"^(river|canal)$"]({BBOX});
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
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL, data=body, headers={"User-Agent": "simulador-valencia/0.5"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


def parse_lanes(tags):
    lanes = tags.get("lanes", "")
    if lanes.isdigit():
        return int(lanes)
    return 1 if tags.get("oneway") in ("yes", "true", "1") else 2


def convert(raw):
    roads, barriers, water = [], [], []
    for el in raw.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        tags = el.get("tags", {})
        points = [to_local(g["lat"], g["lon"]) for g in el["geometry"]]
        if len(points) < 2:
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
    return roads, barriers, water


def main():
    print("Consultando Overpass API…")
    raw = fetch_overpass()
    roads, barriers, water = convert(raw)

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
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"{len(roads)} tramos, {len(barriers)} barreras, {len(water)} cursos de agua -> {out}")


if __name__ == "__main__":
    main()
