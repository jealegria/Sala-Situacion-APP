"""
report.py — Informe de SM y Tocogineco
========================================
Toda la logica de generacion del informe de Salud Mental y Tocoginecologia.
La UI (app/ui/pages/informes/sm_tocogineco.py) solo llama a generar_informe().

Para modificar el informe, editar SOLO este archivo.

Rutas por defecto (se pueden sobreescribir desde la UI):
  - Input  : C:\\02_HPN\\01_Base\\agendas_consolidado
  - Output : C:\\03_Apps\\Sala-Situacion-APP\\Outputs\\informes

El archivo de calendario se busca automaticamente en:
  <carpeta_parent_del_input>\\tablas_relacionales\\calendario_se.csv
"""
import os
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES — editar aqui para cambiar comportamiento
# ══════════════════════════════════════════════════════════════

# Rutas por defecto (se usan tambien como valores iniciales en la UI)
DEFAULT_INPUT_PATH  = Path(r"C:\02_HPN\01_Base\agendas_consolidado")
DEFAULT_OUTPUT_PATH = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\informes")

# Nombre del archivo de calendario (dentro de tablas_relacionales)
CALENDARIO_FILENAME = "calendario_se.csv"

# Nombre del archivo HTML de salida
HTML_OUTPUT_FILENAME = "SM y Tocogineco.html"

# Columnas minimas requeridas en los CSVs de agendas
COLUMNAS_REQUERIDAS = ['idturno', 'fechaconsulta', 'tipoprestacion']

# Prestaciones a filtrar
PRESTACION_TOCO = "consulta de guardia de tocoginecología"
PRESTACION_SM   = "consulta de guardia de salud mental"

# Terminos SNOMED para Tocoginecologia
TERMINOS_SNOMED = [
    "trabajo de parto", "trabajo de parto normal", "sangrado uterino",
    "sangrado vaginal", "sangrado uterino anormal", "preeclampsia"
]
MAPEO_SNOMED = {
    "trabajo de parto":          "Trabajo de Parto",
    "trabajo de parto normal":   "Trabajo de Parto",
    "sangrado uterino":          "Sangrado Uterino",
    "sangrado uterino anormal":  "Sangrado Uterino",
    "sangrado vaginal":          "Sangrado Vaginal",
    "preeclampsia":              "HTA embarazo",
}
NOMBRES_FINALES_SNOMED = list(dict.fromkeys(MAPEO_SNOMED.values()))

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _parsear_fechas(series: pd.Series) -> pd.Series:
    """Parsea fechas en formatos mixtos: YYYY-MM-DD HH:MM:SS, YYYY-MM-DD, DD/MM/YYYY."""
    s = series.astype(str).str.strip()
    parsed = pd.to_datetime(s, format='%Y-%m-%d %H:%M:%S', errors='coerce')

    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(s[mask], format='%Y-%m-%d', errors='coerce')

    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(s[mask], format='%d/%m/%Y', errors='coerce')

    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(s[mask], dayfirst=True, errors='coerce')

    return parsed.dt.normalize()


def _cargar_calendario(path_fechas: Path, log: LogFn) -> pd.DataFrame | None:
    """Carga el archivo calendario_se.csv con semanas epidemiologicas."""
    log(f"    Calendario : {path_fechas}")
    if not path_fechas.exists():
        log(f"    [ERROR] No se encontro el archivo de calendario: {path_fechas}")
        return None
    try:
        df = pd.read_csv(path_fechas, encoding='latin1', sep=';')
        required = ['Fecha', 'Semana', 'Año_se']
        missing = [c for c in required if c not in df.columns]
        if missing:
            log(f"    [ERROR] Columnas faltantes en calendario: {missing}")
            return None
        df = df[required].copy()
        df['Fecha_dt_merge'] = _parsear_fechas(df['Fecha'])
        df.dropna(subset=['Fecha_dt_merge'], inplace=True)
        log(f"    Filas calendario: {len(df):,}")
        return df
    except Exception as e:
        log(f"    [ERROR] Error cargando calendario: {e}")
        return None


def _cargar_agendas(carpeta: Path, log: LogFn) -> pd.DataFrame | None:
    """Lee y concatena todos los CSVs de la carpeta de agendas."""
    archivos = [f for f in carpeta.iterdir()
                if f.is_file() and f.suffix.lower() == '.csv']

    if not archivos:
        log(f"    [ERROR] No se encontraron archivos CSV en: {carpeta}")
        return None

    log(f"    Archivos CSV encontrados: {len(archivos)}")
    lista_dfs = []

    for archivo in sorted(archivos):
        try:
            df_temp = pd.read_csv(
                archivo, encoding='utf-8-sig', sep=';',
                on_bad_lines='warn', low_memory=False
            )
            faltan = set(COLUMNAS_REQUERIDAS) - set(df_temp.columns)
            if faltan:
                log(f"    [WARN] Saltando '{archivo.name}' — faltan columnas: {faltan}")
                continue
            lista_dfs.append(df_temp)
            log(f"    [OK] {archivo.name}  ({len(df_temp):,} filas)")
        except Exception as e:
            log(f"    [ERROR] {archivo.name}: {e}")

    if not lista_dfs:
        log("    [ERROR] Ningun archivo CSV valido pudo cargarse.")
        return None

    df_main = pd.concat(lista_dfs, ignore_index=True)
    log(f"\n    Total registros combinados  : {len(df_main):,}")
    df_main.drop_duplicates(subset=['idturno'], keep='first', inplace=True)
    log(f"    Registros tras deduplicar   : {len(df_main):,}")
    return df_main


# ══════════════════════════════════════════════════════════════
#  PROCESAMIENTO
# ══════════════════════════════════════════════════════════════

def _procesar_salud_mental(df_main: pd.DataFrame, df_fechas: pd.DataFrame,
                           anio: int, log: LogFn) -> dict | None:
    log("\n  [SM] Procesando Salud Mental...")
    df = df_main[df_main['tipoprestacion'] == PRESTACION_SM].copy()
    log(f"    Registros '{PRESTACION_SM}': {len(df):,}")

    if df.empty:
        log("    [WARN] No se encontraron registros de Salud Mental.")
        return None

    df['Fecha_dt_merge'] = _parsear_fechas(df['fechaconsulta'])
    df = pd.merge(df, df_fechas, on='Fecha_dt_merge', how='left')
    df = df[df['Año_se'] == anio].copy()
    df.dropna(subset=['Semana'], inplace=True)

    if df.empty:
        log(f"    [WARN] Sin datos de SM para el año {anio}.")
        return None

    df['Semana'] = df['Semana'].astype(int)
    min_s, max_s = int(df['Semana'].min()), int(df['Semana'].max())
    rango = pd.DataFrame({'Semana': range(min_s, max_s + 1)})

    agrupado = df.groupby('Semana').size().reset_index(name='Cantidad')
    final = pd.merge(rango, agrupado, on='Semana', how='left').fillna(0).astype(int)

    total = int(final['Cantidad'].sum())
    log(f"    Semanas: {min_s} a {max_s}  |  Total consultas SM {anio}: {total:,}")

    return {
        "json_total":      final.sort_values('Semana').to_json(orient='records'),
        "min_week":        min_s,
        "max_week":        max_s,
        "total_consultas": total,
    }


def _procesar_tocoginecologia(df_main: pd.DataFrame, df_fechas: pd.DataFrame,
                               anio: int, log: LogFn) -> dict | None:
    log("\n  [TOCO] Procesando Tocoginecologia...")
    df = df_main[df_main['tipoprestacion'] == PRESTACION_TOCO].copy()
    log(f"    Registros '{PRESTACION_TOCO}': {len(df):,}")

    if df.empty:
        log("    [WARN] No se encontraron registros de Tocoginecologia.")
        return None

    # Prioridad: snomedterm1; si vacio, usar snomedterm2
    t1 = df['snomedterm1'].fillna('').str.strip().str.lower()
    t2 = (df['snomedterm2'].fillna('').str.strip().str.lower()
          if 'snomedterm2' in df.columns else pd.Series('', index=df.index))
    df['termino_busqueda'] = t1.mask(t1 == '', t2)

    df['Fecha_dt_merge'] = _parsear_fechas(df['fechaconsulta'])
    df = pd.merge(df, df_fechas, on='Fecha_dt_merge', how='left')
    df = df[df['Año_se'] == anio].copy()
    df.dropna(subset=['Semana'], inplace=True)

    if df.empty:
        log(f"    [WARN] Sin datos de Toco para el año {anio}.")
        return None

    df['Semana'] = df['Semana'].astype(int)
    min_s, max_s = int(df['Semana'].min()), int(df['Semana'].max())
    all_weeks = pd.Index(range(min_s, max_s + 1), name='Semana')
    rango = pd.DataFrame({'Semana': all_weeks})

    # Total por semana
    agrupado = df.groupby('Semana').size().reset_index(name='Cantidad')
    final_total = pd.merge(rango, agrupado, on='Semana', how='left').fillna(0)
    final_total['Cantidad'] = final_total['Cantidad'].astype(int)

    # SNOMED por semana
    df_snomed = df[df['termino_busqueda'].isin(TERMINOS_SNOMED)].copy()
    df_snomed_final = pd.DataFrame(index=all_weeks)

    if not df_snomed.empty:
        df_snomed['TerminoAgrupado'] = df_snomed['termino_busqueda'].map(MAPEO_SNOMED)
        pivot = df_snomed.groupby(['Semana', 'TerminoAgrupado']).size().unstack(fill_value=0)
        df_snomed_final = df_snomed_final.join(pivot)

    for term in NOMBRES_FINALES_SNOMED:
        if term not in df_snomed_final.columns:
            df_snomed_final[term] = 0
    df_snomed_final.fillna(0, inplace=True)
    df_snomed_final = df_snomed_final[NOMBRES_FINALES_SNOMED].astype(int)
    df_snomed_final.reset_index(inplace=True)

    total = int(final_total['Cantidad'].sum())
    log(f"    Semanas: {min_s} a {max_s}  |  Total consultas Toco {anio}: {total:,}")
    log(f"    Conteo SNOMED: {dict(df_snomed_final[NOMBRES_FINALES_SNOMED].sum())}")

    return {
        "json_total":      final_total.sort_values('Semana').to_json(orient='records'),
        "json_snomed":     df_snomed_final.sort_values('Semana').to_json(orient='records'),
        "snomed_terms":    NOMBRES_FINALES_SNOMED,
        "min_week":        min_s,
        "max_week":        max_s,
        "total_consultas": total,
    }


# ══════════════════════════════════════════════════════════════
#  GENERACION HTML
# ══════════════════════════════════════════════════════════════

def _generar_html(datos_toco: dict | None, datos_sm: dict | None,
                  output_file: Path, anio: int, log: LogFn) -> None:
    fecha_actual = datetime.now().strftime("%d/%m/%Y")

    toco_min = datos_toco['min_week'] if datos_toco else 1
    toco_max = datos_toco['max_week'] if datos_toco else 52
    sm_min   = datos_sm['min_week']   if datos_sm   else 1
    sm_max   = datos_sm['max_week']   if datos_sm   else 52

    snomed_datasets_str = ""
    if datos_toco:
        colors = ['#dc3545', '#007bff', '#28a745', '#ffc107', '#17a2b8', '#6f42c1']
        for i, term in enumerate(datos_toco['snomed_terms']):
            color = colors[i % len(colors)]
            snomed_datasets_str += f"""
            {{
                label: '{term.replace("'", "\\'")}',
                data: [],
                borderColor: '{color}',
                backgroundColor: '{color}20',
                fill: true,
                tension: 0.1
            }},"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte Consolidado de Guardias - {anio}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; color: #333; display: flex; }}
        .sidebar {{ width: 240px; background-color: #004a99; color: white; position: fixed; height: 100%; padding-top: 20px; z-index: 10; }}
        .sidebar h2 {{ text-align: center; padding: 0 10px; font-size: 1.2em; color: white; }}
        .sidebar ul {{ list-style-type: none; padding: 0; margin-top: 30px; }}
        .sidebar ul li a {{ display: block; color: white; padding: 15px 20px; text-decoration: none; transition: background-color 0.3s; border-left: 4px solid transparent; }}
        .sidebar ul li a:hover {{ background-color: #0056b3; }}
        .sidebar ul li a.active {{ background-color: #0062cc; border-left-color: #ffc107; }}
        .main-content {{ margin-left: 240px; padding: 20px; width: calc(100% - 240px); position: relative; }}
        .fecha-actualizacion {{ position: absolute; top: 15px; right: 25px; font-size: 0.85em; color: #666; font-style: italic; }}
        .page-content {{ display: none; }}
        .page-content.active {{ display: block; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #0056b3; text-align: center; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 40px; }}
        h1 {{ margin-top: 10px; font-size: 1.8em; }}
        h3 {{ font-size: 1.4em; border-bottom: none; color: #333; }}
        .controls {{ margin: 20px auto; padding: 15px; background-color: #e9ecef; border-radius: 8px; display: flex; flex-wrap: wrap; justify-content: space-around; align-items: center; max-width: 600px; }}
        .control-group {{ display: flex; flex-direction: column; align-items: center; margin: 5px 15px; }}
        .control-group label {{ margin-bottom: 5px; font-size: 0.9em; }}
        .control-group input[type="range"] {{ width: 200px; }}
        .chart-container {{ position: relative; height: 50vh; width: 95%; margin: 20px auto; }}
        .table-wrapper {{ width: 95%; max-height: 400px; overflow-y: auto; margin: 20px auto; border: 1px solid #e0e0e0; }}
        .table-wrapper-narrow {{ max-width: 450px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #f7f7f7; font-weight: bold; text-align: center; position: sticky; top: 0; }}
        td:not(:first-child) {{ text-align: center; }}
        .footer {{ margin-top: 30px; text-align: center; font-size: 0.9em; color: #777; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>Atenciones de Guardia</h2>
        <ul>
            <li><a href="#toco" id="nav-toco" class="nav-link active">Tocoginecología</a></li>
            <li><a href="#sm"   id="nav-sm"   class="nav-link">Salud Mental</a></li>
        </ul>
    </div>

    <div class="main-content">
        <div class="fecha-actualizacion">Actualizado a {fecha_actual}</div>

        <!-- TOCOGINECOLOGÍA -->
        <div id="page-toco" class="page-content active">
            <div class="container">
                <h1>Guardia de Tocoginecología - Año {anio}</h1>
                {'<h3>No se encontraron datos para este reporte.</h3>' if not datos_toco else f"""
                <h2>Total de Consultas por Semana Epidemiológica</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="tocoTotalMinSlider">Desde Semana: <span id="tocoTotalMinVal">{toco_min}</span></label>
                        <input type="range" id="tocoTotalMinSlider" min="{toco_min}" max="{toco_max}" value="{toco_min}">
                    </div>
                    <div class="control-group">
                        <label for="tocoTotalMaxSlider">Hasta Semana: <span id="tocoTotalMaxVal">{toco_max}</span></label>
                        <input type="range" id="tocoTotalMaxSlider" min="{toco_min}" max="{toco_max}" value="{toco_max}">
                    </div>
                </div>
                <div class="chart-container"><canvas id="tocoTotalChart"></canvas></div>
                <div class="table-wrapper table-wrapper-narrow" id="tocoTotalTable"></div>
                <h2>Análisis de Términos Snomed por Semana Epidemiológica</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="tocoSnomedMinSlider">Desde Semana: <span id="tocoSnomedMinVal">{toco_min}</span></label>
                        <input type="range" id="tocoSnomedMinSlider" min="{toco_min}" max="{toco_max}" value="{toco_min}">
                    </div>
                    <div class="control-group">
                        <label for="tocoSnomedMaxSlider">Hasta Semana: <span id="tocoSnomedMaxVal">{toco_max}</span></label>
                        <input type="range" id="tocoSnomedMaxSlider" min="{toco_min}" max="{toco_max}" value="{toco_max}">
                    </div>
                </div>
                <div class="chart-container"><canvas id="tocoSnomedChart"></canvas></div>
                <div class="table-wrapper" id="tocoSnomedTable"></div>
                """}
            </div>
        </div>

        <!-- SALUD MENTAL -->
        <div id="page-sm" class="page-content">
            <div class="container">
                <h1>Guardia de Salud Mental - Año {anio}</h1>
                {'<h3>No se encontraron datos para este reporte.</h3>' if not datos_sm else f"""
                <h2>Total de Consultas por Semana Epidemiológica</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="smTotalMinSlider">Desde Semana: <span id="smTotalMinVal">{sm_min}</span></label>
                        <input type="range" id="smTotalMinSlider" min="{sm_min}" max="{sm_max}" value="{sm_min}">
                    </div>
                    <div class="control-group">
                        <label for="smTotalMaxSlider">Hasta Semana: <span id="smTotalMaxVal">{sm_max}</span></label>
                        <input type="range" id="smTotalMaxSlider" min="{sm_min}" max="{sm_max}" value="{sm_max}">
                    </div>
                </div>
                <div class="chart-container"><canvas id="smTotalChart"></canvas></div>
                <div class="table-wrapper table-wrapper-narrow" id="smTotalTable"></div>
                """}
            </div>
        </div>

        <div class="footer"><p><em>Reporte generado en el Departamento de Epidemiología y Estadística HPN - Fuente: Andes</em></p></div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function () {{
            const navLinks = document.querySelectorAll('.nav-link');
            const pages    = document.querySelectorAll('.page-content');

            function switchPage(targetId) {{
                pages.forEach(p => p.classList.remove('active'));
                navLinks.forEach(l => l.classList.remove('active'));
                document.getElementById(targetId).classList.add('active');
                document.querySelector(`[href="#${{targetId.split('-')[1]}}"]`).classList.add('active');
            }}
            navLinks.forEach(link => {{
                link.addEventListener('click', e => {{
                    e.preventDefault();
                    switchPage(`page-${{e.target.id.split('-')[1]}}`);
                }});
            }});

            function syncSliders(minS, maxS, minSpan, maxSpan, changed) {{
                let lo = parseInt(minS.value), hi = parseInt(maxS.value);
                if (changed === minS && lo > hi) {{ maxS.value = lo; hi = lo; }}
                if (changed === maxS && hi < lo) {{ minS.value = hi; lo = hi; }}
                minSpan.textContent = lo; maxSpan.textContent = hi;
                return {{ lo, hi }};
            }}

            // ── TOCOGINECOLOGÍA ──────────────────────────────────────────────
            const hasToco = {'true' if datos_toco else 'false'};
            if (hasToco) {{
                const TOCO_TOTAL  = JSON.parse('{datos_toco["json_total"]  if datos_toco else "[]"}');
                const TOCO_SNOMED = JSON.parse('{datos_toco["json_snomed"] if datos_toco else "[]"}');
                const TOCO_TERMS  = {json.dumps(datos_toco["snomed_terms"]) if datos_toco else "[]"};

                const tocoTotalMinS  = document.getElementById('tocoTotalMinSlider');
                const tocoTotalMaxS  = document.getElementById('tocoTotalMaxSlider');
                const tocoTotalMinV  = document.getElementById('tocoTotalMinVal');
                const tocoTotalMaxV  = document.getElementById('tocoTotalMaxVal');
                const tocoTotalTable = document.getElementById('tocoTotalTable');

                const ctxTT = document.getElementById('tocoTotalChart').getContext('2d');
                const tocoTotalChart = new Chart(ctxTT, {{
                    type: 'line',
                    data: {{ labels: [], datasets: [{{ label: 'Consultas', data: [], borderColor: '#0056b3', fill: true, backgroundColor: 'rgba(0,86,179,0.1)' }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, scales: {{ y: {{ beginAtZero: true }} }} }}
                }});

                function updateTocoTotal(changed) {{
                    const {{ lo, hi }} = syncSliders(tocoTotalMinS, tocoTotalMaxS, tocoTotalMinV, tocoTotalMaxV, changed);
                    const fd = TOCO_TOTAL.filter(r => r.Semana >= lo && r.Semana <= hi);
                    tocoTotalChart.data.labels = fd.map(r => r.Semana);
                    tocoTotalChart.data.datasets[0].data = fd.map(r => r.Cantidad);
                    tocoTotalChart.update();
                    let html = '<table><thead><tr><th>Semana</th><th>Consultas</th></tr></thead><tbody>';
                    let sum = 0;
                    fd.forEach(r => {{ html += `<tr><td>${{r.Semana}}</td><td>${{r.Cantidad}}</td></tr>`; sum += r.Cantidad; }});
                    html += `<tr style="font-weight:bold;background:#f0f0f0"><td>Total</td><td>${{sum}}</td></tr>`;
                    tocoTotalTable.innerHTML = html + '</tbody></table>';
                }}
                tocoTotalMinS.addEventListener('input', e => updateTocoTotal(e.target));
                tocoTotalMaxS.addEventListener('input', e => updateTocoTotal(e.target));

                const tocoSnomedMinS  = document.getElementById('tocoSnomedMinSlider');
                const tocoSnomedMaxS  = document.getElementById('tocoSnomedMaxSlider');
                const tocoSnomedMinV  = document.getElementById('tocoSnomedMinVal');
                const tocoSnomedMaxV  = document.getElementById('tocoSnomedMaxVal');
                const tocoSnomedTable = document.getElementById('tocoSnomedTable');

                const ctxTS = document.getElementById('tocoSnomedChart').getContext('2d');
                const tocoSnomedChart = new Chart(ctxTS, {{
                    type: 'line',
                    data: {{ labels: [], datasets: [{snomed_datasets_str}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'top' }} }}, scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Cantidad de Registros' }} }} }} }}
                }});

                function updateTocoSnomed(changed) {{
                    const {{ lo, hi }} = syncSliders(tocoSnomedMinS, tocoSnomedMaxS, tocoSnomedMinV, tocoSnomedMaxV, changed);
                    const fd = TOCO_SNOMED.filter(r => r.Semana >= lo && r.Semana <= hi);
                    tocoSnomedChart.data.labels = fd.map(r => r.Semana);
                    tocoSnomedChart.data.datasets.forEach((ds, i) => {{ ds.data = fd.map(r => r[TOCO_TERMS[i]] || 0); }});
                    tocoSnomedChart.update();
                    let html = `<table><thead><tr><th>Semana</th>${{TOCO_TERMS.map(t => `<th>${{t}}</th>`).join('')}}</tr></thead><tbody>`;
                    let totals = {{}}; TOCO_TERMS.forEach(t => totals[t] = 0);
                    fd.forEach(row => {{
                        html += `<tr><td>${{row.Semana}}</td>`;
                        TOCO_TERMS.forEach(t => {{ const v = row[t]||0; html += `<td>${{v}}</td>`; totals[t]+=v; }});
                        html += '</tr>';
                    }});
                    html += `<tr style="font-weight:bold;background:#f0f0f0"><td>Total</td>${{TOCO_TERMS.map(t=>`<td>${{totals[t]}}</td>`).join('')}}</tr>`;
                    tocoSnomedTable.innerHTML = html + '</tbody></table>';
                }}
                tocoSnomedMinS.addEventListener('input', e => updateTocoSnomed(e.target));
                tocoSnomedMaxS.addEventListener('input', e => updateTocoSnomed(e.target));

                updateTocoTotal(tocoTotalMinS);
                updateTocoSnomed(tocoSnomedMinS);
            }}

            // ── SALUD MENTAL ─────────────────────────────────────────────────
            const hasSm = {'true' if datos_sm else 'false'};
            if (hasSm) {{
                const SM_TOTAL = JSON.parse('{datos_sm["json_total"] if datos_sm else "[]"}');

                const smMinS  = document.getElementById('smTotalMinSlider');
                const smMaxS  = document.getElementById('smTotalMaxSlider');
                const smMinV  = document.getElementById('smTotalMinVal');
                const smMaxV  = document.getElementById('smTotalMaxVal');
                const smTable = document.getElementById('smTotalTable');

                const ctxSM = document.getElementById('smTotalChart').getContext('2d');
                const smChart = new Chart(ctxSM, {{
                    type: 'line',
                    data: {{ labels: [], datasets: [{{ label: 'Consultas', data: [], borderColor: '#0056b3', fill: true, backgroundColor: 'rgba(0,86,179,0.1)' }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, scales: {{ y: {{ beginAtZero: true }} }} }}
                }});

                function updateSm(changed) {{
                    const {{ lo, hi }} = syncSliders(smMinS, smMaxS, smMinV, smMaxV, changed);
                    const fd = SM_TOTAL.filter(r => r.Semana >= lo && r.Semana <= hi);
                    smChart.data.labels = fd.map(r => r.Semana);
                    smChart.data.datasets[0].data = fd.map(r => r.Cantidad);
                    smChart.update();
                    let html = '<table><thead><tr><th>Semana</th><th>Consultas</th></tr></thead><tbody>';
                    let sum = 0;
                    fd.forEach(r => {{ html += `<tr><td>${{r.Semana}}</td><td>${{r.Cantidad}}</td></tr>`; sum += r.Cantidad; }});
                    html += `<tr style="font-weight:bold;background:#f0f0f0"><td>Total</td><td>${{sum}}</td></tr>`;
                    smTable.innerHTML = html + '</tbody></table>';
                }}
                smMinS.addEventListener('input', e => updateSm(e.target));
                smMaxS.addEventListener('input', e => updateSm(e.target));
                updateSm(smMinS);
            }}
        }});
    </script>
</body>
</html>"""

    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        log(f"\n    [OK] HTML generado: {output_file}")
    except Exception as e:
        log(f"\n    [ERROR] No se pudo guardar el HTML: {e}")


# ══════════════════════════════════════════════════════════════
#  FUNCION PUBLICA PRINCIPAL
# ══════════════════════════════════════════════════════════════

def generar_informe(input_path: Path, output_path: Path, log: LogFn,
                    anio: int | None = None) -> None:
    """
    Genera el informe HTML de SM y Tocogineco.

    Args:
        input_path:  Carpeta agendas_consolidado con los CSVs normalizados.
        output_path: Carpeta donde se guarda el HTML generado.
        log:         Callback para emitir mensajes a la consola de la UI.
        anio:        Año del reporte. Si None, usa el año actual.
    """
    anio = anio or datetime.now().year
    log(f"\n{'═'*65}")
    log(f"  INFORME SM Y TOCOGINECO — AÑO {anio}")
    log(f"{'═'*65}")

    # Calendario: hermana de la carpeta input llamada tablas_relacionales
    path_calendario = input_path.parent / "tablas_relacionales" / CALENDARIO_FILENAME

    # ── 1. Cargar agendas ──────────────────────────────────────
    log("\n  [1/4] Cargando archivos de agendas...")
    df_main = _cargar_agendas(input_path, log)
    if df_main is None:
        log("\n  [ERROR] Proceso detenido por falta de datos.")
        return

    # ── 2. Cargar calendario ───────────────────────────────────
    log("\n  [2/4] Cargando calendario epidemiologico...")
    df_fechas = _cargar_calendario(path_calendario, log)
    if df_fechas is None:
        log("\n  [ERROR] Proceso detenido por falta de calendario.")
        return

    # ── 3. Procesar servicios ──────────────────────────────────
    log("\n  [3/4] Procesando datos...")
    datos_toco = _procesar_tocoginecologia(df_main, df_fechas, anio, log)
    datos_sm   = _procesar_salud_mental(df_main, df_fechas, anio, log)

    if not datos_toco and not datos_sm:
        log("\n  [ERROR] Sin datos para ningun servicio. No se genera HTML.")
        return

    # ── 4. Generar HTML ────────────────────────────────────────
    log("\n  [4/4] Generando HTML...")
    output_file = output_path / HTML_OUTPUT_FILENAME
    _generar_html(datos_toco, datos_sm, output_file, anio, log)

    log(f"\n{'═'*65}")
    log(f"  PROCESO COMPLETADO")
    log(f"{'═'*65}")
