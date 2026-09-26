# virtual-jewelry-tryon

Proyecto incremental de visión por computadora: webcam, landmarks de manos,
geometría del dedo anular y superposición de un anillo con rotación, suavizado y
selección de vista según la orientación de la mano. Usa Python, OpenCV y MediaPipe.

## Ejecutar

Desde la raíz del proyecto, usando el entorno virtual existente:

```powershell
.\.venv\Scripts\python.exe main.py
```

En VS Code, selecciona **Webcam - entorno .venv** y presiona **F5**.
La configuración ejecuta `main.py` con el Python del proyecto.

### Interfaz: cámara y visibilidad de referencias

La ventana abre con la cámara **desactivada**. Usa los botones:

- **Activar cámara**: inicia la captura y el procesamiento dentro de la ventana.
- **Desactivar cámara**: libera la webcam y el detector, y borra el último fotograma.
  Puedes volver a activarla sin cerrar el programa.
- **Salir**: libera los recursos y cierra la aplicación. La X de la ventana hace lo mismo.

El botón **Ocultar referencias / Mostrar referencias** alterna los puntos, líneas,
números de landmarks, identificadores sobre la mano y cruz del punto medio.
**Los datos y coordenadas del panel lateral permanecen visibles y se actualizan.**
La detección, orientación y superposición del anillo continúan funcionando igual.
Puedes usarlo con la cámara encendida o apagada; la elección se conserva al volver
a activar la cámara durante la sesión. Al abrir de nuevo el programa, las referencias
están visibles por defecto.

Para probarlo: activa la cámara, muestra una mano y pulsa **Ocultar referencias**.
Verifica que solo desaparecen las marcas sobre la mano, que el anillo sigue el dedo
y que cambian los valores del panel al moverlo. Pulsa **Mostrar referencias** para
recuperarlas. Prueba también desactivar y reactivar la cámara con las marcas ocultas.

La interfaz usa Tkinter (incluido en la instalación habitual de Python para Windows)
y Pillow para mostrar los fotogramas. Si actualizas un entorno existente, ejecuta
` .\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

- **d**: imprimir landmarks y orientación en la terminal.
- `--geometry-only`: ver la geometría y orientación sin imágenes.
- `--help`: consultar las opciones, sin abrir la cámara.
- `--opencv-preview`: abrir el visor anterior de OpenCV; en ese modo **q** sale.

```powershell
.\.venv\Scripts\python.exe main.py --geometry-only
.\.venv\Scripts\python.exe main.py --smoothing 0
.\.venv\Scripts\python.exe main.py --ring "C:\ruta\anillo.png"
.\.venv\Scripts\python.exe main.py --ring-front "C:\ruta\front.png" --ring-back "C:\ruta\back.png"
```

Los recursos predeterminados se resuelven desde la ubicación del proyecto, no desde
el directorio de la terminal. Las rutas personalizadas relativas se interpretan
desde el directorio donde ejecutas el comando.

### Prueba manual de las 36 vistas — parte 1

El modo inicial sigue siendo **Automático front/back**. Para probar el catálogo:

1. Activa la cámara y elige **Manual — 36 vistas** en el selector de modo.
2. Usa **Anterior / Siguiente** para cambiar el PNG sobre la mano.
3. Consulta el contador, el nombre del archivo, el giro y la inclinación junto
   a los controles. El panel también indica el archivo aplicado.
4. Oculta las referencias si quieres observar el anillo sin marcas.
5. Vuelve a **Automático front/back** para recuperar la selección palma/dorso.

El orden es giro 0° a 330° cada 30°, primero con inclinación 0°, después −30° y
finalmente +30°. Los botones recorren circularmente las 36 vistas. Los ángulos
son categorías del PNG, no una medición nueva de la mano.

La misma vista manual se aplica a ambas manos detectadas. Sigue ajustándose a
la posición, tamaño y rotación del dedo, con el suavizado existente. Seleccionar
una imagen no reinicia la cámara ni el detector. La elección se conserva al
desactivar/reactivar la cámara durante la sesión, y el catálogo se carga una sola
vez al entrar al modo manual. Si falta un archivo, se muestra el error y se
conserva el modo anterior de funcionamiento sin interrumpir la cámara.

Con `--ring` o `--geometry-only`, el primer modo se llama **Imagen única** o
**Sin anillo**, respectivamente. Al volver a ese modo se recupera esa configuración.

El selector no elige automáticamente entre las 36 vistas. La carga usa el manifiesto ya existente de
normalización para compensar el margen transparente (288/209); no calibra el
tamaño físico ni corrige halos o alineaciones imperfectas.

### Captura manual en memoria — parte 2

1. Ejecuta `.\.venv\Scripts\python.exe main.py`, activa la cámara y selecciona
   **Manual — 36 vistas**.
2. Recorre las imágenes con **Anterior/Siguiente**. Puedes ocultar las referencias.
3. Elige **Mano a validar** si aparecen dos manos; con una se selecciona sola.
4. Cuando el PNG corresponda visualmente a la postura, pulsa **Capturar (adecuada)**.
5. Revisa el contador y el nombre confirmado. **Descartar última** marca como
   descartada la última muestra válida, manteniendo el registro en memoria.

Cada clic copia los datos del último fotograma presentado: PNG y categorías de
ángulo, mano izquierda/derecha, confianza, 21 coordenadas normalizadas, coordenadas
world si están disponibles, geometría del dedo, pose original y suavizada,
dimensiones del fotograma y configuración. Las coordenadas x/y normalizadas se
refieren al ancho/alto de la imagen; z es profundidad relativa, no distancia de
la cámara en metros. Las coordenadas world son estimaciones en metros relativas
a la mano. La geometría usa píxeles y ángulos en grados. La hora del fotograma
corresponde al inicio de su procesamiento, no a un reloj de hardware de la cámara.

Se rechazan capturas sin una mano identificable, con confianza izquierda/derecha
inferior a 0.6, geometría inválida o etiquetas de mano duplicadas. Al cambiar de
PNG se espera un nuevo fotograma antes de habilitar la captura. Un mismo
fotograma/mano no admite dos muestras válidas. La confianza no mide la calidad
visual del ajuste: **adecuada** es tu valoración manual, y los ángulos del PNG
siguen siendo categorías aproximadas, no mediciones 3D calibradas.

Las muestras sobreviven a desactivar/reactivar la cámara. La parte 3 descrita
abajo añade su guardado en JSON; no se almacenan fotos.
`samples.py` gestiona las muestras; `app.py` prepara sus datos y `gui.py`
conecta los controles. La elección automática front/back continúa disponible.

### Distribución de los controles

**Ancho del dedo: desactivado temporalmente.** Tras las pruebas con webcam, la
estimación no resultó suficientemente fiable. Los controles de calibración, la
línea cian y las lecturas de ancho/mm están ocultos; el cálculo no se ejecuta en
el vídeo. Se conserva el código y sus pruebas bajo `FINGER_WIDTH_ENABLED = False`
en `features.py` para retomarlo después. El deslizador de tamaño del anillo sigue
funcionando. Las nuevas muestras indican `width_measurement_enabled: false` y
`finger_width: null`; los JSON existentes no se modifican.

La siguiente descripción documenta el experimento conservado, actualmente inactivo.
**Ancho del dedo (experimental):** se buscan bordes en cinco líneas perpendiculares
al dedo, en la posición actual del anillo y sobre el vídeo original, antes de
dibujar referencias o joyas. La mediana de bordes consistentes proporciona el
ancho en píxeles. Con referencias visibles aparece una línea cian y sus extremos;
el panel muestra el ancho aunque ocultes las referencias. Si no hay bordes
consistentes muestra «Ancho: no fiable», sin reutilizar medidas antiguas.

Para probarlo, separa los dedos, usa un fondo uniforme con contraste y oculta el
anillo. Comprueba que los extremos cian estén sobre los bordes del dedo. Sombras,
texturas y dedos juntos pueden producir errores incluso si aparece un valor.
Esta medición todavía **no controla el tamaño del anillo**.

**Milímetros:** por defecto se muestra `mm: sin calibrar`. Mide el ancho real del
dedo en ese punto, introduce el valor en **Ancho real del dedo (mm)** y pulsa
**Calibrar mm**, mostrando una sola mano con una medición válida. Se calcula
`mm_por_pixel = ancho_real_mm / ancho_referencia_px`, y después
`ancho_mm = ancho_actual_px * mm_por_pixel`. El resultado se etiqueta aproximado:
no es una medición física independiente ni una talla de anillo. Mantén la misma
distancia a cámara y postura; recalibra si cambian, ya que no se detecta ese cambio
automáticamente. **Quitar calibración** vuelve a píxeles solamente.

La calibración se borra al parar la cámara o cambiar dedo/posición y solo se
aplica a la misma mano, dedo, posición y resolución, con una mano detectada.
Las muestras JSON añaden `hand.finger_width` (píxeles, extremos, método y mm o
`null`) y `settings.width_calibration`, sin modificar los JSON existentes.
La lógica está separada en `finger_width.py`; no añade dependencias.

**Tamaño del anillo**, debajo de oclusión en **Prueba y captura**, ajusta el tamaño
entre 50 % y 200 %. **Restablecer 100 %** recupera la escala automática original.
El factor multiplica el ancho calculado tras el suavizado y conserva proporciones,
centro y ángulo. Continúa adaptándose a la distancia entre articulaciones; no es
una talla física. Se aplica a ambas manos y a los modos manual y automático.
La oclusión experimental usa el tamaño ajustado. La preferencia sobrevive a
desactivar/reactivar la cámara y las capturas esperan un nuevo fotograma al cambiarla.
Las nuevas muestras registran `settings.size_factor` y el ancho final solicitado
en `hands` al preparar el fotograma (`hand.requested_overlay_width_px` en el JSON
guardado). Las poses originales/suavizadas conservan el ancho base sin este factor
ni el margen del PNG. Los límites de seguridad del renderizado pueden reducir
el ancho solicitado. Los JSON antiguos sin `size_factor` corresponden a 1.0.

Debajo de los controles de **Prueba y captura** está **Aplicar oclusión
(experimental)**, desactivada al iniciar. Permite comparar el PNG completo con
una máscara suave que oculta su parte central hacia la base del dedo. Conserva
el seguimiento, la posición, los landmarks y los archivos PNG originales.
La preferencia sobrevive al desactivar/reactivar la cámara. Tras alternarla,
la captura espera un nuevo fotograma; los JSON incluyen `settings.occlusion`
y `occlusion_method` (`palm_half_strip_v1` cuando está activa).

Esta máscara es una hipótesis visual 2D: usa la dirección del dedo y el ancho
visible del PNG, no segmentación de piel ni profundidad. Puede ocultar partes
incorrectas en vistas laterales, de palma o imágenes con otra orientación.
No identifica automáticamente el aro trasero. Para evaluarla, oculta las
referencias, muestra el anillo y compara ambas opciones con la misma vista.
El método está separado en `occlusion.py`; no modifica tamaño ni anclaje.

En **Vista del anillo** puedes elegir **Pulgar, Índice, Medio, Anular o Meñique**
y mover el deslizador desde la base (0 %) hasta la siguiente articulación (100 %).
**Restablecer 50 %** vuelve al centro de ese segmento, no al centro de todo el dedo.
La selección se aplica a ambas manos detectadas; **Mano a validar** elige cuál
registrar al capturar. El dedo y la posición se conservan al reiniciar la cámara.

La posición se calcula con `P = A + t(B − A)`. Los segmentos son 2→3 para pulgar,
5→6 para índice, 9→10 para medio, 13→14 para anular y 17→18 para meñique.
Los landmarks permanecen fijos en la detección; la cruz señala el centro suavizado
usado para colocar el PNG, incluso cuando el anillo está oculto. Para verla,
mantén las referencias visibles. El centro visible de la joya depende del anclaje
del PNG. El tamaño sigue estimándose con la longitud del segmento; especialmente
en el pulgar, esto requiere validación visual y no representa una talla física.

Cada nueva muestra incluye `settings.finger`, `position_fraction` (0–1),
`landmark_indices`, `raw_pose.center` y `smoothed_pose.center` dentro de la mano.
`geometry_px.midpoint` conserva el punto medio geométrico para comparación.
Los JSON anteriores permanecen intactos: sin esos campos, corresponden al
comportamiento anterior (anular, 50 %). Cambiar dedo o posición invalida la captura
hasta mostrar un nuevo fotograma y reinicia el suavizado para evitar arrastrar
la joya desde el dedo anterior.

La casilla **Mostrar anillo**, en **Cámara y visualización**, permite ocultar
únicamente la joya. Los landmarks, las coordenadas y el seguimiento siguen
funcionando. La preferencia se mantiene al desactivar/reactivar la cámara.
Mientras está oculto no se pueden capturar muestras de ajuste; al mostrarlo se
espera un nuevo fotograma antes de habilitar la captura. Las nuevas muestras
incluyen `settings.show_ring` en sus datos JSON. No se modifica la posición del anillo.

Los controles se agrupan horizontalmente en **Cámara y visualización**, **Vista
del anillo** y **Prueba y captura**. Si el ancho no alcanza, el bloque de prueba
pasa a una segunda fila completa. El vídeo y las coordenadas mantienen su
funcionamiento; los mensajes de estado aparecen debajo y se ajustan al ancho.
Esta actualización reorganiza la GUI, sin añadir estimaciones 3D ni modificar
el seguimiento del anillo. Para disponer de más espacio de vídeo, maximiza la ventana.

### Sesiones JSON — parte 3

1. Escribe un nombre en **Prueba**, por ejemplo `json1` o `mano_derecha_luz_dia`.
2. Captura las muestras en modo manual como antes.
3. Pulsa **Guardar JSON**. El mensaje confirma el archivo en `data/sessions/`,
   dentro del proyecto, independientemente del directorio desde el que ejecutes.
4. Continúa capturando o descartando y guarda de nuevo para conservar otra copia.
5. **Nueva prueba** guarda los cambios pendientes y comienza una sesión vacía con
   otro identificador. La cámara continúa activa. **Salir** y cerrar la ventana
   también guardan los cambios pendientes. Si falla el guardado, se conserva la
   sesión abierta y se muestra el error para que puedas reintentarlo.

Cada JSON contiene `schema_version: 1` (versión del formato), `session_id`, nombre,
fechas UTC, `revision`, contador de muestras válidas y todas las muestras, incluidas
las descartadas. La revisión aumenta con cada captura o descarte; cambiar el nombre
no modifica la revisión de los datos. Cada guardado crea un archivo nuevo con nombre,
identificador y revisión, sin sobrescribir los anteriores. Los guardados repetidos
pueden contener las mismas muestras: un análisis futuro deberá evitar contarlas dos
veces usando `session_id`, `revision` y `sample_id`.

`session_store.py` realiza la persistencia y no añade dependencias. La carpeta
`data/sessions/` está excluida de Git para mantener las pruebas locales. No se guardan
sesiones vacías ni fotografías. Guarda periódicamente: un cierre forzado o corte de
energía puede perder cambios todavía en memoria. El guardado al salir corresponde
al cierre normal de la ventana.

Esta etapa permite conservar evidencia; todavía no permite reabrir una sesión
para editarla en la interfaz, entrenar ni escoger automáticamente la mejor prueba.
Los JSON tampoco incluyen copias de los PNG: conserva el catálogo usado junto con
su manifiesto para interpretar los nombres de las imágenes posteriormente.

## Estructura y responsabilidades

```text
virtual-jewelry-tryon/
|-- main.py                       # Punto de entrada
|-- virtual_jewelry_tryon/         # Paquete Python; imports relativos
|   |-- __init__.py
|   |-- cli.py                    # Argumentos, validación y códigos de salida
|   |-- config.py                 # Configuración y rutas de recursos
|   |-- app.py                    # Coordina el procesamiento de cada frame
|   |-- gui.py                    # Ventana, controles y actualización del video
|   |-- camera.py                 # Apertura y liberación de la webcam
|   |-- hand_detection.py         # MediaPipe, landmarks y depuración
|   |-- hand_orientation.py       # Izquierda/derecha, palma/dorso y elección de vista
|   |-- geometry.py               # Matemáticas del dedo anular
|   |-- geometry_view.py          # Dibujo de puntos y panel de medidas
|   |-- ring_overlay.py           # Escala, rotación y composición con transparencia
|   |-- ring_catalog.py           # Catálogo en memoria de las 36 vistas manuales
|   `-- smoothing.py              # Suavizado temporal por mano
|-- assets/
|   |-- references/
|   |   `-- pack_anillos.png       # Hoja original; primera fila = seis vistas
|   `-- rings/demo/
|       |-- ring_front.png         # Imagen generada de demostración
|       `-- ring_back.png          # Imagen generada de demostración
|-- models/
|   `-- hand_landmarker.task       # Modelo descargado; ignorado por Git
|-- tests/                        # Pruebas matemáticas y de integración
|-- docs/
|   |-- development_notes.md      # Fases y explicación de los algoritmos
|   `-- ring_assets.md             # Procedencia y prompts de las imágenes demo
|-- .vscode/                      # Intérprete y ejecución con F5
|-- requirements.txt
`-- .gitignore
```

El flujo es `main.py -> cli.py -> gui.py -> app.py`. El visor alternativo de OpenCV
también reutiliza `app.py`. La cámara y el detector se liberan
mediante gestores de contexto, incluso si ocurre una excepción. Importar módulos
no inicia la webcam. No se modifica `sys.path` ni se requiere instalar el proyecto
como paquete para ejecutarlo desde `main.py`.

### Imágenes originales y de demostración

Las 36 vistas entregadas en `pack_image_36/` tienen copias preparadas en
`assets/rings/views_36_normalized/`: lienzo transparente de 288 × 288 y anclaje
aproximado común, sin modificar los píxeles originales. Incluyen un `manifest.json`
para trazabilidad. **Disponibles en el modo Manual — 36 vistas**. Consulta los
[detalles y límites de la normalización](docs/normalized_views.md).

La primera fila de `assets/references/pack_anillos.png` contiene el mismo anillo en
las vistas front, left, right, top, back y perspective. La hoja se conserva intacta.
**Los PNG de `assets/rings/demo/` son imágenes generadas anteriormente, no recortes
de esa fila.** La reorganización conserva su uso como demostración predeterminada.
Las seis vistas originales todavía no están extraídas ni conectadas al programa.

En la demostración, el dorso de la mano selecciona la imagen decorativa y la palma
selecciona la banda. `--swap-ring-views` invierte la asociación. Una vista incierta
oculta el anillo. `back.png` de la hoja original no equivale necesariamente a la
vista de la banda sobre la palma.

## Instalación desde cero

No recrees `.venv` si ya funciona. En una instalación nueva:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force models | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" -OutFile "models/hand_landmarker.task"
```

Si `py` no encuentra Python, usa la ruta de tu instalación para crear `.venv`:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
```

Se ha trabajado con Python 3.12. Selecciona `.venv\Scripts\python.exe` en
**Python: Select Interpreter** de VS Code. Usa solamente `opencv-contrib-python`
en este entorno: otras distribuciones de OpenCV también proporcionan `cv2` y pueden
entrar en conflicto. Las dependencias están declaradas en `requirements.txt`.

## Validación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas no requieren webcam: verifican geometría, orientación, suavizado,
rotación, transparencia, argumentos, rutas y limpieza de recursos. Para validar
la ejecución real, pulsa **Activar cámara**, muestra una mano, gírala para alternar
palma/dorso y prueba dos manos. Pulsa **Desactivar cámara**, vuelve a activarla y
termina con **Salir**. Reabre el programa para comprobar que la cámara se liberó.

La estimación palma/dorso es una heurística 2D basada en los puntos 0, 5 y 17 y la
clasificación izquierda/derecha. No estima una pose 3D completa. Consulta las
[notas de desarrollo](docs/development_notes.md) para las fórmulas, umbrales,
convenciones de ángulo, mirroring y limitaciones. No se añaden modelos nuevos,
pulseras ni pendientes.
