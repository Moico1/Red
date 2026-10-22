from __future__ import annotations

import argparse
import multiprocessing as mp
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from processor import FILTERS, process_batch


class BatchProcessorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Procesador paralelo de imagenes")
        self.geometry("760x540")
        self.minsize(680, 480)
        self.configure(bg="#101722")
        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#101722")
        style.configure("TLabel", background="#101722", foreground="#dbe7f2", font=("Segoe UI", 10))
        style.configure("Title.TLabel", foreground="#f4f8fb", font=("Segoe UI", 24, "bold"))
        style.configure("Sub.TLabel", foreground="#8fa4b8", font=("Segoe UI", 10))
        style.configure("TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background="#f28f3b", foreground="#101722")
        style.map("Accent.TButton", background=[("active", "#ffae62")])
        style.configure("TEntry", fieldbackground="#182433", foreground="#f4f8fb")
        style.configure("TCombobox", fieldbackground="#182433", foreground="#f4f8fb")
        style.configure("Horizontal.TProgressbar", troughcolor="#182433", background="#51c6a8")

        outer = ttk.Frame(self, padding=28)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="PROCESADOR DE LOTES", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Imagenes en paralelo", style="Title.TLabel").pack(anchor="w", pady=(2, 4))
        ttk.Label(outer, text="Aplica filtros usando varios nucleos de CPU al mismo tiempo.", style="Sub.TLabel").pack(anchor="w", pady=(0, 22))

        settings = ttk.Frame(outer)
        settings.pack(fill="x")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="grayscale")
        self.workers_var = tk.StringVar(value=str(max(1, (mp.cpu_count() or 2) - 1)))
        self._path_row(settings, 0, "Carpeta de entrada", self.input_var, self._choose_input)
        self._path_row(settings, 1, "Carpeta de salida", self.output_var, self._choose_output)

        ttk.Label(settings, text="Filtro").grid(row=2, column=0, sticky="w", pady=(14, 6))
        filter_box = ttk.Combobox(settings, textvariable=self.filter_var, values=list(FILTERS), state="readonly", width=20)
        filter_box.grid(row=2, column=1, sticky="w", pady=(14, 6))
        ttk.Label(settings, text="Procesos").grid(row=2, column=2, sticky="w", padx=(24, 8), pady=(14, 6))
        ttk.Spinbox(settings, from_=1, to=max(1, mp.cpu_count() * 2), textvariable=self.workers_var, width=7).grid(row=2, column=3, sticky="w", pady=(14, 6))
        settings.columnconfigure(1, weight=1)

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(22, 12))
        self.run_button = ttk.Button(action_row, text="Procesar imagenes", style="Accent.TButton", command=self._start)
        self.run_button.pack(side="left")
        self.status_var = tk.StringVar(value="Listo para procesar")
        ttk.Label(action_row, textvariable=self.status_var, style="Sub.TLabel").pack(side="left", padx=16)

        self.progress = ttk.Progressbar(outer, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 22))
        log_frame = ttk.Frame(outer)
        log_frame.pack(fill="both", expand=True)
        ttk.Label(log_frame, text="REGISTRO DE EJECUCION", style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        self.log = tk.Text(log_frame, height=10, bg="#182433", fg="#b8cad9", insertbackground="#ffffff", relief="flat", padx=12, pady=10, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self._write("Selecciona una carpeta con imagenes JPG, PNG, BMP, WEBP o TIFF.")

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, command: object) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(14, 8), pady=6)
        ttk.Button(parent, text="Examinar", command=command).grid(row=row, column=2, pady=6)

    def _choose_input(self) -> None:
        selected = filedialog.askdirectory(title="Seleccionar entrada")
        if selected:
            self.input_var.set(selected)
            if not self.output_var.get():
                self.output_var.set(str(Path(selected) / "procesadas"))

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Seleccionar salida")
        if selected:
            self.output_var.set(selected)

    def _write(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def _start(self) -> None:
        input_dir, output_dir = Path(self.input_var.get()), Path(self.output_var.get())
        if not input_dir.is_dir() or not output_dir:
            messagebox.showwarning("Datos incompletos", "Selecciona las carpetas de entrada y salida.")
            return
        try:
            workers = max(1, int(self.workers_var.get()))
        except ValueError:
            messagebox.showwarning("Procesos invalidos", "El numero de procesos debe ser entero.")
            return
        self.run_button.state(["disabled"])
        self.progress.configure(value=0)
        self.status_var.set("Procesando...")
        self._write(f"Iniciando {self.filter_var.get()} con {workers} procesos...")
        threading.Thread(target=self._run, args=(input_dir, output_dir, self.filter_var.get(), workers), daemon=True).start()

    def _run(self, input_dir: Path, output_dir: Path, filter_name: str, workers: int) -> None:
        def progress(completed: int, total: int, result: object) -> None:
            self.after(0, self._progress, completed, total, result)

        results, elapsed = process_batch(input_dir, output_dir, filter_name, workers, progress)
        errors = sum(result.error is not None for result in results)
        self.after(0, self._finished, len(results), errors, elapsed)

    def _progress(self, completed: int, total: int, result: object) -> None:
        self.progress.configure(value=completed / total * 100)
        self.status_var.set(f"{completed}/{total} imagenes")
        if result.error:
            self._write(f"ERROR {result.source.name}: {result.error}")
        else:
            self._write(f"OK {result.source.name} -> {result.destination.name}")

    def _finished(self, total: int, errors: int, elapsed: float) -> None:
        self.run_button.state(["!disabled"])
        self.status_var.set(f"Finalizado en {elapsed:.2f} s")
        self._write(f"Completado: {total - errors} correctas, {errors} con error. Tiempo total: {elapsed:.2f} s")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Procesador paralelo de imagenes")
    parser.add_argument("--input", type=Path, help="Carpeta de entrada")
    parser.add_argument("--output", type=Path, help="Carpeta de salida")
    parser.add_argument("--filter", choices=FILTERS, default="grayscale")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    if args.input:
        if not args.output:
            parser.error("--output es obligatorio en modo consola")
        results, elapsed = process_batch(args.input, args.output, args.filter, args.workers)
        errors = [result for result in results if result.error]
        print(f"Procesadas: {len(results) - len(errors)}/{len(results)} | Tiempo: {elapsed:.2f} s")
        for result in errors:
            print(f"ERROR {result.source}: {result.error}")
        return
    BatchProcessorApp().mainloop()


if __name__ == "__main__":
    mp.freeze_support()
    cli()
