"""
report.py — Informe de Eventos Obstétricos
===========================================
Lógica de consolidación y procesamiento de datos para el informe de Eventos Obstétricos.
La plantilla visual reside en `template.html`.

Fuente de datos: CSVs en C:\\02_HPN\\01_Base\\eventos_obstetricos
Salida: C:\\03_Apps\\Sala-Situacion-APP\\Outputs\\informes\\eventos_obstetricos.html
"""
from pathlib import Path
from datetime import datetime
from typing import Callable
import json
import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES Y RUTAS
# ══════════════════════════════════════════════════════════════

MODULE_DIR          = Path(__file__).resolve().parent
TEMPLATE_PATH       = MODULE_DIR / "template.html"

DEFAULT_INPUT_PATH  = Path(r"C:\02_HPN\01_Base\eventos_obstetricos")
DEFAULT_OUTPUT_PATH = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\informes")
HTML_OUTPUT_NAME    = "eventos_obstetricos.html"

LogFn = Callable[[str], None]

NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


# ══════════════════════════════════════════════════════════════
#  AUXILIARES
# ══════════════════════════════════════════════════════════════

def _clasificar_condicion(val) -> str:
    """Clasifica la columna condnacrn en Nacidos Vivos, Defunciones Fetales o Sin dato."""
    if pd.isna(val):
        return "Sin dato"
    v = str(val).strip().lower()
    if "vivo" in v:
        return "Nacidos Vivos"
    elif "def" in v or "fetal" in v:
        return "Defunciones Fetales"
    return "Sin dato"


def _clasificar_categoria_eg(eg) -> str | None:
    """Clasifica la edad gestacional según los rangos perinatales estándar."""
    if pd.isna(eg):
        return None
    if eg >= 37:
        return "Termino"
    elif 32 <= eg <= 36:
        return "32 a 36 semanas"
    elif 28 <= eg <= 31:
        return "28 a 31 semanas"
    elif eg < 28:
        return "<28 semanas"
    return None


def _clasificar_categoria_peso(peso) -> str | None:
    """Clasifica el peso al nacer en gramos según las categorías de referencia."""
    if pd.isna(peso):
        return None
    if peso < 1500:
        return "muy bajo peso <1500"
    elif 1500 <= peso <= 2499:
        return "bajo peso 1500-2499 g"
    elif 2500 <= peso <= 3999:
        return "peso adecuado 2500-3999 g"
    elif peso >= 4000:
        return "sobre peso ≥4000 g"
    return None


# ══════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL: generar_informe
# ══════════════════════════════════════════════════════════════

def generar_informe(
    input_path: Path = DEFAULT_INPUT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    log: LogFn = print,
) -> Path | None:
    """
    Consolida los CSVs de eventos obstétricos:
    1. Deduplica según idinternacion.
    2. Mira fechaegreso para calcular el año y mes (formato ej: 4/1/2022).
    3. Desglosa por condnacrn (Nacidos Vivos y Defunciones Fetales).
    4. Analiza edadgestacional (< 32 semanas = prematuros, y categorías apiladas).
    5. Carga template.html, inyecta los datos calculados y genera el archivo de salida.
    """
    log("=" * 60)
    log("  INFORME DE EVENTOS OBSTÉTRICOS")
    log("=" * 60)
    log(f"  Carpeta origen : {input_path}")
    log(f"  Carpeta destino: {output_path}")

    if not input_path.exists():
        log(f"  [ERROR] No existe la carpeta origen: {input_path}")
        return None

    if not TEMPLATE_PATH.exists():
        log(f"  [ERROR] No se encuentra la plantilla HTML en: {TEMPLATE_PATH}")
        return None

    archivos_csv = sorted(input_path.glob("*.csv"))
    if not archivos_csv:
        log(f"  [ERROR] No se encontraron archivos CSV en: {input_path}")
        return None

    log(f"\n--- Lectura de Archivos CSV ({len(archivos_csv)} encontrados) ---")
    dfs = []
    for archivo in archivos_csv:
        try:
            df_tmp = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False)
        except Exception:
            df_tmp = pd.read_csv(archivo, sep=";", encoding="latin1", dtype=str, low_memory=False)
        dfs.append(df_tmp)
        log(f"  [OK] {archivo.name} ({len(df_tmp):,} filas)")

    df_total = pd.concat(dfs, ignore_index=True)
    log(f"\nTotal filas brutas combinadas: {len(df_total):,}")

    for col_req in ["idinternacion", "fechaegreso", "condnacrn", "edadgestacional", "pesonacerrn"]:
        if col_req not in df_total.columns:
            log(f"  [ERROR] Columna requerida '{col_req}' no está presente en los archivos.")
            return None

    # 1. Deduplicación por idinternacion
    log("\n--- Deduplicación por idinternacion ---")
    duplicados_cant = int(df_total.duplicated(subset=["idinternacion"]).sum())
    df_dedup = df_total.drop_duplicates(subset=["idinternacion"]).copy()
    log(f"  Duplicados eliminados: {duplicados_cant:,}")
    log(f"  Filas restantes: {len(df_dedup):,}")

    # 2. Parseo de fechaegreso
    log("\n--- Procesamiento de Fechas de Egreso ---")
    fecha_clean = df_dedup["fechaegreso"].astype(str).str.strip()
    fechas_parsed = pd.to_datetime(
        fecha_clean,
        dayfirst=True,
        format="mixed",
        errors="coerce"
    )

    df_dedup["fechaegreso_parsed"] = fechas_parsed
    df_validas = df_dedup.dropna(subset=["fechaegreso_parsed"]).copy()
    df_validas["anio"] = df_validas["fechaegreso_parsed"].dt.year.astype(int)
    df_validas["mes_num"] = df_validas["fechaegreso_parsed"].dt.month.astype(int)

    total_validas = len(df_validas)
    if total_validas == 0:
        log("  [ERROR] No quedaron filas válidas con fechaegreso.")
        return None

    min_fecha = df_validas["fechaegreso_parsed"].min()
    max_fecha = df_validas["fechaegreso_parsed"].max()
    periodo_str = f"{min_fecha.strftime('%d/%m/%Y')} al {max_fecha.strftime('%d/%m/%Y')}"
    log(f"  Total partos válidos: {total_validas:,}")
    log(f"  Período cubierto: {periodo_str}")

    # 3. Clasificación de variables
    df_validas["cond_tipo"] = df_validas["condnacrn"].apply(_clasificar_condicion)

    # Conversión numérica de edadgestacional (< 32 semanas = prematuro)
    eg_num = pd.to_numeric(df_validas["edadgestacional"].astype(str).str.strip(), errors="coerce")
    eg_num = eg_num.apply(lambda x: 39.0 if x == 3900 else (x if x <= 50 else pd.NA))
    df_validas["eg_num"] = eg_num

    df_validas["es_prem_32"] = df_validas["eg_num"] < 32
    df_validas["es_nv"] = df_validas["cond_tipo"] == "Nacidos Vivos"
    df_validas["es_def"] = df_validas["cond_tipo"] == "Defunciones Fetales"
    df_validas["cat_eg"] = df_validas["eg_num"].apply(_clasificar_categoria_eg)

    # Conversión numérica y clasificación de pesonacerrn
    peso_num = pd.to_numeric(df_validas["pesonacerrn"].astype(str).str.strip(), errors="coerce")
    df_validas["peso_num"] = peso_num
    df_validas["cat_peso"] = df_validas["peso_num"].apply(_clasificar_categoria_peso)

    # ──────────────────────────────────────────────────────────
    #  BLOQUE 1: PARTOS GENERALES
    # ──────────────────────────────────────────────────────────
    tabla_conteo = df_validas.groupby(["anio", "cond_tipo"]).size().unstack(fill_value=0)
    for c in ["Nacidos Vivos", "Defunciones Fetales", "Sin dato"]:
        if c not in tabla_conteo.columns:
            tabla_conteo[c] = 0

    tabla_conteo["Total Partos"] = tabla_conteo.sum(axis=1)
    tabla_conteo = tabla_conteo.sort_index()

    # Identificar año en curso
    anio_actual = datetime.now().year
    if anio_actual in tabla_conteo.index:
        current_year = anio_actual
    else:
        current_year = int(tabla_conteo.index.max())

    row_curr = tabla_conteo.loc[current_year]
    curr_total = int(row_curr["Total Partos"])
    curr_vivos = int(row_curr["Nacidos Vivos"])
    curr_def = int(row_curr["Defunciones Fetales"])
    curr_vivos_pct = f"{(curr_vivos / curr_total * 100):.1f}" if curr_total > 0 else "0.0"
    curr_def_pct = f"{(curr_def / curr_total * 100):.1f}" if curr_total > 0 else "0.0"

    log(f"\n--- Métricas Año en Curso ({current_year}) ---")
    log(f"  Total Partos        : {curr_total:,}")
    log(f"  Nacidos Vivos       : {curr_vivos:,} ({curr_vivos_pct}%)")
    log(f"  Defunciones Fetales : {curr_def:,} ({curr_def_pct}%)")

    # Filas de tabla de partos generales
    filas_html = []
    for anio, row in tabla_conteo.iterrows():
        tot = int(row["Total Partos"])
        viv = int(row["Nacidos Vivos"])
        deff = int(row["Defunciones Fetales"])
        sd = int(row["Sin dato"])

        pct_viv = (viv / tot * 100) if tot > 0 else 0
        pct_def = (deff / tot * 100) if tot > 0 else 0

        is_curr = (anio == current_year)
        row_cls = ' class="row-current-year"' if is_curr else ""
        badge_html = ' <span class="badge-tag">actual</span>' if is_curr else ""

        filas_html.append(
            f"                <tr{row_cls}>\n"
            f"                    <td><strong>{anio}</strong>{badge_html}</td>\n"
            f"                    <td class=\"text-right\"><strong>{tot:,}</strong></td>\n"
            f"                    <td class=\"text-right\">{viv:,}</td>\n"
            f"                    <td class=\"text-right\">{pct_viv:.1f}%</td>\n"
            f"                    <td class=\"text-right\">{deff:,}</td>\n"
            f"                    <td class=\"text-right\">{pct_def:.1f}%</td>\n"
            f"                    <td class=\"text-right\">{sd:,}</td>\n"
            f"                </tr>"
        )
    filas_html_str = "\n".join(filas_html)

    tot_general_partos = int(tabla_conteo["Total Partos"].sum())
    tot_general_vivos = int(tabla_conteo["Nacidos Vivos"].sum())
    tot_general_def = int(tabla_conteo["Defunciones Fetales"].sum())
    tot_general_sd = int(tabla_conteo["Sin dato"].sum())
    tot_vivos_pct = f"{(tot_general_vivos / tot_general_partos * 100):.1f}" if tot_general_partos > 0 else "0.0"
    tot_def_pct = f"{(tot_general_def / tot_general_partos * 100):.1f}" if tot_general_partos > 0 else "0.0"

    datos_anuales = {
        "labels": [f"{a}*" if a == current_year else str(a) for a in tabla_conteo.index],
        "total": [int(x) for x in tabla_conteo["Total Partos"]],
        "vivos": [int(x) for x in tabla_conteo["Nacidos Vivos"]],
        "defunciones": [int(x) for x in tabla_conteo["Defunciones Fetales"]],
    }

    df_validas["periodo_mes"] = df_validas["fechaegreso_parsed"].dt.strftime("%Y-%m")
    tabla_mensual = df_validas.groupby(["periodo_mes", "cond_tipo"]).size().unstack(fill_value=0)
    for c in ["Nacidos Vivos", "Defunciones Fetales"]:
        if c not in tabla_mensual.columns:
            tabla_mensual[c] = 0
    tabla_mensual["Total Partos"] = tabla_mensual.sum(axis=1)
    tabla_mensual = tabla_mensual.sort_index()

    datos_mensuales = {
        "labels": list(tabla_mensual.index),
        "total": [int(x) for x in tabla_mensual["Total Partos"]],
        "vivos": [int(x) for x in tabla_mensual["Nacidos Vivos"]],
        "defunciones": [int(x) for x in tabla_mensual["Defunciones Fetales"]],
    }

    # ──────────────────────────────────────────────────────────
    #  BLOQUE 2: PREMATUREZ (< 32 SEMANAS)
    # ──────────────────────────────────────────────────────────
    log("\n--- Análisis de Prematurez (<32 semanas) ---")

    tabla_prem_anual = []
    prem_anual_labels = []
    prem_anual_nv_tot = []
    prem_anual_nv_prem = []
    prem_anual_tasa_nv = []

    sum_prem_nv = 0
    sum_prem_nv_prem = 0
    sum_prem_def_prem = 0
    sum_prem_tot = 0
    sum_partos_tot = 0

    curr_prem_nv = 0
    curr_prem_nv_prem = 0
    curr_prem_tasa_nv = "0.0"
    curr_prem_tot = 0

    for anio, grp in df_validas.groupby("anio"):
        tot_part = len(grp)
        nv_cant = int(grp["es_nv"].sum())
        nv_prem_cant = int((grp["es_nv"] & grp["es_prem_32"]).sum())
        def_prem_cant = int((grp["es_def"] & grp["es_prem_32"]).sum())
        tot_prem_cant = int(grp["es_prem_32"].sum())

        tasa_nv = (nv_prem_cant / nv_cant * 100) if nv_cant > 0 else 0.0
        tasa_global = (tot_prem_cant / tot_part * 100) if tot_part > 0 else 0.0

        sum_partos_tot += tot_part
        sum_prem_nv += nv_cant
        sum_prem_nv_prem += nv_prem_cant
        sum_prem_def_prem += def_prem_cant
        sum_prem_tot += tot_prem_cant

        is_curr = (anio == current_year)
        if is_curr:
            curr_prem_nv = nv_cant
            curr_prem_nv_prem = nv_prem_cant
            curr_prem_tasa_nv = f"{tasa_nv:.1f}"
            curr_prem_tot = tot_prem_cant

        label_anio = f"{anio}*" if is_curr else str(anio)
        prem_anual_labels.append(label_anio)
        prem_anual_nv_tot.append(nv_cant)
        prem_anual_nv_prem.append(nv_prem_cant)
        prem_anual_tasa_nv.append(round(tasa_nv, 1))

        tabla_prem_anual.append({
            "anio": int(anio),
            "is_curr": is_curr,
            "nv_cant": nv_cant,
            "nv_prem_cant": nv_prem_cant,
            "tasa_nv": round(tasa_nv, 1),
            "def_prem_cant": def_prem_cant,
            "tot_prem_cant": tot_prem_cant,
            "tasa_global": round(tasa_global, 1)
        })

    tot_tasa_nv_gen = (sum_prem_nv_prem / sum_prem_nv * 100) if sum_prem_nv > 0 else 0.0
    tot_tasa_global_gen = (sum_prem_tot / sum_partos_tot * 100) if sum_partos_tot > 0 else 0.0

    tabla_prem_total_general = {
        "nv_tot": sum_prem_nv,
        "nv_prem": sum_prem_nv_prem,
        "tasa_nv": round(tot_tasa_nv_gen, 1),
        "def_prem": sum_prem_def_prem,
        "tot_prem": sum_prem_tot,
        "tasa_global": round(tot_tasa_global_gen, 1)
    }

    prem_data_anual_json = {
        "labels": prem_anual_labels,
        "nv_tot": prem_anual_nv_tot,
        "nv_prem": prem_anual_nv_prem,
        "tasa_nv": prem_anual_tasa_nv,
    }

    # Desglose mensual de prematurez por año
    tabla_prem_mensual_por_anio = {}
    tabla_prem_totales_anuales = {}
    anios_disponibles = [int(a) for a in sorted(df_validas["anio"].unique(), reverse=True)]

    for anio in anios_disponibles:
        grp_a = df_validas[df_validas["anio"] == anio]
        meses_list = []
        for m in range(1, 13):
            grp_m = grp_a[grp_a["mes_num"] == m]
            if len(grp_m) == 0:
                continue
            tot_p = len(grp_m)
            nv_c = int(grp_m["es_nv"].sum())
            nv_p = int((grp_m["es_nv"] & grp_m["es_prem_32"]).sum())
            def_p = int((grp_m["es_def"] & grp_m["es_prem_32"]).sum())
            tot_p_prem = int(grp_m["es_prem_32"].sum())
            t_nv = round(nv_p / nv_c * 100, 1) if nv_c > 0 else 0.0
            t_tot = round(tot_p_prem / tot_p * 100, 1) if tot_p > 0 else 0.0

            meses_list.append({
                "mes_nombre": NOMBRES_MESES[m - 1],
                "nv_tot": nv_c,
                "nv_prem": nv_p,
                "tasa_nv": t_nv,
                "def_prem": def_p,
                "tot_prem": tot_p_prem,
                "tasa_tot": t_tot
            })

        tabla_prem_mensual_por_anio[int(anio)] = meses_list

        tot_p_anio = len(grp_a)
        nv_c_anio = int(grp_a["es_nv"].sum())
        nv_p_anio = int((grp_a["es_nv"] & grp_a["es_prem_32"]).sum())
        def_p_anio = int((grp_a["es_def"] & grp_a["es_prem_32"]).sum())
        tot_p_prem_anio = int(grp_a["es_prem_32"].sum())
        t_nv_anio = round(nv_p_anio / nv_c_anio * 100, 1) if nv_c_anio > 0 else 0.0
        t_tot_anio = round(tot_p_prem_anio / tot_p_anio * 100, 1) if tot_p_anio > 0 else 0.0

        tabla_prem_totales_anuales[int(anio)] = {
            "nv_tot": nv_c_anio,
            "nv_prem": nv_p_anio,
            "tasa_nv": t_nv_anio,
            "def_prem": def_p_anio,
            "tot_prem": tot_p_prem_anio,
            "tasa_global": t_tot_anio
        }

    opciones_select_html = "\n".join([
        f'                        <option value="{a}"{" selected" if a == current_year else ""}>{a}{" (Actual)" if a == current_year else ""}</option>'
        for a in anios_disponibles
    ])

    # ──────────────────────────────────────────────────────────
    #  BLOQUE 3: GRÁFICO DE BARRAS APILADAS Y TABLA 2 (EDAD GESTACIONAL)
    # ──────────────────────────────────────────────────────────
    log("\n--- Cálculo de Distribución de Edad Gestacional (Barras Apiladas) ---")
    nv_df = df_validas[df_validas["es_nv"]].copy()
    cats_orden = ["Termino", "32 a 36 semanas", "28 a 31 semanas", "<28 semanas"]
    anios_apilado = [int(a) for a in sorted(nv_df["anio"].unique())]

    apilado_pct = {c: [] for c in cats_orden}
    apilado_cnt = {c: [] for c in cats_orden}

    for a in anios_apilado:
        grp = nv_df[nv_df["anio"] == a]
        tot = len(grp)
        cnts = grp["cat_eg"].value_counts()
        for c in cats_orden:
            cnt = int(cnts.get(c, 0))
            pct = round(cnt / tot * 100, 1) if tot > 0 else 0.0
            apilado_cnt[c].append(cnt)
            apilado_pct[c].append(pct)
        log(f"  Año {a}: Término={apilado_pct['Termino'][-1]}% | 32-36s={apilado_pct['32 a 36 semanas'][-1]}% | 28-31s={apilado_pct['28 a 31 semanas'][-1]}% | <28s={apilado_pct['<28 semanas'][-1]}%")

    apilado_datos_json = {
        "labels": [str(a) for a in anios_apilado],
        "porcentajes": apilado_pct,
        "conteos": apilado_cnt
    }

    # Tabla 2: Detalle Anual y Mensual de Edad Gestacional
    tabla_eg_anual = []
    tot_general_eg = {"tot": 0, "t_cnt": 0, "s32_cnt": 0, "s28_cnt": 0, "m28_cnt": 0}

    for a in anios_apilado:
        grp = nv_df[nv_df["anio"] == a]
        tot = len(grp)
        cnts = grp["cat_eg"].value_counts()
        t = int(cnts.get("Termino", 0))
        s32 = int(cnts.get("32 a 36 semanas", 0))
        s28 = int(cnts.get("28 a 31 semanas", 0))
        m28 = int(cnts.get("<28 semanas", 0))

        tot_general_eg["tot"] += tot
        tot_general_eg["t_cnt"] += t
        tot_general_eg["s32_cnt"] += s32
        tot_general_eg["s28_cnt"] += s28
        tot_general_eg["m28_cnt"] += m28

        tabla_eg_anual.append({
            "anio": a,
            "is_curr": (a == current_year),
            "tot": tot,
            "t_cnt": t, "t_pct": round(t / tot * 100, 1) if tot > 0 else 0.0,
            "s32_cnt": s32, "s32_pct": round(s32 / tot * 100, 1) if tot > 0 else 0.0,
            "s28_cnt": s28, "s28_pct": round(s28 / tot * 100, 1) if tot > 0 else 0.0,
            "m28_cnt": m28, "m28_pct": round(m28 / tot * 100, 1) if tot > 0 else 0.0,
        })

    tot_nv_gen_tot = tot_general_eg["tot"]
    tabla_eg_total_general = {
        "tot": tot_nv_gen_tot,
        "t_cnt": tot_general_eg["t_cnt"],
        "t_pct": round(tot_general_eg["t_cnt"] / tot_nv_gen_tot * 100, 1) if tot_nv_gen_tot > 0 else 0.0,
        "s32_cnt": tot_general_eg["s32_cnt"],
        "s32_pct": round(tot_general_eg["s32_cnt"] / tot_nv_gen_tot * 100, 1) if tot_nv_gen_tot > 0 else 0.0,
        "s28_cnt": tot_general_eg["s28_cnt"],
        "s28_pct": round(tot_general_eg["s28_cnt"] / tot_nv_gen_tot * 100, 1) if tot_nv_gen_tot > 0 else 0.0,
        "m28_cnt": tot_general_eg["m28_cnt"],
        "m28_pct": round(tot_general_eg["m28_cnt"] / tot_nv_gen_tot * 100, 1) if tot_nv_gen_tot > 0 else 0.0,
    }

    tabla_eg_mensual_por_anio = {}
    tabla_eg_totales_anuales = {}

    for anio in anios_disponibles:
        grp_a = nv_df[nv_df["anio"] == anio]
        meses_eg = []
        for m in range(1, 13):
            grp_m = grp_a[grp_a["mes_num"] == m]
            if len(grp_m) == 0:
                continue
            tot_m = len(grp_m)
            cnts_m = grp_m["cat_eg"].value_counts()
            t_m = int(cnts_m.get("Termino", 0))
            s32_m = int(cnts_m.get("32 a 36 semanas", 0))
            s28_m = int(cnts_m.get("28 a 31 semanas", 0))
            m28_m = int(cnts_m.get("<28 semanas", 0))

            meses_eg.append({
                "mes": NOMBRES_MESES[m - 1],
                "tot": tot_m,
                "t_cnt": t_m, "t_pct": round(t_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
                "s32_cnt": s32_m, "s32_pct": round(s32_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
                "s28_cnt": s28_m, "s28_pct": round(s28_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
                "m28_cnt": m28_m, "m28_pct": round(m28_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
            })

        tabla_eg_mensual_por_anio[int(anio)] = meses_eg

        tot_a = len(grp_a)
        cnts_a = grp_a["cat_eg"].value_counts()
        t_a = int(cnts_a.get("Termino", 0))
        s32_a = int(cnts_a.get("32 a 36 semanas", 0))
        s28_a = int(cnts_a.get("28 a 31 semanas", 0))
        m28_a = int(cnts_a.get("<28 semanas", 0))

        tabla_eg_totales_anuales[int(anio)] = {
            "tot": tot_a,
            "t_cnt": t_a, "t_pct": round(t_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
            "s32_cnt": s32_a, "s32_pct": round(s32_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
            "s28_cnt": s28_a, "s28_pct": round(s28_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
            "m28_cnt": m28_a, "m28_pct": round(m28_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
        }

    # ──────────────────────────────────────────────────────────
    #  BLOQUE 4: SEGUIMIENTO DE PESO AL NACER
    # ──────────────────────────────────────────────────────────
    log("\n--- Análisis de Peso al Nacer (Nacidos Vivos) ---")
    cats_peso_orden = [
        "muy bajo peso <1500",
        "bajo peso 1500-2499 g",
        "peso adecuado 2500-3999 g",
        "sobre peso ≥4000 g"
    ]

    apilado_peso_cnt = {c: [] for c in cats_peso_orden}
    apilado_peso_pct = {c: [] for c in cats_peso_orden}

    for a in anios_apilado:
        grp = nv_df[nv_df["anio"] == a]
        tot = len(grp)
        cnts = grp["cat_peso"].value_counts()
        for c in cats_peso_orden:
            cnt = int(cnts.get(c, 0))
            pct = round(cnt / tot * 100, 1) if tot > 0 else 0.0
            apilado_peso_cnt[c].append(cnt)
            apilado_peso_pct[c].append(pct)
        log(f"  Año {a}: <1500={apilado_peso_pct['muy bajo peso <1500'][-1]}% | 1500-2499={apilado_peso_pct['bajo peso 1500-2499 g'][-1]}% | 2500-3999={apilado_peso_pct['peso adecuado 2500-3999 g'][-1]}% | >=4000={apilado_peso_pct['sobre peso ≥4000 g'][-1]}%")

    apilado_peso_datos_json = {
        "labels": [str(a) for a in anios_apilado],
        "porcentajes": apilado_peso_pct,
        "conteos": apilado_peso_cnt
    }

    # Tabla Detalle Peso Anual y Mensual
    tabla_peso_anual = []
    tot_general_peso = {"tot": 0, "mb_cnt": 0, "b_cnt": 0, "ad_cnt": 0, "sp_cnt": 0}

    for a in anios_apilado:
        grp = nv_df[nv_df["anio"] == a]
        tot = len(grp)
        cnts = grp["cat_peso"].value_counts()
        mb = int(cnts.get("muy bajo peso <1500", 0))
        b = int(cnts.get("bajo peso 1500-2499 g", 0))
        ad = int(cnts.get("peso adecuado 2500-3999 g", 0))
        sp = int(cnts.get("sobre peso ≥4000 g", 0))

        tot_general_peso["tot"] += tot
        tot_general_peso["mb_cnt"] += mb
        tot_general_peso["b_cnt"] += b
        tot_general_peso["ad_cnt"] += ad
        tot_general_peso["sp_cnt"] += sp

        tabla_peso_anual.append({
            "anio": a,
            "is_curr": (a == current_year),
            "tot": tot,
            "mb_cnt": mb, "mb_pct": round(mb / tot * 100, 1) if tot > 0 else 0.0,
            "b_cnt": b, "b_pct": round(b / tot * 100, 1) if tot > 0 else 0.0,
            "ad_cnt": ad, "ad_pct": round(ad / tot * 100, 1) if tot > 0 else 0.0,
            "sp_cnt": sp, "sp_pct": round(sp / tot * 100, 1) if tot > 0 else 0.0,
        })

    tot_nv_peso_gen = tot_general_peso["tot"]
    tabla_peso_total_general = {
        "tot": tot_nv_peso_gen,
        "mb_cnt": tot_general_peso["mb_cnt"],
        "mb_pct": round(tot_general_peso["mb_cnt"] / tot_nv_peso_gen * 100, 1) if tot_nv_peso_gen > 0 else 0.0,
        "b_cnt": tot_general_peso["b_cnt"],
        "b_pct": round(tot_general_peso["b_cnt"] / tot_nv_peso_gen * 100, 1) if tot_nv_peso_gen > 0 else 0.0,
        "ad_cnt": tot_general_peso["ad_cnt"],
        "ad_pct": round(tot_general_peso["ad_cnt"] / tot_nv_peso_gen * 100, 1) if tot_nv_peso_gen > 0 else 0.0,
        "sp_cnt": tot_general_peso["sp_cnt"],
        "sp_pct": round(tot_general_peso["sp_cnt"] / tot_nv_peso_gen * 100, 1) if tot_nv_peso_gen > 0 else 0.0,
    }

    tabla_peso_mensual_por_anio = {}
    tabla_peso_totales_anuales = {}

    for anio in anios_disponibles:
        grp_a = nv_df[nv_df["anio"] == anio]
        meses_peso = []
        for m in range(1, 13):
            grp_m = grp_a[grp_a["mes_num"] == m]
            if len(grp_m) == 0:
                continue
            tot_m = len(grp_m)
            cnts_m = grp_m["cat_peso"].value_counts()
            mb_m = int(cnts_m.get("muy bajo peso <1500", 0))
            b_m = int(cnts_m.get("bajo peso 1500-2499 g", 0))
            ad_m = int(cnts_m.get("peso adecuado 2500-3999 g", 0))
            sp_m = int(cnts_m.get("sobre peso ≥4000 g", 0))

            meses_peso.append({
                "mes": NOMBRES_MESES[m - 1],
                "tot": tot_m,
                "mb_cnt": mb_m, "mb_pct": round(mb_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
                "b_cnt": b_m, "b_pct": round(b_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
                "ad_cnt": ad_m, "ad_pct": round(ad_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
                "sp_cnt": sp_m, "sp_pct": round(sp_m / tot_m * 100, 1) if tot_m > 0 else 0.0,
            })

        tabla_peso_mensual_por_anio[int(anio)] = meses_peso

        tot_a = len(grp_a)
        cnts_a = grp_a["cat_peso"].value_counts()
        mb_a = int(cnts_a.get("muy bajo peso <1500", 0))
        b_a = int(cnts_a.get("bajo peso 1500-2499 g", 0))
        ad_a = int(cnts_a.get("peso adecuado 2500-3999 g", 0))
        sp_a = int(cnts_a.get("sobre peso ≥4000 g", 0))

        tabla_peso_totales_anuales[int(anio)] = {
            "tot": tot_a,
            "mb_cnt": mb_a, "mb_pct": round(mb_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
            "b_cnt": b_a, "b_pct": round(b_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
            "ad_cnt": ad_a, "ad_pct": round(ad_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
            "sp_cnt": sp_a, "sp_pct": round(sp_a / tot_a * 100, 1) if tot_a > 0 else 0.0,
        }

    # ──────────────────────────────────────────────────────────
    #  INYECCIÓN EN PLANTILLA HTML
    # ──────────────────────────────────────────────────────────
    template_raw = TEMPLATE_PATH.read_text(encoding="utf-8")

    html = (
        template_raw
        .replace("__PERIODO_ANALIZADO__", periodo_str)
        .replace("__CURRENT_YEAR__", str(current_year))
        .replace("__CURRENT_TOTAL__", f"{curr_total:,}")
        .replace("__CURRENT_VIVOS__", f"{curr_vivos:,}")
        .replace("__CURRENT_VIVOS_PCT__", curr_vivos_pct)
        .replace("__CURRENT_DEF__", f"{curr_def:,}")
        .replace("__CURRENT_DEF_PCT__", curr_def_pct)
        .replace("__FILAS_TABLA__", filas_html_str)
        .replace("__TOTAL_PARTOS__", f"{tot_general_partos:,}")
        .replace("__TOTAL_VIVOS__", f"{tot_general_vivos:,}")
        .replace("__TOTAL_VIVOS_PCT__", tot_vivos_pct)
        .replace("__TOTAL_DEF__", f"{tot_general_def:,}")
        .replace("__TOTAL_DEF_PCT__", tot_def_pct)
        .replace("__TOTAL_SINDATO__", f"{tot_general_sd:,}")
        .replace("__DATA_ANUAL_JSON__", json.dumps(datos_anuales, ensure_ascii=False))
        .replace("__DATA_MENSUAL_JSON__", json.dumps(datos_mensuales, ensure_ascii=False))
        # Variables de Prematurez
        .replace("__PREM_CURR_NV__", f"{curr_prem_nv_prem:,}")
        .replace("__PREM_CURR_TASA_NV__", curr_prem_tasa_nv)
        .replace("__PREM_CURR_TOT__", f"{curr_prem_tot:,}")
        .replace("__PREM_DATA_ANUAL_JSON__", json.dumps(prem_data_anual_json, ensure_ascii=False))
        # Selectores y tablas interactivas de prematurez
        .replace("__OPCIONES_ANIOS_SELECT__", opciones_select_html)
        .replace("__TABLA_PREM_ANUAL_JSON__", json.dumps(tabla_prem_anual, ensure_ascii=False))
        .replace("__TABLA_PREM_MENSUAL_JSON__", json.dumps(tabla_prem_mensual_por_anio, ensure_ascii=False))
        .replace("__TABLA_PREM_TOTALES_ANUALES_JSON__", json.dumps(tabla_prem_totales_anuales, ensure_ascii=False))
        .replace("__TABLA_PREM_TOTAL_GENERAL_JSON__", json.dumps(tabla_prem_total_general, ensure_ascii=False))
        # Datos del gráfico apilado EG
        .replace("__APILADO_DATOS_JSON__", json.dumps(apilado_datos_json, ensure_ascii=False))
        # Datos de la tabla 2 (Edad Gestacional)
        .replace("__TABLA_EG_ANUAL_JSON__", json.dumps(tabla_eg_anual, ensure_ascii=False))
        .replace("__TABLA_EG_MENSUAL_JSON__", json.dumps(tabla_eg_mensual_por_anio, ensure_ascii=False))
        .replace("__TABLA_EG_TOTALES_ANUALES_JSON__", json.dumps(tabla_eg_totales_anuales, ensure_ascii=False))
        .replace("__TABLA_EG_TOTAL_GENERAL_JSON__", json.dumps(tabla_eg_total_general, ensure_ascii=False))
        # Datos de Seguimiento de Peso
        .replace("__APILADO_PESO_DATOS_JSON__", json.dumps(apilado_peso_datos_json, ensure_ascii=False))
        .replace("__TABLA_PESO_ANUAL_JSON__", json.dumps(tabla_peso_anual, ensure_ascii=False))
        .replace("__TABLA_PESO_MENSUAL_JSON__", json.dumps(tabla_peso_mensual_por_anio, ensure_ascii=False))
        .replace("__TABLA_PESO_TOTALES_ANUALES_JSON__", json.dumps(tabla_peso_totales_anuales, ensure_ascii=False))
        .replace("__TABLA_PESO_TOTAL_GENERAL_JSON__", json.dumps(tabla_peso_total_general, ensure_ascii=False))
    )

    output_path.mkdir(parents=True, exist_ok=True)
    html_salida = output_path / HTML_OUTPUT_NAME
    html_salida.write_text(html, encoding="utf-8")

    log("\n" + "=" * 60)
    log("  INFORME ACTUALIZADO CON ÉXITO")
    log(f"  Archivo: {html_salida}")
    log("=" * 60)

    return html_salida


# ══════════════════════════════════════════════════════════════
#  EJECUCIÓN DIRECTA
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    generar_informe()
