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
para trazabilidad. **Todavía no se usan en la aplicación**. Consulta los
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
