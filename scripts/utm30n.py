"""
Conversión WGS84 lat/lon -> UTM zona 30N (EPSG:25830), fórmulas de Krüger.
Solo usa la biblioteca estándar de Python.
"""
import math


def latlon_to_utm30n(lat, lon):
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
