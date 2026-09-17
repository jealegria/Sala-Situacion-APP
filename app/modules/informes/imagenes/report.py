"""
report.py — Informe de Imágenes
=================================
Este archivo contiene TODA la logica de generacion del informe de Imagenes.
La UI (app/ui/pages/informes/imagenes.py) solo llama a generar_informe().

Para modificar el informe de Imagenes en el futuro, editar SOLO este archivo.

Inputs esperados:
  - Archivos normalizados en Inputs/informes/imagenes/

Output:
  - Informe HTML en Outputs/informes/imagenes/
"""
from pathlib import Path
from typing import Callable

LogFn = Callable[[str], None]


def generar_informe(input_path: Path, output_path: Path, log: LogFn) -> None:
    """
    Genera el informe de Imagenes.

    Args:
        input_path:  Carpeta con los datos de entrada.
        output_path: Carpeta donde se guarda el informe generado.
        log:         Callback para emitir mensajes a la consola de la UI.
    """
    log("  [INFO] Modulo Imagenes — en construccion.")
    log(f"  Input  : {input_path}")
    log(f"  Output : {output_path}")
    log("  Aqui ira la logica del informe de Imagenes.")
