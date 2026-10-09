"""
processor.py — Partos con VSR
==============================
Cruza los eventos obstetricos (partos) con las aplicaciones de vacuna VSR
registradas en SISA y determina si cada internacion tuvo una vacuna VSR
aplicada dentro de la ventana valida (semana 32 a 36+6 de gestacion).

Adaptado desde _legacy/partos_con_vsr.py.

Fuentes de datos (archivos CSV individuales):
  - Eventos obstetricos : C:\\02_HPN\\01_Base\\eventos_obstetricos\\*.csv
  - SISA VSR            : C:\\02_HPN\\01_Base\\SISA\\VSR\\*.csv
Salida: C:\\03_Apps\\Sala-Situacion-APP\\Outputs\\utilidades\\eventos_obstetricos_con_vsr.csv
"""
from pathlib import Path
from typing import Callable

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES Y RUTAS
# ══════════════════════════════════════════════════════════════

DEFAULT_EVENTOS_DIR = Path(r"C:\02_HPN\01_Base\eventos_obstetricos")
DEFAULT_VSR_DIR     = Path(r"C:\02_HPN\01_Base\SISA\VSR")
DEFAULT_OUTPUT_PATH = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\utilidades")
ARCHIVO_SALIDA      = "eventos_obstetricos_con_vsr.csv"

# Ventana valida de vacunacion VSR (en semanas de gestacion)
SEMANA_INICIO_VENTANA = 32
SEMANA_FIN_VENTANA    = 36   # inclusive hasta 36+6

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  AUXILIARES
# ══════════════════════════════════════════════════════════════

def archivo_mas_reciente(carpeta: Path, patron: str = "*.csv") -> Path | None:
    """Retorna el archivo mas reciente (por fecha de modificacion) de la carpeta."""
    if not carpeta.is_dir():
        return None
    archivos = [p for p in carpeta.glob(patron) if p.is_file()]
    if not archivos:
        return None
    return max(archivos, key=lambda p: p.stat().st_mtime)


def _detectar_separador(archivo: Path) -> str:
    with open(archivo, "r", encoding="utf-8-sig") as f:
        linea = f.readline()
    return ";" if linea.count(";") >= linea.count(",") else ","


def _leer_csv(archivo: Path) -> pd.DataFrame:
    sep = _detectar_separador(archivo)
    return pd.read_csv(
        archivo,
        sep=sep,
        encoding="utf-8-sig",
        dtype=str,
        low_memory=False,
    )


def _normalizar_documento(serie: pd.Series) -> pd.Series:
    return (
        serie.astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )


def _validar_columnas(df: pd.DataFrame, columnas: list[str], nombre: str, log: LogFn) -> bool:
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        log(f"  [ERROR] Faltan columnas en {nombre}: {', '.join(faltantes)}")
        return False
    return True


# ══════════════════════════════════════════════════════════════
#  FUNCION PRINCIPAL
# ══════════════════════════════════════════════════════════════

def procesar_partos_con_vsr(
    eventos_file: Path,
    vsr_file: Path,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    log: LogFn = print,
) -> Path | None:
    """
    1. Lee el CSV de eventos obstetricos y el CSV de vacunas VSR (SISA).
    2. Calcula la fecha de inicio del embarazo (fechatermemb - edadgestacional).
    3. Define la ventana valida de vacunacion (sem 32 a 36+6).
    4. Cruza por documento y marca si la vacuna cae dentro de la ventana.
    5. Agrega columnas vsr_valida (SI/NO) y fecha_vacuna_vsr y guarda el CSV.
    """
    log("=" * 60)
    log("  PARTOS CON VSR")
    log("=" * 60)
    log(f"  Eventos obstetricos: {eventos_file}")
    log(f"  Vacunas VSR (SISA) : {vsr_file}")
    log(f"  Carpeta destino    : {output_path}")

    if not eventos_file.is_file():
        log(f"  [ERROR] No existe el archivo de eventos obstetricos: {eventos_file}")
        return None
    if not vsr_file.is_file():
        log(f"  [ERROR] No existe el archivo de vacunas VSR: {vsr_file}")
        return None

    # ── Carga ────────────────────────────────────────────────
    log("\n--- Lectura de archivos ---")
    eventos = _leer_csv(eventos_file)
    log(f"  Eventos obstetricos: {len(eventos):,} registros")
    vacunas = _leer_csv(vsr_file)
    log(f"  Vacunas VSR        : {len(vacunas):,} registros")

    if not _validar_columnas(
        eventos,
        ["idinternacion", "numero_documento", "fechatermemb", "edadgestacional"],
        "eventos obstetricos", log,
    ):
        return None
    if not _validar_columnas(
        vacunas, ["nro_de_documento", "fecha_de_aplicacion"], "vacunas VSR", log,
    ):
        return None

    # ── Normalizacion ────────────────────────────────────────
    log("\n--- Normalizacion ---")
    eventos["numero_documento"] = _normalizar_documento(eventos["numero_documento"])
    vacunas["nro_de_documento"] = _normalizar_documento(vacunas["nro_de_documento"])

    eventos["fechatermemb"] = pd.to_datetime(
        eventos["fechatermemb"], dayfirst=True, errors="coerce"
    )
    vacunas["fecha_de_aplicacion"] = pd.to_datetime(
        vacunas["fecha_de_aplicacion"], dayfirst=True, errors="coerce"
    )
    eventos["edadgestacional"] = pd.to_numeric(
        eventos["edadgestacional"], errors="coerce"
    )

    sin_fecha = int(eventos["fechatermemb"].isna().sum())
    sin_eg    = int(eventos["edadgestacional"].isna().sum())
    if sin_fecha:
        log(f"  [AVISO] {sin_fecha:,} eventos sin fecha de terminacion valida")
    if sin_eg:
        log(f"  [AVISO] {sin_eg:,} eventos sin edad gestacional valida")

    # ── Ventana valida de vacunacion ─────────────────────────
    log("\n--- Calculo de ventana VSR ---")
    dias_gestacion = eventos["edadgestacional"].mul(7)
    td = pd.Series(pd.NaT, index=eventos.index, dtype="timedelta64[ns]")
    mask = dias_gestacion.notna()
    td.loc[mask] = pd.to_timedelta(dias_gestacion.loc[mask], unit="D")

    eventos["fecha_inicio_embarazo"] = eventos["fechatermemb"] - td
    eventos["inicio_ventana_vsr"] = (
        eventos["fecha_inicio_embarazo"]
        + pd.to_timedelta(SEMANA_INICIO_VENTANA * 7, unit="D")
    )
    eventos["fin_ventana_vsr"] = (
        eventos["fecha_inicio_embarazo"]
        + pd.to_timedelta((SEMANA_FIN_VENTANA * 7) + 6, unit="D")
    )
    log(f"  Ventana: semana {SEMANA_INICIO_VENTANA} a {SEMANA_FIN_VENTANA}+6")

    # ── Cruce ────────────────────────────────────────────────
    log("\n--- Cruce eventos x vacunas ---")
    cruce = eventos.merge(
        vacunas[["nro_de_documento", "fecha_de_aplicacion"]],
        left_on="numero_documento",
        right_on="nro_de_documento",
        how="left",
    )
    cruce["vsr_valida"] = (
        (cruce["fecha_de_aplicacion"] >= cruce["inicio_ventana_vsr"])
        & (cruce["fecha_de_aplicacion"] <= cruce["fin_ventana_vsr"])
    )

    resultado = (
        cruce.groupby("idinternacion", dropna=False)
        .agg(
            vsr_valida=("vsr_valida", "max"),
            fecha_vacuna_vsr=("fecha_de_aplicacion", "max"),
        )
        .reset_index()
    )
    resultado["vsr_valida"] = resultado["vsr_valida"].map({True: "SI", False: "NO"})
    resultado["fecha_vacuna_vsr"] = resultado["fecha_vacuna_vsr"].dt.strftime("%d/%m/%Y")

    salida = eventos.merge(resultado, on="idinternacion", how="left")

    # ── Resumen ──────────────────────────────────────────────
    total_int  = salida["idinternacion"].nunique()
    validas    = salida.drop_duplicates("idinternacion")["vsr_valida"].eq("SI").sum()
    con_vacuna = salida.drop_duplicates("idinternacion")["fecha_vacuna_vsr"].notna().sum()
    pct = (validas / total_int * 100) if total_int else 0
    log(f"  Internaciones unicas          : {total_int:,}")
    log(f"  Con alguna vacuna VSR         : {con_vacuna:,}")
    log(f"  Con VSR dentro de ventana     : {validas:,} ({pct:.1f}%)")

    # ── Salida ───────────────────────────────────────────────
    output_path.mkdir(parents=True, exist_ok=True)
    archivo_salida = output_path / ARCHIVO_SALIDA
    try:
        salida.to_csv(archivo_salida, sep=";", index=False, encoding="utf-8-sig")
    except PermissionError:
        log(f"\n  [ERROR] No se pudo escribir {archivo_salida}. "
            f"¿Esta abierto en Excel?")
        return None

    log(f"\n  [OK] Archivo generado: {archivo_salida}")
    log("=" * 60)
    return archivo_salida
