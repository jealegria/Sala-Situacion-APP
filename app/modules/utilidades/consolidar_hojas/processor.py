"""
processor.py — Consolidar Hojas
===============================
Equivalente en Python de la macro de Excel `ConsolidarHojas`.

Logica de la macro (replicada tal cual):
  1. Recorre todas las hojas del libro (incluidas las ocultas).
  2. Los encabezados son la fila 1 de la PRIMERA hoja (solo se copian una vez).
  3. De cada hoja toma las filas 2..ultima fila de la columna A
     (la ultima fila se calcula con la columna A, como End(xlUp)).
  4. Conserva solo las filas que tengan algo en la columna J (columna 10).
  5. Apila todo en una unica tabla "Consolidado".

Diferencia: en lugar de agregar una hoja al libro original, se genera un
Excel nuevo con una unica hoja "Consolidado" (solo valores).
"""
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES Y RUTAS
# ══════════════════════════════════════════════════════════════

DEFAULT_INPUT_DIR   = Path(r"C:\02_HPN\01_Base")
DEFAULT_OUTPUT_PATH = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\utilidades")
ARCHIVO_SALIDA      = "consolidado.csv"

COL_FILTRO_IDX = 9      # Columna J (indice base 0)
COL_ULTIMA_FILA_IDX = 0 # Columna A: define la ultima fila de cada hoja
HOJA_CONSOLIDADO = "Consolidado"

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  AUXILIARES
# ══════════════════════════════════════════════════════════════

def _vacio(valor) -> bool:
    """True si la celda esta vacia (equivale a Value = '' en Excel)."""
    if valor is None:
        return True
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(valor, str) and valor == ""


def _formatear(valor):
    """Normaliza un valor de celda: vacio -> None, enteros flotantes -> int.
    Fechas y numeros se mantienen con su tipo nativo para el Excel."""
    if _vacio(valor):
        return None
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


def _ultima_fila_con_datos(df: pd.DataFrame, col_idx: int) -> int:
    """Indice (base 0) de la ultima fila no vacia en la columna; -1 si no hay."""
    if col_idx >= df.shape[1]:
        return -1
    no_vacias = [i for i, v in enumerate(df.iloc[:, col_idx]) if not _vacio(v)]
    return no_vacias[-1] if no_vacias else -1


# ══════════════════════════════════════════════════════════════
#  FUNCION PRINCIPAL
# ══════════════════════════════════════════════════════════════

def consolidar_hojas(
    input_file: Path,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    log: LogFn = print,
) -> Path | None:
    """Consolida todas las hojas del Excel en un unico CSV (solo valores)."""
    log("=" * 60)
    log("  LIMPIAR EXCEL QUIRÓFANO")
    log("=" * 60)
    log(f"  Archivo Excel   : {input_file}")
    log(f"  Carpeta destino : {output_path}")

    if not input_file.is_file():
        log(f"  [ERROR] No existe el archivo: {input_file}")
        return None

    log("\n--- Lectura del libro ---")
    hojas = pd.read_excel(input_file, sheet_name=None, header=None, dtype=object)
    # La macro borra la hoja "Consolidado" si existe: se ignora.
    hojas = {n: d for n, d in hojas.items() if n != HOJA_CONSOLIDADO}
    log(f"  Hojas encontradas: {len(hojas)}")
    if not hojas:
        log("  [ERROR] El libro no tiene hojas para consolidar.")
        return None

    encabezado: list | None = None
    bloques: list[pd.DataFrame] = []
    total_filas = 0

    log("\n--- Consolidacion ---")
    for nombre, df in hojas.items():
        if df.empty:
            log(f"  {nombre}: hoja vacia")
            continue

        if encabezado is None:
            encabezado = [_formatear(v) for v in df.iloc[0]]

        ultima = _ultima_fila_con_datos(df, COL_ULTIMA_FILA_IDX)
        if ultima < 1 or df.shape[1] <= COL_FILTRO_IDX:
            log(f"  {nombre}: 0 filas (sin datos en columna A / sin columna J)")
            continue

        # Filas 2..ultima (indices 1..ultima) con columna J no vacia
        datos = df.iloc[1:ultima + 1]
        mascara = ~datos.iloc[:, COL_FILTRO_IDX].map(_vacio)
        datos = datos[mascara]
        log(f"  {nombre}: {len(datos):,} filas")
        total_filas += len(datos)
        bloques.append(datos)

    if encabezado is None:
        log("  [ERROR] No se encontro encabezado (todas las hojas estan vacias).")
        return None

    consolidado = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame()

    # Alinear columnas con el encabezado (la macro copia filas completas)
    n_cols = max(len(encabezado), consolidado.shape[1])
    consolidado = consolidado.reindex(columns=range(n_cols))
    encabezado = encabezado + [None] * (n_cols - len(encabezado))
    consolidado = consolidado.map(_formatear)
    consolidado = consolidado.astype(object).where(consolidado.notna(), None)
    # Encabezado como primera fila de datos (permite celdas de titulo vacias)
    consolidado.columns = range(n_cols)

    # ── Guardado ─────────────────────────────────────────────
    output_path.mkdir(parents=True, exist_ok=True)
    salida = output_path / f"{input_file.stem}_consolidado.xlsx"
    tabla = pd.concat(
        [pd.DataFrame([encabezado], dtype=object), consolidado], ignore_index=True
    )
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        tabla.to_excel(writer, sheet_name=HOJA_CONSOLIDADO, header=False, index=False)

    log("\n--- Resultado ---")
    log(f"  Total de filas consolidadas: {total_filas:,}")
    log(f"  Columnas                   : {n_cols}")
    log(f"  Archivo generado           : {salida}")
    log("\n  Consolidacion completa.")
    return salida
