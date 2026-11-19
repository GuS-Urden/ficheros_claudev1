#!/usr/bin/env python3
"""
Descarga la ortofoto PNOA del IGN en UTM 30N (EPSG:25830) para el área de
data/roads.json y la guarda como data/ortho.jpg, para el minimapa.
Ejecutar después de fetch_osm.py (necesita utm_bbox).

Licencia PNOA: CC BY 4.0, © IGN / CNIG. Cita la fuente si publicas algo derivado.

Nota: la URL del servicio WMS puede cambiar. Si falla, comprueba el endpoint vigente
del PNOA máximo en ign.es y ajusta WMS_URL y LAYER. Comprueba también que el servicio
acepta EPSG:25830 (si no, habría que pedir EPSG:4258 y reproyectar).
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

WMS_URL = "https://www.ign.es/wms-inspire/pnoa-ma"
LAYER = "OI.OrthoimageCoverage"
CRS = "EPSG:25830"
WIDTH_PX = 4096
# TODO (resolución): 4096 px sobre ~34 km son unos 8 m/píxel. Para zonas concretas
# conviene pedir teselas por subáreas (más píxeles por metro) o usar el PNOA en
# resolución completa desde CNIG. No implementado todavía.

ROOT = Path(__file__).resolve().parent.parent


def main():
    data = json.loads((ROOT / "data" / "roads.json").read_text(encoding="utf-8"))
    if "utm_bbox" not in data:
        raise SystemExit("roads.json es de una versión anterior: ejecuta primero fetch_osm.py")
    e_min, n_min, e_max, n_max = data["utm_bbox"]

    height_px = round(WIDTH_PX * (n_max - n_min) / (e_max - e_min))
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": LAYER,
        "STYLES": "",
        "CRS": CRS,
        # En EPSG:25830 el orden es este (E), norte (N)
        "BBOX": f"{e_min},{n_min},{e_max},{n_max}",
        "WIDTH": WIDTH_PX,
        "HEIGHT": height_px,
        "FORMAT": "image/jpeg",
    }
    url = WMS_URL + "?" + urllib.parse.urlencode(params)
    print(f"Descargando ortofoto {WIDTH_PX}x{height_px} en {CRS}…")
    req = urllib.request.Request(url, headers={"User-Agent": "simulador-valencia/0.5"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()
    if "image" not in content_type:
        raise SystemExit(f"El servicio no devolvió una imagen ({content_type}). Revisa WMS_URL y CRS.")

    out = ROOT / "data" / "ortho.jpg"
    out.write_bytes(body)
    print(f"Guardado en {out}")


if __name__ == "__main__":
    main()
