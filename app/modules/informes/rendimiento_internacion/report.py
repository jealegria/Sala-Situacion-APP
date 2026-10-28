"""
report.py — Informe de Rendimiento de Internación
=================================================
Lógica de consolidación y procesamiento para el informe interactivo de
Rendimiento de Internación General.
La plantilla visual desacoplada reside en `template.html`.
La UI (app/ui/pages/informes/rendimiento_internacion.py) solo llama a generar_informe().

Fuente de datos:
  - Excel Base: C:\\02_HPN\\01_Base\\rendimiento_estadistica\\A- RENDIMIENTO INTERNACION GENERAL 2026.xlsx
Salida:
  - C:\\03_Apps\\Sala-Situacion-APP\\Outputs\\informes\\Rendimiento Internacion.html
"""

from pathlib import Path
from datetime import datetime
from typing import Callable, Optional
import json
import pandas as pd

from app.modules.informes.rendimiento_internacion.reader import (
    DEFAULT_EXCEL_PATH,
    parse_rendimiento_excel,
)

MODULE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = MODULE_DIR / "template.html"

DEFAULT_OUTPUT_DIR = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\informes")
HTML_OUTPUT_NAME = "Rendimiento Internacion.html"

LogFn = Callable[[str], None]


def generar_informe(
    input_excel: Path = DEFAULT_EXCEL_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    log: Optional[LogFn] = None,
) -> Path:
    """
    Genera el informe HTML interactivo de Rendimiento de Internación.

    Parámetros:
        input_excel: Ruta al archivo Excel de rendimiento de internación.
        output_dir: Carpeta donde guardar el HTML de salida.
        log: Función de callback para logging hacia la UI o consola.

    Retorna:
        Path del archivo HTML generado.
    """
    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    _log("Iniciando generación de informe de Rendimiento de Internación...")
    _log(f"  Archivo fuente : {input_excel}")
    _log(f"  Carpeta destino: {output_dir}")

    input_path = Path(input_excel)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de entrada: {input_path}")

    # 1. Extraer todos los datos del Excel
    _log("Extrayendo datos de internación de todos los meses...")
    df = parse_rendimiento_excel(file_path=input_path, mes_filtro=None, log=_log)

    if df.empty:
        raise ValueError("No se encontraron registros de rendimiento en el archivo proporcionado.")

    anio = int(df["anio"].iloc[0]) if "anio" in df.columns else datetime.now().year
    _log(f"Datos leídos: {len(df)} registros para el año {anio}.")

    # 2. Convertir DataFrame a lista de diccionarios para inyectar en JS
    records = df.to_dict(orient="records")
    data_json = json.dumps(records, ensure_ascii=False)

    # 3. Leer template HTML
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la plantilla HTML en: {TEMPLATE_PATH}")

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_content = f.read()

    # 4. Inyectar datos y metadatos
    html_final = template_content.replace("__ANIO__", str(anio))
    html_final = html_final.replace("__DATA_JSON__", data_json)

    # 5. Guardar resultado
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / HTML_OUTPUT_NAME

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_final)

    _log(f"Informe generado exitosamente en: {out_file}")
    return out_file


if __name__ == "__main__":
    out = generar_informe()
    print(f"Informe listo: {out}")
