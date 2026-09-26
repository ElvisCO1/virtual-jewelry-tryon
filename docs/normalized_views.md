# Preparación de las 36 vistas

Originales: `pack_image_36/` (conservados sin cambios).
Copias: `assets/rings/views_36_normalized/`.

Se conservan los nombres `ring_azXXX_el_YYY.png`: 12 giros por 3 inclinaciones.
Los ángulos siguen siendo categorías visuales aproximadas.

## Normalización aplicada

- Lienzo RGBA transparente común de **288 × 288**.
- Anclaje inicial común en **(144, 144)**.
- Traslación entera, sin interpolación, rotación, recorte ni cambio de escala.
- Conservación exacta de los valores RGBA, incluidos los píxeles semitransparentes.
- Sin limpieza de halos ni reconstrucción de partes cortadas.

Para estimar el anclaje se toma el centro del rectángulo que contiene el componente
conectado más grande con alpha >= 128. Así los pequeños residuos aislados no
determinan el centro. No se elimina ningún residuo: se traslada el lienzo original
completo. El lienzo común deja al menos 16 píxeles de margen para todas las fuentes.

**Este centro es una aproximación visual, no el centro físico del aro ni una
calibración del eje del dedo.** La piedra, reflejos y residuos conectados pueden
afectar la estimación. Debe validarse manualmente cuando exista un selector de vistas.
Tampoco se ha corregido la orientación interna de las imágenes.

Se conserva la escala en píxeles que tenían los originales, para no borrar las
diferencias de perspectiva. No se puede deducir una escala física consistente a
partir de estos recortes sin calibración adicional.

## Trazabilidad y reproducción

`manifest.json` registra el tamaño original, anclaje estimado, desplazamiento,
hashes SHA-256 y posibles contactos del objeto con los bordes de la imagen fuente.
Se verificó que las 36 fuentes conservan sus hashes y que sus píxeles aparecen
intactos en las copias.

```powershell
.\.venv\Scripts\python.exe -m virtual_jewelry_tryon.normalize_assets --output assets/rings/views_36_normalized_v2
```

El comando exige una colección completa y una carpeta de salida nueva; no
sobrescribe imágenes existentes. Por defecto lee `pack_image_36/`.

## Integración pendiente

La aplicación sigue utilizando las dos imágenes demo. Estas copias todavía no
están conectadas a un selector ni a una clasificación automática de 36 vistas.

Al integrarlas debe considerarse que el escalado actual usa el ancho del lienzo:
añadir margen transparente cambia el tamaño aparente para el mismo ancho objetivo.
Como las fuentes tenían 209 píxeles de ancho y las copias 288, para conservar la
escala de una fuente concreta el ancho objetivo equivalente se multiplica por
288/209 (aproximadamente 1.378). Esto no determina el ajuste físico del anillo.
