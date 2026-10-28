"""
report.py — Informe de Quirófano
================================
Logica de procesamiento de datos para el Informe de Quirófano.
La plantilla visual reside en `template.html`.
La UI (app/ui/pages/informes/quirofano.py) solo llama a generar_informe().

Adaptado desde "scripts para reportes/quirofano" (procesamiento.py + generar_reporte.py).

Fuentes de datos (carpetas con CSV ya normalizados, separador ';'):
  - Programadas (admin)  : <carpeta>\\*_normalizado.csv        (uno por mes)
  - Urgencias (admin)    : <carpeta>\\urgencias_historicas_normalizado.csv
  - Circulante (limpia)  : <carpeta>\\base_circulante_normalizado.csv
  - Calendario SE        : archivo calendario_se.csv
Salida: <carpeta de salida>\\Informe Quirofano.html
"""
import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES Y RUTAS
# ══════════════════════════════════════════════════════════════

MODULE_DIR    = Path(__file__).resolve().parent
TEMPLATE_PATH = MODULE_DIR / "template.html"
ASSETS_DIR    = MODULE_DIR / "assets"
FONDO_PATH    = ASSETS_DIR / "fondo_hpn.png"
LOGO_PATH     = ASSETS_DIR / "logo_v_1.png"

# Rutas a las bases (se pueden cambiar desde la UI).
DEFAULT_INPUT_PROGRAMADAS = Path(r"C:\02_HPN\01_Base\quirofano\Programadas")   # carpeta con *_normalizado.csv
DEFAULT_INPUT_URGENCIAS   = Path(r"C:\02_HPN\01_Base\quirofano\Urgencias")     # carpeta con urgencias_historicas_normalizado.csv
DEFAULT_INPUT_CIRCULANTE  = Path(r"C:\02_HPN\01_Base\quirofano\Circulante")    # carpeta con base_circulante_normalizado.csv
DEFAULT_CALENDARIO_FILE   = Path(r"C:\02_HPN\01_Base\tablas_relacionales\calendario_se.csv")

DEFAULT_OUTPUT_PATH = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\informes")
HTML_OUTPUT_NAME    = "Informe Quirofano.html"

PATRON_PROGRAMADAS = "*_normalizado.csv"
ARCHIVO_URGENCIAS  = "urgencias_historicas_normalizado.csv"
ARCHIVO_CIRCULANTE = "base_circulante_normalizado.csv"

MESES = {
    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
    "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
    "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
}

SITUACIONES = ["Internado", "Ambulatorio", "Guardia Adultos", "Guardia Pediatría",
               "Hospital de Día", "Otros"]

GRUPOS_EDAD = [
    "Recién Nacido", "Menor a 1 año", "1-4", "5-9", "10-14", "15-19",
    "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", ">= 90",
]

QUIROFANOS = ["1", "2", "3", "4", "5", "Otros"]

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  AUXILIARES GENERALES
# ══════════════════════════════════════════════════════════════

def _nombre_mes(mes_anio: str) -> str:
    try:
        y, m = mes_anio.split("-")
        return f"{MESES.get(m, m)} {y}"
    except Exception:
        return mes_anio


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 1) if total > 0 else 0


def _conteo_cirugia(df: pd.DataFrame) -> tuple[int, int, int]:
    """(programadas, urgencias, total) de un DataFrame."""
    return (
        int((df["cirugia"] == "Programada").sum()),
        int((df["cirugia"] == "Urgencia").sum()),
        len(df),
    )


def _fila_pct(df_sub: pd.DataFrame, total_p: int, total_u: int, total_g: int) -> dict:
    """Conteos y % de un subconjunto respecto de los totales (prog / urg / general)."""
    p_n, u_n, _ = _conteo_cirugia(df_sub)
    t_n = p_n + u_n
    return {
        "prog_n": p_n, "prog_pct": _pct(p_n, total_p),
        "urg_n": u_n, "urg_pct": _pct(u_n, total_u),
        "total_n": t_n, "total_pct": _pct(t_n, total_g),
    }


def _totales(df: pd.DataFrame) -> dict:
    p, u, g = _conteo_cirugia(df)
    return {"prog_n": p, "urg_n": u, "total_n": g}


def _por_mes(fn, df: pd.DataFrame) -> dict:
    """Aplica fn al total y a cada mes: {"Total": ..., "months": {mes: ...}}."""
    return {
        "Total": fn(df),
        "months": {m: fn(df[df["mes_año"] == m]) for m in sorted(df["mes_año"].unique())},
    }


def _imagen_base64(path: Path) -> str:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:image/{path.suffix.lower().lstrip('.')};base64,{encoded}"
    except OSError:
        return ""


# ══════════════════════════════════════════════════════════════
#  NORMALIZACIONES
# ══════════════════════════════════════════════════════════════

def _limpiar_suspension(reason) -> str:
    if not isinstance(reason, str):
        return "No especificado"
    if reason.lower().startswith("si"):
        return "Realizada"
    reason = reason.replace("Suspensión por ", "").replace("Suspension por ", "")
    if "decisión Médica" in reason or "decisión Mdica" in reason:
        return "Decisión Médica (condición paciente)"
    if "material defectuoso" in reason:
        return "Material defectuoso / Falla esterilización"
    if "falta de material" in reason:
        return "Falta de material"
    return reason


def _normalizar_servicio(s: str, desglosar: bool = False) -> str:
    """
    Agrupa el servicio en categorias principales.
    desglosar=True separa subespecialidades de Cirugía General (versión v2).
    """
    if desglosar:
        low = s.lower()
        if "vascular" in low:
            return "Cirugía General (Vascular Periférico)"
        if "urologia" in low or "urología" in low:
            return "Cirugía General (Urología)"
        if "mohs" in low:
            return "Cirugía General (MOHS)"
        if "hepatobilio" in low:
            return "Cirugía General (Hepatobiliopancreática)"
        if "cabeza y cuello" in low:
            return "Cirugía General (Cabeza y Cuello - Tórax)"

    s = re.sub(r"\(.*?\)", "", s).strip()
    low = s.lower()

    if "cardiocirug" in low or "cardiolog" in low:
        return "Cardiología"
    if "cirug" in low and "general" in low:
        return "Cirugía General"
    if "cirug" in low and "pedi" in low:
        return "Cirugía Pediátrica"
    if "traumato" in low:
        return "Traumatología"
    if "neurociru" in low:
        return "Neurocirugía"
    if "gineco" in low:
        return "Ginecología"
    if "obstetri" in low:
        return "Obstetricia"
    if "plástic" in low or "plastic" in low:
        return "Cirugía Plástica"
    if "otorrino" in low or "orl" in low:
        return "Otorrinolaringología"
    if "oftalmo" in low:
        return "Oftalmología"
    if "odonto" in low:
        return "Odontología"
    if "trasplante" in low or "ablacion" in low or "ablaci" in low:
        return "Trasplante / Ablación"
    return "Otros"


def _servicios_de_fila(val, desglosar: bool = True) -> list[str]:
    """Lista de servicios normalizados (sin repetir) de una celda multi-servicio."""
    if not isinstance(val, str) or len(val.strip()) < 3:
        return []
    servicios: list[str] = []
    for parte in (p.strip() for p in val.split(",")):
        if len(parte) < 3 or parte.lower().startswith("paciente"):
            continue
        norm = _normalizar_servicio(parte, desglosar)
        if norm not in servicios:
            servicios.append(norm)
    return servicios


def _normalizar_situacion(s) -> str:
    if not isinstance(s, str):
        return "Otros"
    low = s.lower()
    if "internado" in low:
        return "Internado"
    if "ambulatorio" in low:
        return "Ambulatorio"
    if "guardia" in low and "adult" in low:
        return "Guardia Adultos"
    if "guardia" in low and ("pediat" in low or "pediá" in low):
        return "Guardia Pediatría"
    if "hospital de día" in low or "dia" in low:
        return "Hospital de Día"
    return "Otros"


def _normalizar_quirofano(val) -> str:
    if pd.isna(val):
        return "Otros"
    txt = str(val).strip()
    if txt in ("1", "2", "3", "4", "5"):
        return txt
    try:
        num = float(txt)
        if num.is_integer() and str(int(num)) in ("1", "2", "3", "4", "5"):
            return str(int(num))
    except ValueError:
        pass
    if "2°" in txt and "piso" in txt.lower():
        return "5"
    return "Otros"


# ══════════════════════════════════════════════════════════════
#  PARSEO DE HORAS
# ══════════════════════════════════════════════════════════════

def _parse_hora(val) -> tuple[int, int] | None:
    """Devuelve (hora, minuto) de textos tipo 'HH:MM', 'HH:MM am/pm' o con fecha."""
    if not isinstance(val, str) or len(val.strip()) < 4:
        return None
    try:
        if "/" in val and ":" in val:
            val = val.split(" ")[-1]
        val = val.lower().replace(".", "")
        is_pm, is_am = "pm" in val, "am" in val
        partes = val.replace("am", "").replace("pm", "").strip().split(":")
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
        if is_pm and h < 12:
            h += 12
        if is_am and h == 12:
            h = 0
        return h, m
    except Exception:
        return None


def _a_minutos(val) -> int | None:
    hm = _parse_hora(val)
    return hm[0] * 60 + hm[1] if hm else None


def _hora_del_dia(val) -> int | None:
    hm = _parse_hora(val)
    return hm[0] if hm and 0 <= hm[0] <= 23 else None


# ══════════════════════════════════════════════════════════════
#  ESTADISTICAS
# ══════════════════════════════════════════════════════════════

def _stats_suspension(df: pd.DataFrame) -> dict:
    total_p, total_u, total_g = _conteo_cirugia(df)
    reales = df[df["outcome"] == "Realizada"]
    stats = {
        "realizadas": _fila_pct(reales, total_p, total_u, total_g),
        "reasons": {},
        "total": {"prog_n": total_p, "urg_n": total_u, "total_n": total_g},
    }
    for motivo in df[df["outcome"] != "Realizada"]["outcome"].unique():
        stats["reasons"][motivo] = _fila_pct(
            df[df["outcome"] == motivo], total_p, total_u, total_g
        )
    return stats


def _por_servicio(fn, df: pd.DataFrame) -> dict:
    """{"Todos": fn(df), <servicio>: fn(df de ese servicio), ...}"""
    filas_por_servicio: dict[str, list] = {}
    for _, row in df.iterrows():
        for s in _servicios_de_fila(row.get("servicio_que_realiza_la_practica")):
            filas_por_servicio.setdefault(s, []).append(row)
    res = {"Todos": fn(df)}
    for s, filas in filas_por_servicio.items():
        res[s] = fn(pd.DataFrame(filas))
    return res


def _stats_suspension_v2(df: pd.DataFrame) -> dict:
    return _por_servicio(_stats_suspension, df)


def _stats_tiempos(df: pd.DataFrame) -> dict:
    metricas = [
        ("Espera del paciente", "hs_ingreso_paciente_a_quirofano",
         "hs_ingreso_del_paciente_al_area_quirurgica"),
        ("Tiempo de cirugía", "fin_de_cirugia", "comienzo_cirugia_incision"),
        ("Duración procedimiento", "salida_de_quirofano", "hs_ingreso_paciente_a_quirofano"),
    ]
    diffs_por_metrica: dict[str, list[int]] = {}
    validas = 0

    for _, row in df.iterrows():
        fila_ok = True
        valores = {}
        for label, col_f, col_i in metricas:
            m_f, m_i = _a_minutos(row.get(col_f)), _a_minutos(row.get(col_i))
            valor = None
            if m_f is not None and m_i is not None:
                diff = m_f - m_i
                if diff < 0:
                    diff += 1440
                rango = (2, 300) if label == "Espera del paciente" else (10, 720)
                if rango[0] <= diff <= rango[1]:
                    valor = diff
            if valor is None:
                fila_ok = False
            else:
                valores[label] = valor
        if fila_ok:
            validas += 1
            for label, valor in valores.items():
                diffs_por_metrica.setdefault(label, []).append(valor)

    stats = {}
    for label, _, _ in metricas:
        diffs = diffs_por_metrica.get(label)
        if diffs:
            stats[label] = {
                "avg": int(round(sum(diffs) / len(diffs), 0)),
                "min": min(diffs), "max": max(diffs), "n": len(diffs),
            }
        else:
            stats[label] = {"avg": 0, "min": 0, "max": 0, "n": 0}

    return {
        "stats": stats,
        "quality": {"valid_n": validas, "invalid_n": max(0, len(df) - validas)},
    }


def _stats_tiempos_v2(df: pd.DataFrame) -> dict:
    return _por_servicio(_stats_tiempos, df)


def _stats_horas(df: pd.DataFrame) -> dict:
    conteo = {f"{h:02d}:00": 0 for h in range(24)}
    for val in df["hs_ingreso_paciente_a_quirofano"]:
        h = _hora_del_dia(val)
        if h is not None:
            conteo[f"{h:02d}:00"] += 1
    return conteo


def _stats_situacion(df: pd.DataFrame) -> dict:
    total_p, total_u, total_g = _conteo_cirugia(df)
    norm = df["situacion_del_paciente"].apply(_normalizar_situacion)
    return {
        "data": {s: _fila_pct(df[norm == s], total_p, total_u, total_g) for s in SITUACIONES},
        "total": {"prog_n": total_p, "urg_n": total_u, "total_n": total_g},
    }


def _stats_metodo(df: pd.DataFrame) -> dict:
    total_p, total_u, total_g = _conteo_cirugia(df)
    tipo = df["tipo_de_cirugia"].fillna("Suspendidas")
    return {
        "data": {m: _fila_pct(df[tipo == m], total_p, total_u, total_g) for m in tipo.unique()},
        "total": {"prog_n": total_p, "urg_n": total_u, "total_n": total_g},
    }


def _stats_quirofano(df: pd.DataFrame) -> dict:
    total_p, total_u, total_g = _conteo_cirugia(df)
    norm = df["quirofano"].apply(_normalizar_quirofano)
    return {
        "data": {q: _fila_pct(df[norm == q], total_p, total_u, total_g) for q in QUIROFANOS},
        "total": {"prog_n": total_p, "urg_n": total_u, "total_n": total_g},
    }


def _grupo_edad(edad, tipo_edad) -> str | None:
    tipo = str(tipo_edad).lower()
    try:
        val = float(edad)
    except (TypeError, ValueError):
        return None
    if "hs" in tipo or "dia" in tipo or "día" in tipo:
        return "Recién Nacido"
    if "mes" in tipo or val < 1:
        return "Menor a 1 año"
    for tope, grupo in [(4, "1-4"), (9, "5-9"), (14, "10-14"), (19, "15-19"),
                        (29, "20-29"), (39, "30-39"), (49, "40-49"), (59, "50-59"),
                        (69, "60-69"), (79, "70-79"), (89, "80-89")]:
        if val <= tope:
            return grupo
    return ">= 90"


def _stats_demografia(df: pd.DataFrame) -> dict:
    res = {g: {"Masculino": 0, "Femenino": 0} for g in GRUPOS_EDAD}
    for _, row in df.iterrows():
        sexo = row.get("sexo", "")
        if sexo not in ("Masculino", "Femenino"):
            continue
        grupo = _grupo_edad(row.get("edad", 0), row.get("tipo_edad", ""))
        if grupo:
            res[grupo][sexo] += 1
    return res


def _stats_servicios(df: pd.DataFrame, desglosar: bool) -> dict:
    """Conteo por servicio: 'indiv' (unico servicio) vs 'comp' (combinado)."""
    res: dict[str, dict] = {}
    for val in df["servicio_que_realiza_la_practica"]:
        servicios = _servicios_de_fila(val, desglosar)
        if not servicios:
            continue
        clave = "indiv" if len(servicios) == 1 else "comp"
        for s in servicios:
            res.setdefault(s, {"indiv": 0, "comp": 0})[clave] += 1
    return res


# ══════════════════════════════════════════════════════════════
#  CARGA DE DATOS
# ══════════════════════════════════════════════════════════════

def _leer_csv(archivo: Path) -> pd.DataFrame:
    df = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _agregar_calendario(df: pd.DataFrame, df_cal: pd.DataFrame) -> pd.DataFrame:
    df["fecha_solo"] = df["fecha_dt"].dt.normalize()
    return df.merge(df_cal.rename(columns={"fecha_dt": "fecha_solo"}), on="fecha_solo", how="left")


def _cargar_calendario(archivo: Path) -> pd.DataFrame:
    df = pd.read_csv(archivo, sep=";", encoding="latin-1", dtype=str)
    df.columns = ["Fecha", "Dia", "Semana", "Mes", "Año", "OrdenDia", "OrdenMes", "Año_se"]
    df["fecha_dt"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    return df[["fecha_dt", "Semana", "Año_se"]].drop_duplicates()


def _cargar_programadas(carpeta: Path, df_cal: pd.DataFrame, log: LogFn) -> pd.DataFrame:
    """Base administrativa de cirugias programadas (varios archivos mensuales)."""
    listas = []
    archivos = sorted(carpeta.glob(PATRON_PROGRAMADAS))
    log(f"  Programadas: {len(archivos)} archivos {PATRON_PROGRAMADAS}")
    for f in archivos:
        try:
            df = pd.read_csv(f, sep=";", encoding="utf-8-sig", dtype=str)
            cols = [str(c).strip().lower() for c in df.columns]
            # Evita duplicados con la 1ra columna, que se fuerza a 'quirofano'
            cols = [c if c not in ("quirofano", "n_quirofano") else f"old_col_{i}"
                    for i, c in enumerate(cols)]
            if cols:
                cols[0] = "quirofano"
            df.columns = cols

            df = df[~df["quirofano"].fillna("").str.contains("endoscopia", case=False)]

            if "fecha" not in df.columns:
                log(f"  [AVISO] {f.name}: sin columna 'fecha', se omite")
                continue
            df["fecha_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
            if df["fecha_dt"].isna().any():
                # Fecha faltante: se asume el 1ro del mes indicado en el nombre (AAAA_MM_...)
                partes = f.name.split("_")
                if len(partes) >= 2 and partes[0].isdigit() and partes[1].isdigit():
                    df.loc[df["fecha_dt"].isna(), "fecha_dt"] = pd.Timestamp(
                        int(partes[0]), int(partes[1]), 1
                    )
            if "dni" not in df.columns:
                df["dni"] = pd.NA
            listas.append(df[["fecha_dt", "dni"]])
        except Exception as e:
            log(f"  [AVISO] No se pudo leer {f.name}: {e}")

    if listas:
        df_prog = pd.concat(listas, ignore_index=True)
    else:
        df_prog = pd.DataFrame({
            "fecha_dt": pd.Series(dtype="datetime64[ns]"),
            "dni": pd.Series(dtype=object),
        })
    return _agregar_calendario(df_prog, df_cal)


def _cargar_urgencias(carpeta: Path, df_cal: pd.DataFrame) -> pd.DataFrame:
    """Base administrativa de cirugias de urgencia."""
    df = _leer_csv(carpeta / ARCHIVO_URGENCIAS)
    if "servicio_que_opera" in df.columns:
        df = df[~df["servicio_que_opera"].fillna("").str.contains("endoscopia", case=False)]
    col = next((c for c in df.columns if "marca" in c and "temporal" in c), None)
    if col:
        df["fecha_dt"] = pd.to_datetime(
            df[col].astype(str).str.split(" ").str[0], format="%Y/%m/%d", errors="coerce"
        )
    else:
        df["fecha_dt"] = pd.NaT
    return _agregar_calendario(df, df_cal)


def _cargar_circulante(carpeta: Path, df_cal: pd.DataFrame) -> pd.DataFrame:
    """Base limpia del quirofano circulante."""
    df = _leer_csv(carpeta / ARCHIVO_CIRCULANTE)
    col = next((c for c in df.columns if "marca" in c and "temporal" in c), None)
    if col:
        df["fecha_dt"] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    else:
        df["fecha_dt"] = pd.NaT
    return _agregar_calendario(df, df_cal)


# ══════════════════════════════════════════════════════════════
#  PROCESAMIENTO
# ══════════════════════════════════════════════════════════════

def _procesar_datos(
    input_programadas: Path,
    input_urgencias: Path,
    input_circulante: Path,
    calendario_file: Path,
    anio: int,
    log: LogFn,
) -> dict:
    anio_s = str(anio)

    log("\n--- Lectura de archivos ---")
    df_cal = _cargar_calendario(calendario_file)
    df_prog = _cargar_programadas(input_programadas, df_cal, log)
    df_urg = _cargar_urgencias(input_urgencias, df_cal)
    df_circ = _cargar_circulante(input_circulante, df_cal)
    log(f"  Programadas (admin): {len(df_prog):,} registros")
    log(f"  Urgencias (admin)  : {len(df_urg):,} registros")
    log(f"  Circulante (limpia): {len(df_circ):,} registros")

    # ── Filtros: año y mes vencido ───────────────────────────
    log("\n--- Filtros ---")
    primer_dia_mes_actual = pd.Timestamp.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    def _filtrar(df: pd.DataFrame) -> pd.DataFrame:
        df["mes_año"] = df["fecha_dt"].dt.strftime("%Y-%m")
        df = df[df["mes_año"].str.startswith(anio_s, na=False)]
        return df[df["fecha_dt"] < primer_dia_mes_actual].copy()

    df_prog, df_urg, df_circ = _filtrar(df_prog), _filtrar(df_urg), _filtrar(df_circ)
    log(f"  Año {anio} hasta el último día del mes anterior:")
    log(f"    Programadas {len(df_prog):,} | Urgencias {len(df_urg):,} | Circulante {len(df_circ):,}")

    # ── Cobertura de carga (admin vs circulante) ─────────────
    admin_prog = df_prog.groupby("mes_año").size()
    admin_urg = df_urg.groupby("mes_año").size()
    clean_prog = df_circ[df_circ["cirugia"] == "Programada"].groupby("mes_año").size()
    clean_urg = df_circ[df_circ["cirugia"] == "Urgencia"].groupby("mes_año").size()

    meses = sorted(set(admin_prog.index) | set(admin_urg.index)
                   | set(clean_prog.index) | set(clean_urg.index))
    meses = [m for m in meses if m and str(m).startswith(anio_s)]

    def _carga(a: int, c: int) -> dict:
        return {"total": a, "cargadas": c, "pct": _pct(c, a)}

    report = {"months": {}}
    for mes in meses:
        report["months"][mes] = {
            "label": _nombre_mes(mes),
            "prog": _carga(int(admin_prog.get(mes, 0)), int(clean_prog.get(mes, 0))),
            "urg": _carga(int(admin_urg.get(mes, 0)), int(clean_urg.get(mes, 0))),
        }
    report["Total"] = {
        "label": f"Total {anio}",
        "prog": _carga(int(admin_prog.sum()), int(clean_prog.sum())),
        "urg": _carga(int(admin_urg.sum()), int(clean_urg.sum())),
    }

    # ── Frecuencia programada vs urgencia ────────────────────
    def _frecuencia(df: pd.DataFrame) -> dict:
        p, u, t = _conteo_cirugia(df)
        t = p + u
        return {"prog_n": p, "prog_pct": _pct(p, t), "urg_n": u, "urg_pct": _pct(u, t), "total_n": t}

    stats = {anio_s: {"months": {}, "total": _frecuencia(df_circ)}}
    for m in sorted(df_circ["mes_año"].unique()):
        stats[anio_s]["months"][m.split("-")[1]] = _frecuencia(df_circ[df_circ["mes_año"] == m])

    # ── Resto de bloques ─────────────────────────────────────
    log("\n--- Cálculo de estadísticas ---")
    df_circ["outcome"] = df_circ["cirugia_realizada"].apply(_limpiar_suspension)

    report["stats"] = stats
    report["suspension"] = _por_mes(_stats_suspension_v2, df_circ)
    report["services"] = _por_mes(lambda d: _stats_servicios(d, False), df_circ)
    report["services_v2"] = _por_mes(lambda d: _stats_servicios(d, True), df_circ)
    report["methods"] = _por_mes(_stats_metodo, df_circ)
    report["times"] = _por_mes(_stats_tiempos_v2, df_circ)
    report["hourly"] = _por_mes(_stats_horas, df_circ)
    report["situations"] = _por_mes(_stats_situacion, df_circ)
    report["quirofanos"] = _por_mes(_stats_quirofano, df_circ)
    report["demographics"] = _por_mes(_stats_demografia, df_circ)

    # Último mes (para el encabezado)
    if len(df_circ) > 0:
        ultimo = sorted(df_circ["mes_año"].unique())[-1]
        report["latest_month"] = report["months"][ultimo]["label"]
    else:
        report["latest_month"] = "N/A"
    log(f"  Último mes con datos: {report['latest_month']}")
    return report


# ══════════════════════════════════════════════════════════════
#  FUNCION PRINCIPAL
# ══════════════════════════════════════════════════════════════

def generar_informe(
    input_programadas: Path | None = None,
    input_urgencias: Path | None = None,
    input_circulante: Path | None = None,
    calendario_file: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_PATH,
    log: LogFn = print,
    anio: int | None = None,
) -> Path | None:
    """Procesa las bases de quirofano y genera el HTML del informe."""
    anio = anio or datetime.now().year

    log("=" * 60)
    log("  INFORME QUIRÓFANO")
    log("=" * 60)
    log(f"  Año                : {anio}")
    log(f"  Programadas        : {input_programadas}")
    log(f"  Urgencias          : {input_urgencias}")
    log(f"  Circulante         : {input_circulante}")
    log(f"  Calendario SE      : {calendario_file}")
    log(f"  Carpeta destino    : {output_dir}")

    # ── Validaciones ─────────────────────────────────────────
    requeridos = [
        ("carpeta de Programadas", input_programadas, "dir"),
        ("carpeta de Urgencias", input_urgencias, "dir"),
        ("carpeta de Circulante", input_circulante, "dir"),
        ("archivo de Calendario SE", calendario_file, "file"),
    ]
    for nombre, ruta, tipo in requeridos:
        if not ruta or str(ruta) in ("", "."):
            log(f"  [ERROR] Falta definir la {nombre}.")
            return None
        ok = Path(ruta).is_dir() if tipo == "dir" else Path(ruta).is_file()
        if not ok:
            log(f"  [ERROR] No existe la {nombre}: {ruta}")
            return None
    for nombre, ruta, archivo in [
        ("Urgencias", input_urgencias, ARCHIVO_URGENCIAS),
        ("Circulante", input_circulante, ARCHIVO_CIRCULANTE),
    ]:
        if not (Path(ruta) / archivo).is_file():
            log(f"  [ERROR] No se encontró {archivo} en la carpeta de {nombre}: {ruta}")
            return None

    data = _procesar_datos(
        Path(input_programadas), Path(input_urgencias), Path(input_circulante),
        Path(calendario_file), anio, log,
    )

    # ── Generacion HTML ──────────────────────────────────────
    log("\n--- Generación HTML ---")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = (
        template
        .replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
        .replace("__FONDO_BASE64__", _imagen_base64(FONDO_PATH))
        .replace("__LOGO_BASE64__", _imagen_base64(LOGO_PATH))
        .replace("__ANIO__", str(anio))
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_salida = output_dir / HTML_OUTPUT_NAME
    try:
        html_salida.write_text(html, encoding="utf-8")
    except PermissionError:
        log(f"  [ERROR] No se pudo escribir {html_salida}. ¿Está abierto en otro programa?")
        return None

    log(f"\n  [OK] HTML generado: {html_salida}")
    log("=" * 60)
    return html_salida
