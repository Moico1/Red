# Image Lab

Aplicacion web responsive para subir lotes de imagenes y aplicar uno o varios filtros en paralelo. Las imagenes se procesan en memoria temporal y el resultado se descarga como un ZIP.

## Desarrollo local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` desde el navegador del ordenador o del celular conectado a la misma red. Para acceder desde otros dispositivos de la red:

```powershell
python app.py --host 0.0.0.0 --port 5000
```

## Despliegue

Usa Waitress en produccion:

```powershell
$env:SECRET_KEY = "una-clave-larga-y-secreta"
waitress-serve --listen=0.0.0.0:5000 app:app
```

Configura HTTPS y un limite de subida en el proxy inverso. El limite de la aplicacion es de 100 MB por solicitud.

## Filtros y concurrencia

Filtros disponibles: blanco y negro, desenfoque, nitidez, bordes, sepia, contraste, duotono azul/oro, relieve y contorno. Se pueden seleccionar varios filtros para generar una variante por filtro y por imagen.

- **Procesos CPU:** recomendado para filtros intensivos y lotes grandes; evita el GIL distribuyendo el trabajo entre nucleos.
- **Hilos:** util para lotes pequenos o cuando Pillow libera el GIL durante la operacion.
- **Secuencial:** referencia sencilla para comparar el rendimiento.

Cada imagen es una tarea independiente. El motor usa `ProcessPoolExecutor` o `ThreadPoolExecutor` segun la opcion elegida y devuelve un resultado individual por tarea, incluyendo errores sin cancelar el lote completo.

## Asistente de configuracion y demostracion

La interfaz calcula una recomendacion automatica usando el peso total del lote, la cantidad de imagenes y los nucleos disponibles en el dispositivo. Para demostrar la concurrencia:

1. Sube varias imagenes y selecciona dos o mas filtros. El resumen mostrara una tarea por cada imagen y filtro.
2. Ejecuta el lote con **Uno a uno** y anota el tiempo.
3. Ejecuta el mismo lote con **Procesos** y varias tareas simultaneas.
4. Compara los tiempos y observa el resumen: modo, numero de tareas, tareas simultaneas y segundos.

El ZIP se descarga automaticamente en la carpeta de descargas configurada por el navegador; el usuario no debe indicar una carpeta de salida.

## Uso desde consola

El modo web es la entrada principal. El motor sigue disponible desde Python mediante `process_batch` y `process_jobs` en `processor.py` para integrarlo con colas, tareas programadas o una API futura.
