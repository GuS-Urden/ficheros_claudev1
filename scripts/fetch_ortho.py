#!/usr/bin/env python3
"""
Descarga la ortofoto PNOA del IGN para el área de data/roads.json y la guarda
como data/ortho.jpg, para el minimapa. Ejecutar después de fetch_osm.py.

Licencia PNOA: CC BY 4.0, © IGN / CNIG. Cita la fuente si publicas algo derivado.

Nota: la URL del servicio WMS puede cambiar. Si falla, comprueba el endpoint
vigente del PNOA máximo en ign.es y ajusta WMS_URL y LAYER.
"""
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

WMS_URL = "https://www.ign.es/wms-inspire/pnoa-ma"
LAYER = "OI.OrthoimageCoverage"
WIDTH_PX = 4096
# TODO (resolución): 4096 px sobre ~34 km son unos 8 m/píxel. Para zonas concretas
# conviene pedir teselas por subáreas (más píxeles por metro) o usar el PNOA en
# resolución completa desde CNIG. No implementado todavía.

ROOT = Path(__file__).resolve().parent.parent


def main():
    roads_path = ROOT / "data" / "roads.json"
    data = json.loads(roads_path.read_text(encoding="utf-8"))
    b = data["bbox"]

    # Proporción de la imagen a partir de las distancias reales en metros
    lat_mid = (b["south"] + b["north"]) / 2
    height_m = (b["north"] - b["south"]) * 111_320.0
    width_m = (b["east"] - b["west"]) * 111_320.0 * math.cos(math.radians(lat_mid))
    height_px = round(WIDTH_PX * height_m / width_m)

    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": LAYER,
        "STYLES": "",
        "CRS": "EPSG:4326",
        # WMS 1.3.0 con EPSG:4326 usa el orden lat,lon
        "BBOX": f"{b['south']},{b['west']},{b['north']},{b['east']}",
        "WIDTH": WIDTH_PX,
        "HEIGHT": height_px,
        "FORMAT": "image/jpeg",
    }
    url = WMS_URL + "?" + urllib.parse.urlencode(params)
    print(f"Descargando ortofoto {WIDTH_PX}x{height_px}…")
    req = urllib.request.Request(url, headers={"User-Agent": "simulador-valencia/0.2"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()
    if "image" not in content_type:
        raise SystemExit(f"El servicio no devolvió una imagen ({content_type}). Revisa WMS_URL.")

    out = ROOT / "data" / "ortho.jpg"
    out.write_bytes(body)
    print(f"Guardado en {out}")


if __name__ == "__main__":
    main()
