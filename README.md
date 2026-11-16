# Simulador V-30 / V-31 / V-15 (prototipo)

Prototipo web de conducción sobre geometría de OpenStreetMap, con Three.js.
Sin dependencias de compilación: solo Python 3 para descargar datos y un navegador moderno.

## Estructura

```
simulador-valencia/
├── scripts/fetch_osm.py   # descarga OSM (Overpass) y convierte a metros locales
├── data/
│   ├── roads.json         # generado por fetch_osm.py (datos reales)
│   └── sample.json        # tramo sintético de prueba, incluido
└── web/index.html         # visor Three.js: carretera, marcas, barreras, coche
```

## Cómo ejecutarlo

1. Ver el tramo de prueba (no necesita internet para los datos, sí para Three.js):

   ```bash
   cd simulador-valencia
   python3 -m http.server 8000
   ```

   Abre `http://localhost:8000/web/index.html?data=sample`.

2. Descargar los datos reales de la V-30, V-31 y V-15:

   ```bash
   python3 scripts/fetch_osm.py
   ```

   Después abre `http://localhost:8000/web/index.html`.

El visor necesita un servidor local porque el navegador no permite cargar JSON con `fetch` desde `file://`.

**Controles:** W/↑ acelerar, S/↓ frenar o marcha atrás, A/← y D/→ dirección.

## Qué hace y qué no hace todavía

- Calzada asfaltada a partir del trazado y el número de carriles de OSM.
- Marcas viales por reglas: bordes continuos, separaciones de carril discontinuas, central continua en doble sentido.
- Barreras de hormigón donde OSM tiene `barrier=jersey`, `concrete`, `wall`, `guard_rail` o `retaining_wall`.
- Coche con física básica. **No hay colisiones**: el coche atraviesa barreras y no sigue el carril.

## Limitaciones conocidas

- **Marcas:** son una aproximación. Lo correcto es corregir los tramos concretos a mano, contrastando con fotos de Mapillary o la ortofoto del PNOA.
- **Refs combinadas:** OSM a veces agrupa varias vías en un mismo tramo (`V-30;V-31`). La consulta las incluye, pero conviene revisar que el trazado no se duplique.
- **Sentidos:** cada calzada de una autovía suele ser una vía `oneway=yes` distinta. El ancho se calcula como `lanes × 3,5 m` centrado sobre la línea de OSM, que es una simplificación.
- **Rendimiento:** cada segmento de barrera es un objeto separado. Con muchas barreras conviene fusionarlas en una sola geometría.
- **Señales:** no incluidas todavía.

## Próximos pasos sugeridos

1. Comprobar en el visor que las calzadas y las barreras de la V-30 cuadran con la realidad.
2. Añadir colisión con barreras y que el coche se quede dentro de su carril.
3. Crear un fichero `data/corrections.json` para las marcas que haya que corregir a mano, sin tocar el código.
4. Incorporar señales a partir de los datos de Mapillary.
5. Sustituir la geometría básica por texturas de la ortofoto del PNOA.

## Licencias de datos

- OpenStreetMap: © colaboradores de OpenStreetMap, licencia ODbL. Hay que citar la fuente si se publica algo derivado.
- Three.js: licencia MIT, cargado desde jsDelivr.
