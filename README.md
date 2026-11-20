# Simulador V-30 / V-31 / V-15 (prototipo)

Prototipo web de conducción sobre la red real de OpenStreetMap, con el terreno del MDT05 del IGN, la ortofoto PNOA como fondo del minimapa y Three.js para el visor 3D. Solo necesita Python 3 (biblioteca estándar) y un navegador moderno.

## Estructura

```
simulador-valencia/
├── scripts/
│   ├── fetch_osm.py      # red viaria, barreras y ríos de OSM, en UTM 30N -> data/roads.json
│   ├── fetch_mdt.py      # MDT05 del IGN por teselas (25 m base y 5 m en el corredor) -> data/mdt/
│   ├── fetch_ortho.py    # ortofoto PNOA en UTM 30N -> data/ortho.jpg
│   ├── check_mdt.py      # diagnóstico offline de alturas del MDT en el Turia y las calzadas
│   ├── utm30n.py         # conversión lat/lon -> UTM 30N (biblioteca estándar)
│   └── fetch_dem.py      # obsoleto (Open-Meteo); ya no se usa, puede borrarse
├── data/
│   ├── roads.json        # generado por fetch_osm.py
│   ├── mdt/              # teselas .f32 + index.json, generados por fetch_mdt.py
│   ├── ortho.jpg         # generado por fetch_ortho.py (opcional)
│   └── sample.json       # tramo sintético de prueba, incluido
└── web/index.html        # visor Three.js
```

## Orden de ejecución

Desde la raíz del proyecto, en este orden:

```powershell
python scripts\fetch_osm.py      # 1. red viaria, barreras y ríos
python scripts\fetch_mdt.py      # 2. terreno (tarda; se puede reanudar)
python scripts\fetch_ortho.py    # 3. ortofoto para el minimapa (opcional)
python scripts\check_mdt.py      # 4. diagnóstico de alturas (opcional)
```

Cada script puede volver a ejecutarse: `fetch_mdt.py` salta las teselas ya descargadas, y `fetch_osm.py` regenera `roads.json` completo.

**Si cambias la configuración de niveles del MDT** (tamaño de tesela o paso), `fetch_mdt.py` se negará a continuar para no mezclar teselas de distinto tamaño. En ese caso borra la carpeta de teselas y vuelve a descargar:

```powershell
Remove-Item -Recurse -Force data\mdt
python scripts\fetch_mdt.py
```

Si `fetch_osm.py` falla con `502 Bad Gateway`, es un fallo temporal de Overpass: el script prueba dos servidores y reintenta, pero a veces hay que volver a ejecutarlo en unos minutos.

## Cómo ejecutar el visor

El navegador no permite cargar JSON ni binarios con `fetch` desde `file://`, así que hay que servir la carpeta:

```powershell
python -m http.server 8000
```

Después abre `http://localhost:8000/web/index.html`.

**Parámetros de URL:**

| Parámetro | Efecto |
|---|---|
| `?vmax=230` | Velocidad máxima en km/h (por defecto 230). |
| `?minimap=left` | Minimapa a la izquierda (por defecto, a la derecha). |
| `?data=sample` | Tramo sintético de prueba, sin terreno. |
| `?mdt=0` | Suelo plano, sin cargar el MDT. Útil para pruebas rápidas. |
| `?fog=0` | Desactiva la niebla. Útil para diagnóstico. |

Ejemplo: `http://localhost:8000/web/index.html?mdt=0&vmax=130`

**Controles:** W/↑ acelerar, S/↓ frenar o marcha atrás, A/← y D/→ dirección. En el minimapa, M lo muestra u oculta, N alterna entre norte arriba y rumbo arriba, y +/− cambian el zoom.

## Qué hace

- **Marco de coordenadas:** todo está en UTM 30N (EPSG:25830), relativo a un origen en el centro del área. El terreno, las calzadas y la ortofoto comparten sistema sin transformaciones aproximadas. El norte del minimapa es el norte de cuadrícula, que en esta zona se desvía unos 1,7° del norte geográfico.
- **Calzadas:** trazado de OSM suavizado con Catmull-Rom (curvas que pasan por los puntos originales), con anchura según el número de carriles.
- **Marcas viales:** reglas aproximadas. Bordes continuos, separaciones de carril discontinuas y línea central continua en doble sentido. OSM no tiene estas marcas fiables.
- **Terreno:** MDT05 del IGN. Paso de 25 m en la base y de 5 m en una franja de 50 m alrededor de calzadas y ríos. Las mallas se cargan solo en un radio de 3 km alrededor del coche.
- **Puentes:** los tramos con `bridge=*` suben desde el nivel de las orillas hasta un tablero situado 6 m por encima por cada nivel de `layer`. La rampa de acceso tiene la longitud necesaria para una pendiente máxima del 4 %.
- **Ríos:** cursos de agua de OSM sobre el terreno, en azul. No hay cauce tallado en el terreno todavía.
- **Coche:** física básica con velocidad máxima configurable. Sigue la altura de la calzada cercana, incluidos los puentes. No hay colisiones todavía.

## Limitaciones conocidas

- **Barreras:** siguen el terreno, no el tablero de los puentes.
- **Marcas viales:** aproximadas. Las zonas concretas hay que corregirlas a mano.
- **Cauce del Turia:** el MDT05 no siempre refleja el cauce con detalle. Si hace falta un cauce tallado, requiere otra fuente de datos.
- **Cruces a distinto nivel:** el coche elige la altura de la calzada más próxima a su altura actual. Puede fallar justo debajo de otra calzada.
- **Túneles:** no están modelados.
- **Señales de tráfico:** no incluidas todavía.
- **Colisiones:** el coche atraviesa barreras y no permanece en su carril.

## Próximas fases (pendientes de confirmación)

1. Colisiones con barreras y permanencia en carril.
2. Corrección de los accesos a puentes cuando la rampa está en otra vía de OSM (requiere tratar la red como grafo).
3. Señales de tráfico a partir de Mapillary (CC-BY-SA).
4. Base a 50 m si el rendimiento lo necesita.

## Licencias de datos

- **OpenStreetMap:** © colaboradores de OpenStreetMap, licencia ODbL. Hay que citar la fuente si se publica algo derivado.
- **MDT05 del IGN:** datos del Instituto Geográfico Nacional, licencia CC BY 4.0. Cita la fuente si publicas algo derivado.
- **Ortofoto PNOA:** © IGN / CNIG, licencia CC BY 4.0.
- **Three.js:** licencia MIT, cargado desde jsDelivr.
