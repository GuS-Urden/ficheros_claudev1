#!/usr/bin/env python3
"""
Diagnóstico offline: comprueba las alturas del MDT a lo largo del Turia (y de las
calzadas) leyendo directamente data/mdt y data/roads.json. No necesita navegador.

Uso (raíz del proyecto):
    python scripts\\check_mdt.py
"""
import array
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load_tiles():
    index = json.loads((DATA / "mdt" / "index.json").read_text(encoding="utf-8"))
    tiles = {}
    for t in index["tiles"]:
        h = array.array("f")
        with open(DATA / "mdt" / t["file"], "rb") as f:
            h.frombytes(f.read())
        tiles[(t["level"], t["x0"], t["y0"])] = (t, h)
    return index, tiles


def sample(index, tiles, e, n):
    """Altura nearest-neighbour en UTM: detalle si existe, si no base. None si no hay tesela."""
    for level in ("detail", "base"):
        tile_m = index["levels"][level]["tile_m"]
        key = (level, (int(e // tile_m)) * tile_m, (int(n // tile_m)) * tile_m)
        if key in tiles:
            t, h = tiles[key]
            i = round((e - t["x0"]) / t["step_m"])
            j = round((t["y0"] + t["tile_m"] - n) / t["step_m"])
            i = min(max(i, 0), t["nx"] - 1)
            j = min(max(j, 0), t["ny"] - 1)
            return h[j * t["nx"] + i], level
    return None, None


def stats(label, values):
    if not values:
        print(f"{label}: sin muestras")
        return
    vals = sorted(values)
    p = lambda q: vals[int(q * (len(vals) - 1))]
    print(f"{label}: {len(vals)} muestras | min {vals[0]:.2f} | p5 {p(0.05):.2f} | "
          f"mediana {p(0.5):.2f} | p95 {p(0.95):.2f} | max {vals[-1]:.2f} | rango {vals[-1] - vals[0]:.2f} m")


def main():
    roads = json.loads((DATA / "roads.json").read_text(encoding="utf-8"))
    if "utm_origin" not in roads:
        raise SystemExit("roads.json es de una versión anterior: ejecuta fetch_osm.py")
    e0, n0 = roads["utm_origin"]
    index, tiles = load_tiles()
    print(f"Teselas cargadas: {len(tiles)}")

    def to_utm(p):
        return e0 + p[0], n0 - p[1]

    # Turia (por nombre) y, si no hay, todos los cursos de agua
    water = roads.get("water", [])
    turia = [w for w in water if "turia" in w.get("name", "").lower()]
    print(f"Cursos de agua: {len(water)} | con 'Turia' en el nombre: {len(turia)}")

    for label, group in (("Turia", turia), ("Todos los cauces", water)):
        vals, levels = [], {"detail": 0, "base": 0, "sin datos": 0}
        for w in group:
            for p in w["points"]:
                h, lv = sample(index, tiles, *to_utm(p))
                if h is None:
                    levels["sin datos"] += 1
                else:
                    vals.append(h)
                    levels[lv] += 1
        stats(f"Altura MDT en {label}", vals)
        print(f"  origen de las muestras: {levels}")

    # Calzadas, para comparar: rango de alturas en las calzadas
    road_vals = []
    for r in roads["roads"][:2000]:
        for p in r["points"][::5]:
            h, _ = sample(index, tiles, *to_utm(p))
            if h is not None:
                road_vals.append(h)
    stats("Altura MDT en calzadas (muestra)", road_vals)


if __name__ == "__main__":
    main()
