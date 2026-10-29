"""Procesamiento paralelo de imagenes para el proyecto educativo."""

from __future__ import annotations

import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageFilter, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}


@dataclass(frozen=True)
class Job:
    source: Path
    destination: Path
    filter_name: str
    output_format: str = "PNG"
    max_dimension: int | None = None


@dataclass(frozen=True)
class Result:
    source: Path
    destination: Path
    elapsed: float
    error: str | None = None


def _sepia(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image).convert("RGB")
    pixels = grayscale.load()
    for y in range(grayscale.height):
        for x in range(grayscale.width):
            value = pixels[x, y][0]
            pixels[x, y] = (
                min(255, int(value * 1.12 + 30)),
                min(255, int(value * 0.95 + 20)),
                min(255, int(value * 0.72 + 5)),
            )
    return grayscale


FILTERS: dict[str, Callable[[Image.Image], Image.Image]] = {
    "grayscale": ImageOps.grayscale,
    "blur": lambda image: image.filter(ImageFilter.GaussianBlur(radius=4)),
    "sharpen": lambda image: image.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3)),
    "edge": lambda image: image.filter(ImageFilter.FIND_EDGES),
    "sepia": _sepia,
    "contrast": lambda image: ImageOps.autocontrast(image),
    "color": lambda image: ImageOps.colorize(ImageOps.grayscale(image), "#162a46", "#f6b44b"),
    "emboss": lambda image: image.filter(ImageFilter.EMBOSS),
    "contour": lambda image: image.filter(ImageFilter.CONTOUR),
}


def _process_one(job: Job) -> Result:
    started = time.perf_counter()
    try:
        job.destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(job.source) as image:
            result = FILTERS[job.filter_name](image.convert("RGB"))
            if job.max_dimension and max(result.size) > job.max_dimension:
                result.thumbnail((job.max_dimension, job.max_dimension), Image.Resampling.LANCZOS)
            save_options = {"quality": 90, "optimize": True} if job.output_format == "JPEG" else {"optimize": True}
            result.save(job.destination, format=job.output_format, **save_options)
        return Result(job.source, job.destination, time.perf_counter() - started)
    except Exception as exc:  # noqa: BLE001 - cada tarea reporta su propio fallo
        return Result(job.source, job.destination, time.perf_counter() - started, str(exc))


def image_paths(input_dir: Path) -> list[Path]:
    return sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def build_jobs(input_dir: Path, output_dir: Path, filter_name: str) -> list[Job]:
    if filter_name not in FILTERS:
        raise ValueError(f"Filtro desconocido: {filter_name}")
    return [
        Job(source, output_dir / f"{source.stem}_{filter_name}.png", filter_name)
        for source in image_paths(input_dir)
    ]


def build_file_jobs(
    sources: Iterable[Path],
    output_dir: Path,
    filter_names: Iterable[str],
    output_format: str = "PNG",
    max_dimension: int | None = None,
) -> list[Job]:
    selected_filters = list(dict.fromkeys(filter_names))
    unknown = [name for name in selected_filters if name not in FILTERS]
    if unknown:
        raise ValueError(f"Filtros desconocidos: {', '.join(unknown)}")
    if output_format not in {"PNG", "JPEG", "WEBP"}:
        raise ValueError(f"Formato de salida desconocido: {output_format}")
    extension = "jpg" if output_format == "JPEG" else output_format.lower()
    return [
        Job(source, output_dir / f"{source.stem}_{filter_name}.{extension}", filter_name, output_format, max_dimension)
        for source in sources
        for filter_name in selected_filters
    ]


def process_jobs(
    jobs: list[Job],
    workers: int | None = None,
    mode: str = "processes",
    progress: Callable[[int, int, Result], None] | None = None,
) -> tuple[list[Result], float]:
    if not jobs:
        return [], 0.0
    worker_count = workers or max(1, mp.cpu_count() - 1)
    worker_count = max(1, min(worker_count, len(jobs)))
    executor_class = {
        "processes": ProcessPoolExecutor,
        "threads": ThreadPoolExecutor,
        "sequential": None,
    }.get(mode)
    if mode not in {"processes", "threads", "sequential"}:
        raise ValueError(f"Modo de concurrencia desconocido: {mode}")
    started = time.perf_counter()
    results: list[Result] = []
    if executor_class is None:
        completed_jobs = ((_process_one(job) for job in jobs), len(jobs))
        iterator = completed_jobs[0]
        total = completed_jobs[1]
        for completed, result in enumerate(iterator, start=1):
            results.append(result)
            if progress:
                progress(completed, total, result)
    else:
        with executor_class(max_workers=worker_count) as executor:
            for completed, result in enumerate(executor.map(_process_one, jobs), start=1):
                results.append(result)
                if progress:
                    progress(completed, len(jobs), result)
    return results, time.perf_counter() - started


def process_batch(
    input_dir: Path,
    output_dir: Path,
    filter_name: str,
    workers: int | None = None,
    progress: Callable[[int, int, Result], None] | None = None,
) -> tuple[list[Result], float]:
    jobs = build_jobs(input_dir, output_dir, filter_name)
    return process_jobs(jobs, workers, "processes", progress)


def process_sequential(input_dir: Path, output_dir: Path, filter_name: str) -> float:
    jobs = build_jobs(input_dir, output_dir, filter_name)
    started = time.perf_counter()
    for job in jobs:
        _process_one(job)
    return time.perf_counter() - started
