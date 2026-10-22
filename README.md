# Procesador de Lotes de Imagenes en Paralelo

Aplicacion de escritorio para aplicar filtros a una carpeta de imagenes usando multiprocessing a nivel de CPU.

## Ejecucion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Tambien se puede procesar desde consola:

```powershell
python app.py --input ./entrada --output ./salida --filter grayscale --workers 4
```

Filtros disponibles: `grayscale`, `blur`, `sharpen`, `edge` y `sepia`.

## Idea de concurrencia

Cada imagen es una tarea independiente. El proceso principal crea un `Pool` de procesos de trabajo y distribuye las rutas mediante `imap_unordered`. Asi, el trabajo intensivo de Pillow se ejecuta en varios nucleos sin depender del GIL de Python.
