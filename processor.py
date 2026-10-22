"""Procesamiento paralelo de imagenes para el proyecto educativo."""

from __future__ import annotations

import multiprocessing as mp
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageFilter, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}


@dataclass(frozen=True)
class Job:
    source: Path
    destination: Path
    filter_name: str


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
}


def _process_one(job: Job) -> Result:
    started = time.perf_counter()
    try:
        job.destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(job.source) as image:
            result = FILTERS[job.filter_name](image.convert("RGB"))
            result.save(job.destination)
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


def process_batch(
    input_dir: Path,
    output_dir: Path,
    filter_name: str,
    workers: int | None = None,
    progress: Callable[[int, int, Result], None] | None = None,
) -> tuple[list[Result], float]:
    jobs = build_jobs(input_dir, output_dir, filter_name)
    if not jobs:
        return [], 0.0
    worker_count = workers or max(1, mp.cpu_count() - 1)
    worker_count = max(1, min(worker_count, len(jobs)))
    started = time.perf_counter()
    results: list[Result] = []
    with mp.Pool(processes=worker_count) as pool:
        for completed, result in enumerate(pool.imap_unordered(_process_one, jobs), start=1):
            results.append(result)
            if progress:
                progress(completed, len(jobs), result)
    return results, time.perf_counter() - started


def process_sequential(input_dir: Path, output_dir: Path, filter_name: str) -> float:
    jobs = build_jobs(input_dir, output_dir, filter_name)
    started = time.perf_counter()
    for job in jobs:
        _process_one(job)
    return time.perf_counter() - started
