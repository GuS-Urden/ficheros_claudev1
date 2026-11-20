#!/usr/bin/env python3
"""
Inspección de data/roads.json: vías por referencia (V-30, V-31, V-15), con sus
carriles, sentido, puente y nivel, y tramos que cruzan el cauce del Turia.

Uso (raíz del proyecto):
    python scripts\\inspect_roads.py
    python scripts\\inspect_roads.py V-15        # solo una referencia
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_ROWS = 15   # filas por referencia; el resto se resume
REFS = sys.argv[1:] or ["V-30", "V-31", "V-15", "CV-500"]


def length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def main():
    data = json.loads((ROOT / "data" / "roads.json").read_text(encoding="utf-8"))
    roads = data["roads"]
    print(f"Vías totales: {len(roads)}\n")

    for ref in REFS:
        # Coincidencia exacta por token: "V-30" no debe casar con "CV-300" ni con "V-301"
        hits = [r for r in roads if ref in [t.strip() for t in r.get("ref", "").split(";")]]
        print(f"=== {ref}: {len(hits)} vías ===")
        if not hits:
            print("  (ninguna; revisa si la referencia en OSM es distinta)\n")
            continue
        bridges = sum(1 for r in hits if r.get("bridge", "no") != "no")
        total_km = sum(length(r["points"]) for r in hits) / 1000
        print(f"  puentes: {bridges} | longitud total: {total_km:.1f} km")
        print(f"{'id':>12} {'lanes':>5} {'oneway':>6} {'bridge':>8} {'layer':>5} {'long_m':>8}  {'ref':<14} name")
        ordered = sorted(hits, key=lambda r: -length(r["points"]))
        for r in ordered[:MAX_ROWS]:
            print(f"{r['id']:>12} {r['lanes']:>5} {str(r['oneway']):>6} {r.get('bridge', 'no'):>8} "
                  f"{r.get('layer', '0'):>5} {length(r['points']):>8.0f}  {r.get('ref', ''):<14} {r.get('name', '')}")
        if len(ordered) > MAX_ROWS:
            print(f"  ... {len(ordered) - MAX_ROWS} vías más (las más cortas)")
        print()

    # Enlaces (ramales de entrada y salida): suelen no llevar ref, por eso no entran en la consulta
    links = [r for r in roads if r["highway"].endswith("_link")]
    print(f"Ramales (*_link) en roads.json: {len(links)}")
    print("Si los ramales de entrada a V-30/V-31 no aparecen, es porque OSM no les pone ref.")


if __name__ == "__main__":
    main()
