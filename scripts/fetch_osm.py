#!/usr/bin/env python3
"""
Descarga de OpenStreetMap (Overpass API) para la V-30, V-31 y V-15.

Convierte lat/lon a metros locales (x = este, z = sur) alrededor de un origen
y guarda el resultado en data/roads.json.

Uso (desde la raíz del proyecto):
    python scripts/fetch_osm.py

Datos de OpenStreetMap: © colaboradores de OpenStreetMap, licencia ODbL.
"""
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Caja geográfica: sur, oeste, norte, este. Ajústala si quieres más área.
BBOX = "39.35,-0.60,39.60,-0.20"

# Origen de coordenadas locales (centro aproximado de la zona)
ORIGIN_LAT, ORIGIN_LON = 39.47, -0.38
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(ORIGIN_LAT))

BARRIER_TYPES = "jersey|concrete|wall|retaining_wall|guard_rail"

# La regex sin anclar también recoge refs combinadas como "V-30;V-31"
QUERY = f"""
[out:json][timeout:120];
(
  way["ref"~"V-(30|31|15)"]({BBOX});
  way["barrier"~"^({BARRIER_TYPES})$"]({BBOX});
);
out geom tags;
"""


def to_local(lat, lon):
    """Lat/lon -> metros locales. Aproximación válida para áreas de unos pocos km."""
    x = (lon - ORIGIN_LON) * M_PER_DEG_LON
    z = -(lat - ORIGIN_LAT) * M_PER_DEG_LAT
    return [round(x, 2), round(z, 2)]


def fetch_overpass():
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL, data=body, headers={"User-Agent": "simulador-valencia/0.1"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


def parse_lanes(tags):
    lanes = tags.get("lanes", "")
    if lanes.isdigit():
        return int(lanes)
    return 1 if tags.get("oneway") in ("yes", "true", "1") else 2


def convert(raw):
    roads, barriers = [], []
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
                "points": points,
            })
        elif "barrier" in tags:
            barriers.append({
                "id": el["id"],
                "type": tags["barrier"],
                "points": points,
            })
    return roads, barriers


def main():
    print("Consultando Overpass API…")
    raw = fetch_overpass()
    roads, barriers = convert(raw)

    out = Path(__file__).resolve().parent.parent / "data" / "roads.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON},
                "roads": roads,
                "barriers": barriers,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"{len(roads)} tramos de carretera y {len(barriers)} barreras -> {out}")


if __name__ == "__main__":
    main()
