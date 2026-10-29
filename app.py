from __future__ import annotations

import argparse
import io
import os
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from processor import FILTERS, SUPPORTED_EXTENSIONS, build_file_jobs, process_jobs

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

FILTER_LABELS = {
    "grayscale": "Blanco y negro",
    "blur": "Desenfoque",
    "sharpen": "Nitidez",
    "edge": "Bordes",
    "sepia": "Sepia",
    "contrast": "Contraste",
    "color": "Duotono azul / oro",
    "emboss": "Relieve",
    "contour": "Contorno",
}
MODE_LABELS = {
    "processes": "Procesos",
    "threads": "Hilos",
    "sequential": "Uno a uno",
}
MODE_HELP = {
    "processes": "Recomendado: usa varios núcleos del procesador para acelerar lotes grandes.",
    "threads": "Ligero: varias tareas comparten el proceso y consume menos memoria.",
    "sequential": "Comparación: procesa una imagen cada vez y usa menos recursos.",
}


@app.get("/")
def index():
    return render_template("index.html", filters=FILTER_LABELS, modes=MODE_LABELS, mode_help=MODE_HELP)


@app.post("/process")
def process_images():
    uploads = request.files.getlist("images")
    selected_filters = [name for name in request.form.getlist("filters") if name in FILTERS]
    mode = request.form.get("mode", "processes")
    output_format = request.form.get("output_format", "PNG")
    try:
        max_dimension = max(0, min(8000, int(request.form.get("max_dimension", "0")))) or None
    except ValueError:
        max_dimension = None
    try:
        workers = max(1, min(32, int(request.form.get("workers", "4"))))
    except ValueError:
        workers = 4

    valid_uploads = [
        upload for upload in uploads
        if upload.filename and Path(upload.filename).suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not valid_uploads:
        flash("Selecciona al menos una imagen compatible.", "error")
        return redirect(url_for("index"))
    if not selected_filters:
        flash("Selecciona al menos un filtro.", "error")
        return redirect(url_for("index"))

    with tempfile.TemporaryDirectory(prefix="image-lab-") as temporary_dir:
        root = Path(temporary_dir)
        input_dir, output_dir = root / "input", root / "output"
        input_dir.mkdir()
        sources = []
        for position, upload in enumerate(valid_uploads):
            safe_name = secure_filename(upload.filename or f"image-{position}.jpg")
            source = input_dir / f"{position:03d}-{safe_name}"
            upload.save(source)
            sources.append(source)

        jobs = build_file_jobs(sources, output_dir, selected_filters, output_format, max_dimension)
        results, elapsed = process_jobs(jobs, workers, mode)
        errors = [result for result in results if result.error]
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for result in results:
                if not result.error and result.destination.exists():
                    bundle.write(result.destination, result.destination.name)
        archive.seek(0)
        filename = f"image-lab-{len(results) - len(errors)}-resultados.zip"
        response = send_file(archive, as_attachment=True, download_name=filename, mimetype="application/zip")
        response.headers["X-Processed-Images"] = str(len(results) - len(errors))
        response.headers["X-Processing-Errors"] = str(len(errors))
        response.headers["X-Processing-Seconds"] = f"{elapsed:.3f}"
        response.headers["X-Processing-Tasks"] = str(len(jobs))
        response.headers["X-Processing-Mode"] = mode
        response.headers["X-Processing-Workers"] = str(1 if mode == "sequential" else workers)
        return response


def cli() -> None:
    parser = argparse.ArgumentParser(description="Image Lab: filtros de imagen en paralelo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    cli()
