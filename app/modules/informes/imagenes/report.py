"""
report.py — Informe de Imágenes
=================================
Logica de consolidacion y procesamiento de datos para el Panel de Imagenes.
La plantilla visual reside en `template.html`.
La UI (app/ui/pages/informes/imagenes.py) solo llama a generar_informe().

Adaptado desde _legacy/prestaciones_imagenes.py.

Fuentes de datos:
  - Agendas consolidadas : C:\\02_HPN\\01_Base\\agendas_consolidado\\*.csv
  - Fuera de agenda      : C:\\02_HPN\\01_Base\\fuera_agenda\\*.csv
  - Internacion Andes    : C:\\02_HPN\\01_Base\\internacion_andes\\*.csv
  - Imagenes (Intranet)  : C:\\02_HPN\\01_Base\\imagenes\\*.csv
  - Mapeo de grupos      : C:\\02_HPN\\01_Base\\tablas_relacionales\\imagenes_procedimientos_agrupados.csv
Salida: C:\\03_Apps\\Sala-Situacion-APP\\Outputs\\informes\\Panel Imagenes.html
"""
from pathlib import Path
from datetime import datetime
from typing import Callable
import json
import re
import unicodedata

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES Y RUTAS
# ══════════════════════════════════════════════════════════════

MODULE_DIR    = Path(__file__).resolve().parent
TEMPLATE_PATH = MODULE_DIR / "template.html"

DEFAULT_INPUT_AGENDAS      = Path(r"C:\02_HPN\01_Base\agendas_consolidado")
DEFAULT_INPUT_FUERA_AGENDA = Path(r"C:\02_HPN\01_Base\fuera_agenda")
DEFAULT_INPUT_INTERNACION  = Path(r"C:\02_HPN\01_Base\internacion_andes")
DEFAULT_INPUT_IMAGENES     = Path(r"C:\02_HPN\01_Base\imagenes")
DEFAULT_MAPEO_DIR          = Path(r"C:\02_HPN\01_Base\tablas_relacionales")
DEFAULT_MAPEO_FILE         = DEFAULT_MAPEO_DIR / "imagenes_procedimientos_agrupados.csv"
DEFAULT_OUTPUT_PATH        = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\informes")
HTML_OUTPUT_NAME           = "Panel Imagenes.html"

COLUMNAS_BASE = ["fechaconsulta", "tipoprestacion", "localidad", "edad", "uniedad", "origen", "dni"]

PATRON_IMAGENES = r"ecograf|radiograf|resonanc|tomograf|mamograf|rx\b|rmn\b|tac\b|\beco\b|ecocardio"

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  AUXILIARES
# ══════════════════════════════════════════════════════════════

def _normalizar(texto) -> str:
    if pd.isna(texto):
        return ""
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join(c for c in nfkd_form if not unicodedata.combining(c))


def _clean_localidad(loc) -> str:
    if pd.isna(loc) or str(loc).strip() == "":
        return "(Sin dato)"
    return _remove_accents(str(loc).strip()).title()


def _rango_edad(edad_anos: int) -> str:
    if edad_anos <= 10:
        return "1 - 10 años"
    elif edad_anos <= 20:
        return "11 - 20 años"
    elif edad_anos <= 30:
        return "21 - 30 años"
    elif edad_anos <= 40:
        return "31 - 40 años"
    elif edad_anos <= 50:
        return "41 - 50 años"
    elif edad_anos <= 60:
        return "51 - 60 años"
    elif edad_anos <= 70:
        return "61 - 70 años"
    elif edad_anos <= 80:
        return "71 - 80 años"
    return "81+ años"


def _procesar_edad(row) -> tuple[str, str]:
    """Retorna (edad_clean, edad_rango) segun el origen del registro."""
    sin_dato = ("(Sin dato)", "(Sin dato)")
    menor_1  = ("<1 año", "<1 año")

    edad_raw = row.get("edad")
    if pd.isna(edad_raw) or str(edad_raw).strip() == "":
        return sin_dato

    nums = re.findall(r"\d+", str(edad_raw))
    if not nums:
        return sin_dato
    edad_num = int(nums[0])

    if row.get("origen") == "Intranet":
        edad_str_lower = str(edad_raw).lower()
        if ("mes" in edad_str_lower or "dia" in edad_str_lower or "días" in edad_str_lower
                or "m" in re.findall(r"\b[md]\b", edad_str_lower)):
            return menor_1
    else:
        uniedad_raw = row.get("uniedad")
        uni = str(uniedad_raw).strip().upper() if pd.notna(uniedad_raw) else "A"
        if uni in ["D", "DIAS", "DIA", "M", "MES", "MESES"]:
            return menor_1

    if edad_num < 1:
        return menor_1

    return f"{edad_num} años", _rango_edad(edad_num)


def _leer_carpeta_csv(carpeta: Path | None, etiqueta: str, log: LogFn) -> list[pd.DataFrame]:
    """Lee todos los CSV de una carpeta (sep=';'). Retorna lista de DataFrames."""
    dfs: list[pd.DataFrame] = []
    if not carpeta or not str(carpeta).strip() or not carpeta.is_dir():
        log(f"  [AVISO] Carpeta de {etiqueta} no encontrada: {carpeta}")
        return dfs
    archivos = sorted(carpeta.glob("*.csv"))
    if not archivos:
        log(f"  [AVISO] No hay CSVs en la carpeta de {etiqueta}: {carpeta}")
    for archivo in archivos:
        log(f"  Leyendo {etiqueta}: {archivo.name}")
        dfs.append(pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False))
    return dfs


def _parse_fecha(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(
        serie.astype(str).str.strip(), format="mixed", dayfirst=True, errors="coerce"
    )


def _cargar_mapeo(ruta: Path | None, log: LogFn) -> dict[str, str]:
    if not ruta or not ruta.is_file():
        log(f"  [AVISO] No se encontró el archivo de mapeo: {ruta}")
        return {}
    try:
        df_mapeo = pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str)
        if "procedimientos" not in df_mapeo.columns:
            df_mapeo = pd.read_csv(ruta, sep=",", encoding="utf-8-sig", dtype=str)
        if "procedimientos" in df_mapeo.columns and "grupo" in df_mapeo.columns:
            df_mapeo["procedimientos"] = df_mapeo["procedimientos"].fillna("").astype(str).str.strip()
            df_mapeo["grupo"] = df_mapeo["grupo"].fillna("").astype(str).str.strip()
            df_mapeo = df_mapeo[df_mapeo["grupo"] != ""].copy()
            dict_grupos = dict(zip(df_mapeo["procedimientos"], df_mapeo["grupo"]))
            log(f"  Mapeo de grupos cargado: {len(dict_grupos)} procedimientos mapeados")
            return dict_grupos
        log("  [AVISO] El archivo de mapeo no tiene las columnas 'procedimientos' y 'grupo'")
    except Exception as e:
        log(f"  [ERROR] Al leer el archivo de mapeo: {e}")
    return {}


# ══════════════════════════════════════════════════════════════
#  LECTURA POR FUENTE
# ══════════════════════════════════════════════════════════════

def _cargar_agendas(carpeta: Path | None, anio: int, log: LogFn) -> pd.DataFrame:
    dfs = _leer_carpeta_csv(carpeta, "agendas", log)
    if not dfs:
        return pd.DataFrame(columns=COLUMNAS_BASE)
    df = pd.concat(dfs, ignore_index=True)
    for col in ["fechaconsulta", "localidad", "edad", "uniedad", "tipoprestacion", "idturno", "dni"]:
        if col not in df.columns:
            df[col] = ""
    df["fechaconsulta"] = _parse_fecha(df["fechaconsulta"])
    df = df.dropna(subset=["fechaconsulta"])
    df = df[df["fechaconsulta"].dt.year == anio].copy()
    if df["idturno"].astype(str).str.strip().any():
        df = df.drop_duplicates(subset="idturno")
    df["origen"] = "agenda"
    return df[COLUMNAS_BASE].copy()


def _cargar_fuera_agenda(carpeta: Path | None, anio: int, log: LogFn) -> pd.DataFrame:
    dfs = _leer_carpeta_csv(carpeta, "fuera agenda", log)
    if not dfs:
        return pd.DataFrame(columns=COLUMNAS_BASE)
    df = pd.concat(dfs, ignore_index=True)
    for col in ["fechaconsulta", "localidad", "edad", "uniedad", "tipoprestacion", "idprestacion", "dni"]:
        if col not in df.columns:
            df[col] = ""
    df["fechaconsulta"] = _parse_fecha(df["fechaconsulta"])
    df = df.dropna(subset=["fechaconsulta"])
    df = df[df["fechaconsulta"].dt.year == anio].copy()
    if df["idprestacion"].astype(str).str.strip().any():
        df = df.drop_duplicates(subset="idprestacion")
    df["origen"] = "fuera_agenda"
    return df[COLUMNAS_BASE].copy()


def _cargar_intranet(carpeta: Path | None, anio: int, log: LogFn) -> pd.DataFrame:
    dfs = _leer_carpeta_csv(carpeta, "Intranet", log)
    if not dfs:
        return pd.DataFrame(columns=COLUMNAS_BASE)
    renombres = {
        "fecha": "fechaconsulta",
        "documento": "dni",
        "edad_al_momento_de_la_prestacion": "edad",
    }
    dfs = [d.rename(columns={k: v for k, v in renombres.items() if k in d.columns}) for d in dfs]
    df = pd.concat(dfs, ignore_index=True)
    for col in ["fechaconsulta", "tipoprestacion", "dni", "edad"]:
        if col not in df.columns:
            df[col] = ""
    df["fechaconsulta"] = _parse_fecha(df["fechaconsulta"])
    df = df.dropna(subset=["fechaconsulta"])
    df = df[df["fechaconsulta"].dt.year == anio].copy()

    # Exclusion: no traer mamografias del origen Intranet
    mask_mamografia = df["tipoprestacion"].apply(_normalizar).str.contains("mamograf", na=False)
    excluidas = int(mask_mamografia.sum())
    df = df[~mask_mamografia].copy()
    if excluidas:
        log(f"  Mamografías de Intranet excluidas: {excluidas:,}")

    if "protocolo" in df.columns and df["protocolo"].astype(str).str.strip().any():
        df = df.drop_duplicates(subset="protocolo")

    df["origen"]    = "Intranet"
    df["localidad"] = ""
    df["uniedad"]   = ""
    return df[COLUMNAS_BASE].copy()


def _cargar_internacion(carpeta: Path | None, log: LogFn) -> pd.DataFrame:
    dfs = _leer_carpeta_csv(carpeta, "internación", log)
    if not dfs:
        return pd.DataFrame(columns=["dni_clean", "ingreso_dt", "egreso_dt"])
    df = pd.concat(dfs, ignore_index=True)
    for col in ["numero_documento", "fechaingreso", "fechaegreso", "prestacionid"]:
        if col not in df.columns:
            df[col] = ""
    if df["prestacionid"].astype(str).str.strip().any():
        df = df.drop_duplicates(subset="prestacionid")
    df["ingreso_dt"] = _parse_fecha(df["fechaingreso"]).dt.normalize()
    df["egreso_dt"]  = _parse_fecha(df["fechaegreso"]).dt.normalize()
    df["dni_clean"]  = df["numero_documento"].fillna("").astype(str).str.strip()
    df = df[
        (df["dni_clean"] != "")
        & (df["dni_clean"].str.lower() != "nan")
        & (df["ingreso_dt"].notna())
    ].copy()
    return df[["dni_clean", "ingreso_dt", "egreso_dt"]]


# ══════════════════════════════════════════════════════════════
#  FUNCION PRINCIPAL: generar_informe
# ══════════════════════════════════════════════════════════════

def generar_informe(
    input_agendas: Path | None = DEFAULT_INPUT_AGENDAS,
    input_fuera_agenda: Path | None = DEFAULT_INPUT_FUERA_AGENDA,
    input_internacion: Path | None = DEFAULT_INPUT_INTERNACION,
    input_imagenes: Path | None = DEFAULT_INPUT_IMAGENES,
    mapeo_file: Path | None = DEFAULT_MAPEO_FILE,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    log: LogFn = print,
    anio: int | None = None,
) -> Path | None:
    """
    1. Lee agendas, fuera de agenda e Intranet (imagenes) del año indicado.
    2. Filtra prestaciones de diagnostico por imagen y descarta turnos sin paciente.
    3. Asigna grupo de procedimiento segun el archivo de mapeo.
    4. Marca prestaciones a pacientes internados (cruce con internacion Andes).
    5. Inyecta los datos en template.html y genera el panel HTML.
    """
    anio = anio or datetime.now().year

    log("=" * 60)
    log(f"  PANEL DE IMÁGENES — {anio}")
    log("=" * 60)
    log(f"  Agendas        : {input_agendas}")
    log(f"  Fuera de agenda: {input_fuera_agenda}")
    log(f"  Internación    : {input_internacion}")
    log(f"  Imágenes       : {input_imagenes}")
    log(f"  Mapeo          : {mapeo_file}")
    log(f"  Carpeta destino: {output_path}")

    if not TEMPLATE_PATH.exists():
        log(f"  [ERROR] No se encuentra la plantilla HTML en: {TEMPLATE_PATH}")
        return None

    # ── Mapeo ────────────────────────────────────────────────
    log("\n--- Mapeo de grupos ---")
    dict_grupos = _cargar_mapeo(mapeo_file, log)

    # ── Lectura ──────────────────────────────────────────────
    log("\n--- Lectura de archivos ---")
    df_ag  = _cargar_agendas(input_agendas, anio, log)
    df_fu  = _cargar_fuera_agenda(input_fuera_agenda, anio, log)
    df_im  = _cargar_intranet(input_imagenes, anio, log)
    df_int = _cargar_internacion(input_internacion, log)

    log(f"\n  Registros {anio}: agenda={len(df_ag):,} | fuera agenda={len(df_fu):,} "
        f"| Intranet={len(df_im):,} | internaciones={len(df_int):,}")

    # ── Consolidacion y filtrado ─────────────────────────────
    log("\n--- Consolidación y filtrado ---")
    frames = [d for d in (df_ag, df_fu, df_im) if not d.empty]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNAS_BASE)
    log(f"  Total filas antes de limpiar: {len(df):,}")

    dni_vacio = (
        df["dni"].fillna("").astype(str).str.strip().str.lower()
        .isin(["", "nan", "none", "null", "(sin dato)"])
    )
    df = df[~dni_vacio].copy().reset_index(drop=True)
    log(f"  Total filas sin turnos vacíos: {len(df):,}")

    df["tipoprestacion_norm"] = df["tipoprestacion"].apply(_normalizar)
    mask = df["tipoprestacion_norm"].str.contains(PATRON_IMAGENES, na=False)
    df_img = df[mask].copy().drop_duplicates().reset_index(drop=True)
    log(f"  Prestaciones de imagen finales: {len(df_img):,}")

    if df_img.empty:
        log(f"  [AVISO] No se encontraron prestaciones de imagen para {anio}.")
        periodo_analizado = "Sin datos disponibles"
    else:
        min_fecha = df_img["fechaconsulta"].min()
        max_fecha = df_img["fechaconsulta"].max()
        periodo_analizado = f"{min_fecha.strftime('%d/%m/%Y')} al {max_fecha.strftime('%d/%m/%Y')}"
    log(f"  Período analizado: {periodo_analizado}")

    registros_lista: list[dict] = []

    if not df_img.empty:
        df_img["localidad_clean"] = df_img["localidad"].apply(_clean_localidad)
        edad_procesada = df_img.apply(_procesar_edad, axis=1)
        df_img["edad_clean"] = [x[0] for x in edad_procesada]
        df_img["edad_rango"] = [x[1] for x in edad_procesada]
        df_img["dni_clean"]  = df_img["dni"].fillna("").astype(str).str.strip()

        # Grupo de procedimiento
        df_img["tipoprestacion_clean"] = df_img["tipoprestacion"].fillna("").astype(str).str.strip()
        df_img["grupo"] = df_img["tipoprestacion_clean"].map(dict_grupos).fillna("(Sin grupo)")
        df_img.loc[df_img["grupo"] == "", "grupo"] = "(Sin grupo)"
        sin_grupo = int((df_img["grupo"] == "(Sin grupo)").sum())
        if sin_grupo:
            log(f"  [AVISO] {sin_grupo:,} prestaciones sin grupo asignado en el mapeo")

        # ── Pacientes internados ─────────────────────────────
        log("\n--- Cruce con internación ---")
        df_img["internado"] = 0
        if not df_int.empty:
            df_img["fecha_norm"] = df_img["fechaconsulta"].dt.normalize()
            df_img["temp_index"] = df_img.index
            merged = pd.merge(
                df_img[["temp_index", "dni_clean", "fecha_norm"]],
                df_int[["dni_clean", "ingreso_dt", "egreso_dt"]],
                on="dni_clean",
                how="inner",
            )
            cond_despues_ingreso = merged["fecha_norm"] >= merged["ingreso_dt"]
            cond_antes_egreso = (merged["fecha_norm"] <= merged["egreso_dt"]) | merged["egreso_dt"].isna()
            indices_internados = merged[cond_despues_ingreso & cond_antes_egreso]["temp_index"].unique()
            df_img.loc[df_img["temp_index"].isin(indices_internados), "internado"] = 1
            df_img.drop(columns=["temp_index", "fecha_norm"], inplace=True)
        log(f"  Prestaciones a pacientes internados: {int(df_img['internado'].sum()):,}")

        # ── Dataset compacto para el HTML ────────────────────
        df_img["mes"] = df_img["fechaconsulta"].dt.month
        df_img["fecha_str"] = df_img["fechaconsulta"].dt.strftime("%Y-%m-%d")
        df_json = df_img[[
            "origen", "mes", "tipoprestacion", "grupo", "fecha_str",
            "localidad_clean", "edad_clean", "edad_rango", "dni_clean", "internado",
        ]].copy()
        df_json.columns = ["o", "m", "t", "g", "f", "l", "e", "er", "d", "i"]
        df_json["t"] = df_json["t"].fillna("")
        registros_lista = df_json.to_dict(orient="records")

    # ── Generacion HTML ──────────────────────────────────────
    log("\n--- Generación HTML ---")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = (
        template
        .replace("__ANIO__", str(anio))
        .replace("__PERIODO_ANALIZADO__", periodo_analizado)
        .replace("__REGISTROS_JSON__", json.dumps(registros_lista, ensure_ascii=False))
    )

    output_path.mkdir(parents=True, exist_ok=True)
    html_salida = output_path / HTML_OUTPUT_NAME
    try:
        html_salida.write_text(html, encoding="utf-8")
    except PermissionError:
        log(f"  [ERROR] No se pudo escribir {html_salida}. ¿Está abierto en otro programa?")
        return None

    log(f"\n  [OK] HTML generado: {html_salida}")
    log("=" * 60)
    return html_salida
