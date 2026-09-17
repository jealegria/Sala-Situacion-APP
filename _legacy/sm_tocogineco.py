# ================================== #
# ===        IMPORTACIONES         === #
# ================================== #
import os
import pandas as pd
import json
import traceback
from datetime import datetime

# ================================== #
# === CONFIGURACIÓN Y ORIGEN DE DATOS === #
# ================================== #
RUTA_BASE = r"C:\Users\usuario\Desktop\base" 
ANIO_REPORTE = 2026

CARPETA_DATOS = os.path.join(RUTA_BASE, "agendas_consolidado")
PATH_FECHAS = os.path.join(RUTA_BASE, "tablas_relacionales", "calendario_se.csv")
PATH_HTML_OUTPUT = r"C:\Users\usuario\Desktop\Juan\scripts para reportes\output\SM y Tocogineco.html"

PRESTACION_TOCO = "consulta de guardia de tocoginecología"
TERMINOS_SNOMED_A_BUSCAR = [
    "trabajo de parto", "trabajo de parto normal", "sangrado uterino",
    "sangrado vaginal", "sangrado uterino anormal", "preeclampsia"
]
MAPEO_SNOMED = {
    "trabajo de parto": "Trabajo de Parto", "trabajo de parto normal": "Trabajo de Parto",
    "sangrado uterino": "Sangrado Uterino", "sangrado uterino anormal": "Sangrado Uterino",
    "sangrado vaginal": "Sangrado Vaginal", "preeclampsia": "HTA embarazo" 
}
NOMBRES_FINALES_SNOMED = list(dict.fromkeys(MAPEO_SNOMED.values()))

PRESTACION_SM = "consulta de guardia de salud mental"


# ================================== #
# ===   FUNCIONES AUXILIARES     === #
# ================================== #

def parsear_fechas_robusto(series):
    """
    Intenta parsear fechas manejando formatos mixtos de forma estricta.
    1. YYYY-MM-DD HH:MM:SS
    2. YYYY-MM-DD
    3. DD/MM/YYYY
    """
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

def cargar_tabla_fechas(path_fechas):
    """Carga y procesa el archivo de calendario con las semanas epidemiológicas."""
    print(f"Intentando cargar calendario desde: {path_fechas}")
    if not os.path.exists(path_fechas):
        print(f"Error: No se encontró el archivo de calendario en la ruta: {path_fechas}")
        return None
    try:
        df_fechas = pd.read_csv(path_fechas, encoding='latin1', sep=';')
        required_cols = ['Fecha', 'Semana', 'Año_se']
        if not all(col in df_fechas.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df_fechas.columns]
            print(f"Error: El archivo de calendario no tiene las columnas requeridas. Faltan: {missing}")
            return None
        
        df_fechas = df_fechas[required_cols].copy()
        df_fechas['Fecha_dt_merge'] = parsear_fechas_robusto(df_fechas['Fecha'])
        df_fechas.dropna(subset=['Fecha_dt_merge'], inplace=True)
        return df_fechas
    except Exception as e:
        print(f"Error crítico cargando archivo de fechas: {e}")
        return None

def procesar_datos_salud_mental(df_main, df_fechas, anio):
    """Filtra y procesa los datos para el reporte de Salud Mental."""
    print("\n--- Procesando datos de Salud Mental ---")
    df_filtered = df_main[df_main['tipoprestacion'] == PRESTACION_SM].copy()
    print(f"Registros de '{PRESTACION_SM}': {len(df_filtered)}")
    
    if df_filtered.empty:
        print(f"No se encontraron registros para '{PRESTACION_SM}'")
        return None

    df_filtered['Fecha_dt_merge'] = parsear_fechas_robusto(df_filtered['fechaconsulta'])
    df_reporte = pd.merge(df_filtered, df_fechas, on='Fecha_dt_merge', how='left')
    df_reporte = df_reporte[df_reporte['Año_se'] == anio].copy()
    df_reporte.dropna(subset=['Semana'], inplace=True)
    
    if df_reporte.empty:
        print(f"No se encontraron datos para '{PRESTACION_SM}' en el año {anio}.")
        return None
    
    df_reporte['Semana'] = df_reporte['Semana'].astype(int)
    min_semana = int(df_reporte['Semana'].min())
    max_semana = int(df_reporte['Semana'].max())
    rango_semanas = pd.DataFrame({'Semana': range(min_semana, max_semana + 1)})
    
    df_total_agrupado = df_reporte.groupby('Semana').size().reset_index(name='Cantidad')
    df_total_final = pd.merge(rango_semanas, df_total_agrupado, on='Semana', how='left').fillna(0).astype(int)
    
    print(f"Análisis de Salud Mental completado para las semanas {min_semana} a {max_semana}.")
    print(f"Total de consultas de SM en {anio}: {df_total_final['Cantidad'].sum()}")

    return {
        "json_total": df_total_final.sort_values('Semana').to_json(orient='records'),
        "min_week": min_semana,
        "max_week": max_semana,
        "total_consultas": df_total_final['Cantidad'].sum()
    }

def procesar_datos_tocoginecologia(df_main, df_fechas, anio):
    """Filtra y procesa los datos para el reporte de Tocoginecología."""
    print("\n--- Procesando datos de Tocoginecología ---")
    
    df_filtered = df_main[df_main['tipoprestacion'] == PRESTACION_TOCO].copy()
    print(f"Registros de '{PRESTACION_TOCO}': {len(df_filtered)}")

    if df_filtered.empty:
        print(f"No se encontraron registros para '{PRESTACION_TOCO}'")
        return None

    # Lógica de prioridad: primero snomedterm1, si está vacía, usa snomedterm2
    t1 = df_filtered['snomedterm1'].fillna('').str.strip().str.lower()
    t2 = df_filtered['snomedterm2'].fillna('').str.strip().str.lower() if 'snomedterm2' in df_filtered.columns else ''
    df_filtered['termino_busqueda'] = t1.mask(t1 == '', t2)

    df_filtered['Fecha_dt_merge'] = parsear_fechas_robusto(df_filtered['fechaconsulta'])
    df_reporte = pd.merge(df_filtered, df_fechas, on='Fecha_dt_merge', how='left')
    df_reporte = df_reporte[df_reporte['Año_se'] == anio].copy()
    df_reporte.dropna(subset=['Semana'], inplace=True)

    if df_reporte.empty:
        print(f"No se encontraron datos para '{PRESTACION_TOCO}' en el año {anio}.")
        return None

    df_reporte['Semana'] = df_reporte['Semana'].astype(int)
    min_semana = int(df_reporte['Semana'].min())
    max_semana = int(df_reporte['Semana'].max())
    all_weeks_index = pd.Index(range(min_semana, max_semana + 1), name='Semana')
    rango_semanas_df = pd.DataFrame({'Semana': all_weeks_index})

    df_total_agrupado = df_reporte.groupby('Semana').size().reset_index(name='Cantidad')
    df_total_final = pd.merge(rango_semanas_df, df_total_agrupado, on='Semana', how='left').fillna(0)
    df_total_final['Cantidad'] = df_total_final['Cantidad'].astype(int)
    print(f"Análisis total de consultas de Toco completado para las semanas {min_semana} a {max_semana}.")

    df_snomed = df_reporte[df_reporte['termino_busqueda'].isin(TERMINOS_SNOMED_A_BUSCAR)].copy()
    
    df_snomed_final = pd.DataFrame(index=all_weeks_index)
    
    if not df_snomed.empty:
        df_snomed['TerminoAgrupado'] = df_snomed['termino_busqueda'].map(MAPEO_SNOMED)
        snomed_pivot = df_snomed.groupby(['Semana', 'TerminoAgrupado']).size().unstack(fill_value=0)
        df_snomed_final = df_snomed_final.join(snomed_pivot)
    
    for term in NOMBRES_FINALES_SNOMED:
        if term not in df_snomed_final.columns:
            df_snomed_final[term] = 0
            
    df_snomed_final.fillna(0, inplace=True)
    df_snomed_final = df_snomed_final[NOMBRES_FINALES_SNOMED].astype(int)
    df_snomed_final.reset_index(inplace=True)

    print("\n--- Conteo total de términos Snomed (Toco) ---")
    print(df_snomed_final[NOMBRES_FINALES_SNOMED].sum())
    print("-------------------------------------------\n")

    return {
        "json_total": df_total_final.sort_values('Semana').to_json(orient='records'),
        "json_snomed": df_snomed_final.sort_values('Semana').to_json(orient='records'),
        "snomed_terms": NOMBRES_FINALES_SNOMED,
        "min_week": min_semana,
        "max_week": max_semana,
        "total_consultas": df_total_final['Cantidad'].sum()
    }

def generar_html_unificado(datos_toco, datos_sm, output_path, anio):
    """Genera un único archivo HTML con panel de navegación para ambos reportes."""
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    
    toco_min_week = datos_toco['min_week'] if datos_toco else 1
    toco_max_week = datos_toco['max_week'] if datos_toco else 52
    sm_min_week = datos_sm['min_week'] if datos_sm else 1
    sm_max_week = datos_sm['max_week'] if datos_sm else 52

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

    html_template = f"""
<!DOCTYPE html>
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
            <li><a href="#sm" id="nav-sm" class="nav-link">Salud Mental</a></li>
        </ul>
    </div>

    <div class="main-content">
        <div class="fecha-actualizacion">Actualizado a {fecha_actual}</div>

        <!-- =============== PÁGINA DE TOCOGINECOLOGÍA =============== -->
        <div id="page-toco" class="page-content active">
            <div class="container">
                <h1>Guardia de Tocoginecología - Año {anio}</h1>
                {'<h3>No se encontraron datos para este reporte.</h3>' if not datos_toco else f"""
                <h2>Total de Consultas por Semana Epidemiológica</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="tocoTotalChartMinWeekSlider">Desde Semana: <span id="tocoTotalChartMinWeekValue">{toco_min_week}</span></label>
                        <input type="range" id="tocoTotalChartMinWeekSlider" min="{toco_min_week}" max="{toco_max_week}" value="{toco_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="tocoTotalChartMaxWeekSlider">Hasta Semana: <span id="tocoTotalChartMaxWeekValue">{toco_max_week}</span></label>
                        <input type="range" id="tocoTotalChartMaxWeekSlider" min="{toco_min_week}" max="{toco_max_week}" value="{toco_max_week}">
                    </div>
                </div>
                <div class="chart-container"><canvas id="tocoTotalConsultasChart"></canvas></div>
                <div class="table-wrapper table-wrapper-narrow" id="tocoTotalConsultasTableContainer"></div>

                <h2>Análisis de Términos Snomed por Semana Epidemiológica</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="tocoSnomedChartMinWeekSlider">Desde Semana: <span id="tocoSnomedChartMinWeekValue">{toco_min_week}</span></label>
                        <input type="range" id="tocoSnomedChartMinWeekSlider" min="{toco_min_week}" max="{toco_max_week}" value="{toco_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="tocoSnomedChartMaxWeekSlider">Hasta Semana: <span id="tocoSnomedChartMaxWeekValue">{toco_max_week}</span></label>
                        <input type="range" id="tocoSnomedChartMaxWeekSlider" min="{toco_min_week}" max="{toco_max_week}" value="{toco_max_week}">
                    </div>
                </div>
                <div class="chart-container"><canvas id="tocoSnomedChart"></canvas></div>
                <div class="table-wrapper" id="tocoSnomedTableContainer"></div>
                """}
            </div>
        </div>

        <!-- =============== PÁGINA DE SALUD MENTAL =============== -->
        <div id="page-sm" class="page-content">
            <div class="container">
                <h1>Guardia de Salud Mental - Año {anio}</h1>
                {'<h3>No se encontraron datos para este reporte.</h3>' if not datos_sm else f"""
                <h2>Total de Consultas por Semana Epidemiológica</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="smTotalChartMinWeekSlider">Desde Semana: <span id="smTotalChartMinWeekValue">{sm_min_week}</span></label>
                        <input type="range" id="smTotalChartMinWeekSlider" min="{sm_min_week}" max="{sm_max_week}" value="{sm_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="smTotalChartMaxWeekSlider">Hasta Semana: <span id="smTotalChartMaxWeekValue">{sm_max_week}</span></label>
                        <input type="range" id="smTotalChartMaxWeekSlider" min="{sm_min_week}" max="{sm_max_week}" value="{sm_max_week}">
                    </div>
                </div>
                <div class="chart-container"><canvas id="smTotalConsultasChart"></canvas></div>
                <div class="table-wrapper table-wrapper-narrow" id="smTotalConsultasTableContainer"></div>
                """}
            </div>
        </div>
        
        <div class="footer"><p><em>Reporte generado en el Departamento de Epidemiología y Estadística HPN - Fuente: Andes</em></p></div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function () {{
            const navLinks = document.querySelectorAll('.nav-link');
            const pages = document.querySelectorAll('.page-content');

            function switchPage(targetId) {{
                pages.forEach(page => page.classList.remove('active'));
                navLinks.forEach(link => link.classList.remove('active'));
                document.getElementById(targetId).classList.add('active');
                document.querySelector(`[href="#${{targetId.split('-')[1]}}"]`).classList.add('active');
            }}

            navLinks.forEach(link => {{
                link.addEventListener('click', (e) => {{
                    e.preventDefault();
                    const targetId = `page-${{e.target.id.split('-')[1]}}`;
                    switchPage(targetId);
                }});
            }});
            
            function updateSliderControls(minSlider, maxSlider, minValSpan, maxValSpan, changedSlider) {{
                let minW = parseInt(minSlider.value);
                let maxW = parseInt(maxSlider.value);

                if (changedSlider === minSlider && minW > maxW) {{
                    maxSlider.value = minW;
                    maxW = minW;
                }}

                if (changedSlider === maxSlider && maxW < minW) {{
                    minSlider.value = maxW;
                    minW = maxW;
                }}

                minValSpan.textContent = minW;
                maxValSpan.textContent = maxW;

                return {{ minW, maxW }};
            }}

            // ===============================================
            // ===          LÓGICA TOCOGINECOLOGÍA         ===
            // ===============================================
            const datosToco = {'true' if datos_toco else 'false'};
            if (datosToco) {{
                const ALL_TOCO_TOTAL_DATA = JSON.parse('{datos_toco["json_total"] if datos_toco else "[]"}');
                const ALL_TOCO_SNOMED_DATA = JSON.parse('{datos_toco["json_snomed"] if datos_toco else "[]"}');
                const TOCO_SNOMED_TERMS = {json.dumps(datos_toco["snomed_terms"]) if datos_toco else "[]"};

                const tocoTotalMinSlider = document.getElementById('tocoTotalChartMinWeekSlider');
                const tocoTotalMaxSlider = document.getElementById('tocoTotalChartMaxWeekSlider');
                const tocoTotalMinVal = document.getElementById('tocoTotalChartMinWeekValue');
                const tocoTotalMaxVal = document.getElementById('tocoTotalChartMaxWeekValue');
                const tocoTotalTable = document.getElementById('tocoTotalConsultasTableContainer');

                const ctxTocoTotal = document.getElementById('tocoTotalConsultasChart').getContext('2d');
                const tocoTotalChart = new Chart(ctxTocoTotal, {{
                    type: 'line',
                    data: {{ labels: [], datasets: [{{ label: 'Consultas', data: [], borderColor: '#0056b3', fill: true, backgroundColor: 'rgba(0, 86, 179, 0.1)' }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, scales: {{ y: {{ beginAtZero: true }} }} }}
                }});

                function updateTocoTotalView() {{
                    const {{ minW, maxW }} = updateSliderControls(tocoTotalMinSlider, tocoTotalMaxSlider, tocoTotalMinVal, tocoTotalMaxVal, this);
                    const filteredData = ALL_TOCO_TOTAL_DATA.filter(r => r.Semana >= minW && r.Semana <= maxW);
                    
                    tocoTotalChart.data.labels = filteredData.map(r => r.Semana);
                    tocoTotalChart.data.datasets[0].data = filteredData.map(r => r.Cantidad);
                    tocoTotalChart.update();

                    let tableHTML = '<table><thead><tr><th>Semana</th><th>Consultas</th></tr></thead><tbody>';
                    let totalSum = 0;
                    filteredData.forEach(r => {{ tableHTML += `<tr><td>${{r.Semana}}</td><td>${{r.Cantidad}}</td></tr>`; totalSum += r.Cantidad; }});
                    tableHTML += `<tr style="font-weight:bold; background-color:#f0f0f0;"><td>Total</td><td>${{totalSum}}</td></tr>`;
                    tocoTotalTable.innerHTML = tableHTML + '</tbody></table>';
                }}
                
                tocoTotalMinSlider.addEventListener('input', updateTocoTotalView);
                tocoTotalMaxSlider.addEventListener('input', updateTocoTotalView);
                
                const tocoSnomedMinSlider = document.getElementById('tocoSnomedChartMinWeekSlider');
                const tocoSnomedMaxSlider = document.getElementById('tocoSnomedChartMaxWeekSlider');
                const tocoSnomedMinVal = document.getElementById('tocoSnomedChartMinWeekValue');
                const tocoSnomedMaxVal = document.getElementById('tocoSnomedChartMaxWeekValue');
                const tocoSnomedTable = document.getElementById('tocoSnomedTableContainer');
                
                const ctxTocoSnomed = document.getElementById('tocoSnomedChart').getContext('2d');
                const tocoSnomedChart = new Chart(ctxTocoSnomed, {{
                    type: 'line',
                    data: {{ labels: [], datasets: [{snomed_datasets_str}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'top' }} }}, scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Cantidad de Registros' }} }} }} }}
                }});

                function updateTocoSnomedView() {{
                    const {{ minW, maxW }} = updateSliderControls(tocoSnomedMinSlider, tocoSnomedMaxSlider, tocoSnomedMinVal, tocoSnomedMaxVal, this);
                    const filteredData = ALL_TOCO_SNOMED_DATA.filter(r => r.Semana >= minW && r.Semana <= maxW);
                    
                    tocoSnomedChart.data.labels = filteredData.map(r => r.Semana);
                    tocoSnomedChart.data.datasets.forEach((dataset, index) => {{
                        dataset.data = filteredData.map(r => r[TOCO_SNOMED_TERMS[index]] || 0);
                    }});
                    tocoSnomedChart.update();
                    
                    let tableHTML = `<table><thead><tr><th>Semana</th>${{TOCO_SNOMED_TERMS.map(t => `<th>${{t}}</th>`).join('')}}</tr></thead><tbody>`;
                    let totals = {{}}; TOCO_SNOMED_TERMS.forEach(t => totals[t] = 0);
                    filteredData.forEach(row => {{
                        tableHTML += `<tr><td>${{row.Semana}}</td>`;
                        TOCO_SNOMED_TERMS.forEach(term => {{
                            const val = row[term] || 0;
                            tableHTML += `<td>${{val}}</td>`;
                            totals[term] += val;
                        }});
                        tableHTML += '</tr>';
                    }});
                    tableHTML += `<tr style="font-weight:bold; background-color:#f0f0f0;"><td>Total</td>${{TOCO_SNOMED_TERMS.map(t => `<td>${{totals[t]}}</td>`).join('')}}</tr>`;
                    tocoSnomedTable.innerHTML = tableHTML + '</tbody></table>';
                }}
                
                tocoSnomedMinSlider.addEventListener('input', updateTocoSnomedView);
                tocoSnomedMaxSlider.addEventListener('input', updateTocoSnomedView);
                
                updateTocoTotalView.call(tocoTotalMinSlider);
                updateTocoSnomedView.call(tocoSnomedMinSlider);
            }}

            // ===============================================
            // ===          LÓGICA SALUD MENTAL            ===
            // ===============================================
            const datosSm = {'true' if datos_sm else 'false'};
            if (datosSm) {{
                const ALL_SM_TOTAL_DATA = JSON.parse('{datos_sm["json_total"] if datos_sm else "[]"}');
                
                const smTotalMinSlider = document.getElementById('smTotalChartMinWeekSlider');
                const smTotalMaxSlider = document.getElementById('smTotalChartMaxWeekSlider');
                const smTotalMinVal = document.getElementById('smTotalChartMinWeekValue');
                const smTotalMaxVal = document.getElementById('smTotalChartMaxWeekValue');
                const smTotalTable = document.getElementById('smTotalConsultasTableContainer');

                const ctxSmTotal = document.getElementById('smTotalConsultasChart').getContext('2d');
                const smTotalChart = new Chart(ctxSmTotal, {{
                    type: 'line',
                    data: {{ labels: [], datasets: [{{ label: 'Consultas', data: [], borderColor: '#0056b3', fill: true, backgroundColor: 'rgba(0, 86, 179, 0.1)' }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, scales: {{ y: {{ beginAtZero: true }} }} }}
                }});

                function updateSmTotalView() {{
                    const {{ minW, maxW }} = updateSliderControls(smTotalMinSlider, smTotalMaxSlider, smTotalMinVal, smTotalMaxVal, this);
                    const filteredData = ALL_SM_TOTAL_DATA.filter(r => r.Semana >= minW && r.Semana <= maxW);
                    
                    smTotalChart.data.labels = filteredData.map(r => r.Semana);
                    smTotalChart.data.datasets[0].data = filteredData.map(r => r.Cantidad);
                    smTotalChart.update();

                    let tableHTML = '<table><thead><tr><th>Semana</th><th>Consultas</th></tr></thead><tbody>';
                    let totalSum = 0;
                    filteredData.forEach(r => {{ tableHTML += `<tr><td>${{r.Semana}}</td><td>${{r.Cantidad}}</td></tr>`; totalSum += r.Cantidad; }});
                    tableHTML += `<tr style="font-weight:bold; background-color:#f0f0f0;"><td>Total</td><td>${{totalSum}}</td></tr>`;
                    smTotalTable.innerHTML = tableHTML + '</tbody></table>';
                }}

                smTotalMinSlider.addEventListener('input', updateSmTotalView);
                smTotalMaxSlider.addEventListener('input', updateSmTotalView);
                
                updateSmTotalView.call(smTotalMinSlider);
            }}
        }});
    </script>
</body>
</html>
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        print(f"\nReporte HTML unificado generado exitosamente en: {output_path}")
    except Exception as e:
        print(f"Error al guardar el reporte HTML: {e}")

# ================================== #
# ===     EJECUCIÓN PRINCIPAL    === #
# ================================== #
if __name__ == "__main__":
    print(f"--- INICIO DEL ANÁLISIS CONSOLIDADO DE GUARDIAS (AÑO {ANIO_REPORTE}) ---")

    if not os.path.isdir(CARPETA_DATOS):
        print(f"Error: No se encontró la carpeta de datos: {CARPETA_DATOS}"); exit()
    
    archivos_csv = [f for f in os.listdir(CARPETA_DATOS) if f.lower().endswith('.csv')]
    if not archivos_csv:
        print(f"No se encontraron archivos CSV en la carpeta {CARPETA_DATOS}"); exit()

    print(f"\nProcesando {len(archivos_csv)} archivos desde '{CARPETA_DATOS}'...")
    lista_dfs = []
    columnas_requeridas = ['idturno', 'fechaconsulta', 'tipoprestacion'] 

    for archivo in archivos_csv:
        path_completo = os.path.join(CARPETA_DATOS, archivo)
        try:
            df_temp = pd.read_csv(path_completo, encoding='utf-8-sig', sep=';', on_bad_lines='warn', low_memory=False)
            
            if not all(col in df_temp.columns for col in columnas_requeridas):
                missing_cols = set(columnas_requeridas) - set(df_temp.columns)
                print(f"  - ¡Advertencia! Saltando '{archivo}' por faltar columnas básicas: {missing_cols}")
                continue
            
            lista_dfs.append(df_temp)
        except Exception as e:
            print(f"  - Error leyendo el archivo '{archivo}': {e}\n{traceback.format_exc()}")

    if not lista_dfs:
        print("\nNo se pudo procesar ningún archivo CSV válido. Proceso detenido."); exit()

    df_main = pd.concat(lista_dfs, ignore_index=True)
    print(f"\nTotal de registros combinados: {len(df_main)}")
    df_main.drop_duplicates(subset=['idturno'], keep='first', inplace=True)
    print(f"Registros después de eliminar duplicados por 'idturno': {len(df_main)}")

    df_fechas = cargar_tabla_fechas(PATH_FECHAS)
    if df_fechas is None:
        print("Proceso detenido por falta de archivo de calendario."); exit()

    datos_reporte_toco = procesar_datos_tocoginecologia(df_main, df_fechas, ANIO_REPORTE)
    datos_reporte_sm = procesar_datos_salud_mental(df_main, df_fechas, ANIO_REPORTE)

    if not datos_reporte_toco and not datos_reporte_sm:
        print("\nNo se encontraron datos para ningún reporte. No se generará el archivo HTML."); exit()
        
    generar_html_unificado(
        datos_toco=datos_reporte_toco,
        datos_sm=datos_reporte_sm,
        output_path=PATH_HTML_OUTPUT,
        anio=ANIO_REPORTE
    )

    print("\n--- PROCESO COMPLETADO ---")