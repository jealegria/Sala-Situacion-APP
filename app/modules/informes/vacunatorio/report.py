"""
report.py — Informe de Vacunatorio
===================================
Toda la logica de consolidacion y generacion del informe HTML de Vacunatorio
(Agendas, Fuera de Agenda, Internacion y Mapeo SNOMED).
La UI (app/ui/pages/informes/vacunatorio.py) solo llama a generar_informe().

Para modificar el informe en el futuro, editar SOLO este archivo.

Rutas por defecto:
  - Agendas        : C:\\02_HPN\\01_Base\\agendas_consolidado
  - Fuera Agenda   : C:\\02_HPN\\01_Base\\fuera_agenda
  - Internacion    : C:\\02_HPN\\01_Base\\internacion_andes
  - Mapeo SNOMED   : C:\\02_HPN\\01_Base\\tablas_relacionales\\conceptos_snomed_vacunatorio.csv
  - Output         : C:\\03_Apps\\Sala-Situacion-APP\\Outputs\\informes
"""
from pathlib import Path
from datetime import datetime
from typing import Callable
import unicodedata
import re
import json

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES — editar aqui para cambiar comportamiento
# ══════════════════════════════════════════════════════════════

DEFAULT_INPUT_AGENDAS       = Path(r"C:\02_HPN\01_Base\agendas_consolidado")
DEFAULT_INPUT_FUERA_AGENDA  = Path(r"C:\02_HPN\01_Base\fuera_agenda")
DEFAULT_INPUT_INTERNACION   = Path(r"C:\02_HPN\01_Base\internacion_andes")
DEFAULT_TABLAS_RELACIONALES = Path(r"C:\02_HPN\01_Base\tablas_relacionales")
MAPEO_FILENAME              = "conceptos_snomed_vacunatorio.csv"
DEFAULT_OUTPUT_PATH         = Path(r"C:\03_Apps\Sala-Situacion-APP\Outputs\informes")

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════

def normalizar(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def clean_localidad(loc):
    if pd.isna(loc) or str(loc).strip() == "":
        return "(Sin dato)"
    loc_str = str(loc).strip()
    loc_str = remove_accents(loc_str)
    return loc_str.title()


def procesar_edad(row):
    edad_raw = row.get("edad")
    uniedad_raw = row.get("uniedad")

    if pd.isna(edad_raw) or str(edad_raw).strip() == "":
        return "(Sin dato)", "(Sin dato)"

    nums = re.findall(r"\d+", str(edad_raw))
    if not nums:
        return "(Sin dato)", "(Sin dato)"
    edad_num = int(nums[0])

    uni = str(uniedad_raw).strip().upper() if pd.notna(uniedad_raw) else "A"

    if uni in ["D", "DIAS", "DIA", "M", "MES", "MESES"]:
        return "<1", "<1"

    if edad_num < 1:
        return "<1", "<1"

    edad_anos = edad_num

    if edad_anos <= 10:
        rango = "1 - 10"
    elif edad_anos <= 20:
        rango = "11 - 20"
    elif edad_anos <= 30:
        rango = "21 - 30"
    elif edad_anos <= 40:
        rango = "31 - 40"
    elif edad_anos <= 50:
        rango = "41 - 50"
    elif edad_anos <= 60:
        rango = "51 - 60"
    elif edad_anos <= 70:
        rango = "61 - 70"
    elif edad_anos <= 80:
        rango = "71 - 80"
    else:
        rango = "81+"

    return f"{edad_anos}", rango


def determinar_tipo_prestacion(row, mapeo_snomed: dict):
    primer_concepto = None
    for col in ["snomedterm1", "snomedterm2", "snomedterm3"]:
        term = row.get(col)
        if pd.notna(term) and str(term).strip() != "":
            primer_concepto = str(term).strip()
            break

    if not primer_concepto:
        return "Sin registrar"

    if primer_concepto in mapeo_snomed:
        val = mapeo_snomed[primer_concepto]
        val_norm = str(val).strip().lower()
        if val_norm in ["vacunacion", "vacunación"]:
            return "Vacunación"
        if val_norm in ["recaptacion", "recaptación"]:
            return "Recaptación"
        return val

    return "Otro"


def extraer_hora(val):
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    match = re.search(r"(\d{1,2}):(\d{2})", val_str)
    if match:
        hora = int(match.group(1))
        minuto = int(match.group(2))
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return f"{hora:02d}:{minuto:02d}"
    return ""


# ══════════════════════════════════════════════════════════════
#  PLANTILLA HTML
# ══════════════════════════════════════════════════════════════

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Panel poblacional - Vacunatorio __ANIO__</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>

body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f4f7fa;
    margin: 0;
    padding: 40px 20px;
    color: #222;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.container {
    width: 100%;
    max-width: 950px;
}

h1 {
    color: #1d4f7a;
    margin-bottom: 5px;
    text-align: center;
}

.periodo {
    text-align: center;
    color: #666;
    font-size: 14px;
    margin-top: 5px;
    margin-bottom: 25px;
    font-weight: 500;
}

.panel {
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin-top: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}

.panel-select {
    padding: 20px;
}

.selector-group {
    display: flex;
    gap: 15px;
    justify-content: space-between;
    flex-wrap: wrap;
}

.selector-item {
    flex: 1;
    min-width: 200px;
    display: flex;
    flex-direction: column;
}

.selector-item label {
    margin-bottom: 8px;
    font-weight: bold;
    color: #1d4f7a;
    font-size: 14px;
}

select {
    padding: 10px;
    width: 100%;
    font-size: 14px;
    border: 1px solid #ccc;
    border-radius: 6px;
    background-color: white;
    box-sizing: border-box;
}

.kpis {
    display: flex;
    gap: 15px;
    margin-top: 20px;
    justify-content: space-between;
}

.kpi {
    background: white;
    padding: 20px 10px;
    border-radius: 12px;
    flex: 1;
    text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    min-width: 150px;
}

.kpi-label {
    font-size: 12px;
    color: #666;
    margin-bottom: 5px;
}

.kpi-value {
    font-size: 30px;
    font-weight: bold;
    color: #1d4f7a;
}

.chart-container {
    position: relative;
    height: 250px;
    width: 100%;
    margin-top: 15px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
}

th {
    background: #1d4f7a;
    color: white;
    text-align: left;
    padding: 10px;
}

td {
    padding: 8px;
    border-bottom: 1px solid #ddd;
}

.poblacion-grid {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-top: 20px;
    width: 100%;
}

.poblacion-grid .panel {
    width: 100%;
    margin-top: 0;
}

.table-scroll {
    max-height: 260px;
    overflow-y: auto;
    margin-top: 10px;
    border: 1px solid #eee;
    border-radius: 6px;
}

.table-scroll table {
    margin-top: 0;
}

.table-scroll th {
    position: sticky;
    top: 0;
    z-index: 1;
}

</style>
</head>

<body>

<div class="container">

    <h1>Panel Vacunatorio __ANIO__</h1>
    <div class="periodo">Período analizado: __PERIODO_ANALIZADO__</div>

    <div class="panel panel-select">
        <div class="selector-group">
            <div class="selector-item">
                <label for="origen">Origen de Datos</label>
                <select id="origen">
                    <option value="(Todos)">Todos</option>
                    <option value="agenda">Agenda</option>
                    <option value="fuera_agenda">Fuera de Agenda</option>
                </select>
            </div>
            <div class="selector-item">
                <label for="mes">Mes</label>
                <select id="mes"></select>
            </div>
            <div class="selector-item">
                <label for="prestacion">Tipo de Prestación</label>
                <select id="prestacion"></select>
            </div>
            <div class="selector-item">
                <label for="franja">Franja Horaria</label>
                <select id="franja">
                    <option value="(Todas)">Todas</option>
                    <option value="8-14">8 - 14 hs</option>
                    <option value="14-20">14 - 20 hs</option>
                </select>
            </div>
        </div>
    </div>

    <div class="kpis">
        <div class="kpi">
            <div class="kpi-label">Prestaciones totales</div>
            <div class="kpi-value" id="total">0</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Pacientes únicos</div>
            <div class="kpi-value" id="pacientes">0</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Prestaciones prom. día</div>
            <div class="kpi-value" id="promedio">0</div>
        </div>
    </div>

    <div class="panel">
        <h3 style="margin-top: 0; text-align: center; color: #1d4f7a;" id="titulo-grafico">Prestaciones por mes</h3>
        <div class="chart-container">
            <canvas id="grafico"></canvas>
        </div>
    </div>

    <div class="panel">
        <h3 style="margin-top: 0; color: #1d4f7a;">Tipos de prestación (Agrupación SNOMED)</h3>
        <table id="tabla">
            <thead>
                <tr>
                    <th>Prestación</th>
                    <th>Prestaciones</th>
                    <th>Pacientes</th>
                    <th>Frecuencia Prestaciones %</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    </div>

    <hr style="border: 0; border-top: 1px solid #ccc; margin: 40px 0 20px 0; width: 100%;">

    <h2 style="color: #1d4f7a; text-align: center; margin-top: 0; margin-bottom: 5px;">Población</h2>
    
    <div class="poblacion-grid">
        <div class="panel">
            <h3 style="margin-top: 0; color: #1d4f7a;">Distribución por Localidad</h3>
            <div class="table-scroll">
                <table id="tabla-localidades">
                    <thead>
                        <tr>
                            <th>Localidad</th>
                            <th>Prestaciones</th>
                            <th>Pacientes</th>
                            <th>Frecuencia Prestaciones %</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>

        <div class="panel">
            <h3 style="margin-top: 0; color: #1d4f7a;">Distribución por Edad</h3>
            <table id="tabla-edades">
                <thead>
                    <tr>
                        <th>Rango de Edad</th>
                        <th>Prestaciones</th>
                        <th>Pacientes</th>
                        <th>Frecuencia Prestaciones %</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    <div style="text-align: center; color: #888; font-size: 12px; margin-top: 30px; margin-bottom: 10px;">
        Elaborado por el Servicio de Epidemiología HPN
    </div>

</div>

<script>

const registros = __REGISTROS_JSON__;

const nombresMeses = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
};

const mesesCortos = [
    "Ene","Feb","Mar","Abr","May","Jun",
    "Jul","Ago","Sep","Oct","Nov","Dic"
];

const comboOrigen = document.getElementById("origen");
const comboMes = document.getElementById("mes");
const comboPrest = document.getElementById("prestacion");
const comboFranja = document.getElementById("franja");

const mesesConDatos = [...new Set(registros.map(r => r.m))].sort((a, b) => a - b);
let optAllMes = document.createElement("option");
optAllMes.value = "(Todos)";
optAllMes.textContent = "Todos";
comboMes.appendChild(optAllMes);

mesesConDatos.forEach(m => {
    let opt = document.createElement("option");
    opt.value = m;
    opt.textContent = nombresMeses[m] || "Mes " + m;
    comboMes.appendChild(opt);
});

const listaPrestaciones = [...new Set(registros.map(r => r.t).filter(t => t !== ""))].sort();
let optAllPrest = document.createElement("option");
optAllPrest.value = "(Todas)";
optAllPrest.textContent = "Todas";
comboPrest.appendChild(optAllPrest);

listaPrestaciones.forEach(t => {
    let opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    comboPrest.appendChild(opt);
});

let chart = null;

const ordenRangosEdad = {
    "<1": 1,
    "1 - 10": 2,
    "11 - 20": 3,
    "21 - 30": 4,
    "31 - 40": 5,
    "41 - 50": 6,
    "51 - 60": 7,
    "61 - 70": 8,
    "71 - 80": 9,
    "81+": 10,
    "(Sin dato)": 11
};

function actualizar() {
    const selOrigen = comboOrigen.value;
    const selMes = comboMes.value;
    const selPrest = comboPrest.value;
    const selFranja = comboFranja.value;

    let filtrados = registros;

    if (selOrigen !== "(Todos)") {
        filtrados = filtrados.filter(r => r.o === selOrigen);
    }
    if (selMes !== "(Todos)") {
        const mesInt = parseInt(selMes, 10);
        filtrados = filtrados.filter(r => r.m === mesInt);
    }
    if (selPrest !== "(Todas)") {
        filtrados = filtrados.filter(r => r.t === selPrest);
    }
    if (selFranja !== "(Todas)") {
        filtrados = filtrados.filter(r => {
            if (!r.h) return false;
            const partes = r.h.split(":");
            const horaNum = parseInt(partes[0], 10);
            if (selFranja === "8-14") {
                return horaNum >= 8 && horaNum < 14;
            } else if (selFranja === "14-20") {
                return horaNum >= 14 && horaNum < 20;
            }
            return true;
        });
    }

    const total = filtrados.length;
    const diasUnicos = new Set(filtrados.map(r => r.f));
    const cantDias = diasUnicos.size;
    const promedio = cantDias > 0 ? Math.round(total / cantDias) : 0;

    const dnisValidos = filtrados
        .map(r => r.d)
        .filter(d => d && d !== "" && d.toLowerCase() !== "nan" && d.toLowerCase() !== "none" && d.toLowerCase() !== "null" && d.toLowerCase() !== "(sin dato)");
    const pacientesUnicosCount = new Set(dnisValidos).size;

    document.getElementById("promedio").innerText = promedio;
    document.getElementById("total").innerText = total;
    document.getElementById("pacientes").innerText = pacientesUnicosCount;

    if (chart) {
        chart.destroy();
    }

    const cuentasMensuales = Array(13).fill(0);
    filtrados.forEach(r => {
        cuentasMensuales[r.m]++;
    });

    const labelsGrafico = [];
    const dataGrafico = [];

    mesesCortos.forEach((mesCorto, index) => {
        const numMes = index + 1;
        const totalMes = cuentasMensuales[numMes];

        if (selMes === "(Todos)") {
            if (totalMes > 0) {
                labelsGrafico.push(mesCorto);
                dataGrafico.push(totalMes);
            }
        } else {
            if (numMes === parseInt(selMes, 10)) {
                labelsGrafico.push(mesCorto);
                dataGrafico.push(totalMes);
            }
        }
    });

    const ctx = document.getElementById("grafico");
    chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labelsGrafico,
            datasets: [{
                label: 'Prestaciones',
                data: dataGrafico,
                backgroundColor: '#1d4f7a',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });

    const titGrafico = document.getElementById("titulo-grafico");
    if (selMes !== "(Todos)") {
        titGrafico.innerText = "Detalle del mes de " + nombresMeses[parseInt(selMes, 10)];
    } else {
        titGrafico.innerText = "Prestaciones por mes";
    }

    const tbody = document.querySelector("#tabla tbody");
    tbody.innerHTML = "";

    const conteoPrestaciones = {};
    filtrados.forEach(r => {
        const prest = r.t || "(Sin dato)";
        if (!conteoPrestaciones[prest]) {
            conteoPrestaciones[prest] = { cant: 0, dnis: new Set() };
        }
        conteoPrestaciones[prest].cant++;

        const dni = r.d;
        if (dni && dni !== "" && dni.toLowerCase() !== "nan" && dni.toLowerCase() !== "none" && dni.toLowerCase() !== "null" && dni.toLowerCase() !== "(sin dato)") {
            conteoPrestaciones[prest].dnis.add(dni);
        }
    });

    const arrayTabla = Object.entries(conteoPrestaciones)
        .map(([prestacion, info]) => ({
            prestacion,
            cantidad: info.cant,
            pacientes: info.dnis.size,
            frecuencia: total > 0 ? Math.round((info.cant / total) * 1000) / 10 : 0
        }))
        .sort((a, b) => b.cantidad - a.cantidad);

    arrayTabla.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML =
            "<td>" + r.prestacion + "</td>" +
            "<td>" + r.cantidad + "</td>" +
            "<td>" + r.pacientes + "</td>" +
            "<td>" + r.frecuencia + "%</td>";
        tbody.appendChild(tr);
    });

    const tbodyLoc = document.querySelector("#tabla-localidades tbody");
    tbodyLoc.innerHTML = "";

    const conteoLocalidades = {};
    filtrados.forEach(r => {
        const loc = r.l || "(Sin dato)";
        if (!conteoLocalidades[loc]) {
            conteoLocalidades[loc] = { cant: 0, dnis: new Set() };
        }
        conteoLocalidades[loc].cant++;

        const dni = r.d;
        if (dni && dni !== "" && dni.toLowerCase() !== "nan" && dni.toLowerCase() !== "none" && dni.toLowerCase() !== "null" && dni.toLowerCase() !== "(sin dato)") {
            conteoLocalidades[loc].dnis.add(dni);
        }
    });

    const arrayLocalidades = Object.entries(conteoLocalidades)
        .map(([localidad, info]) => ({
            localidad,
            cantidad: info.cant,
            pacientes: info.dnis.size,
            frecuencia: total > 0 ? Math.round((info.cant / total) * 1000) / 10 : 0
        }))
        .sort((a, b) => b.cantidad - a.cantidad);

    arrayLocalidades.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML =
            "<td>" + r.localidad + "</td>" +
            "<td>" + r.cantidad + "</td>" +
            "<td>" + r.pacientes + "</td>" +
            "<td>" + r.frecuencia + "%</td>";
        tbodyLoc.appendChild(tr);
    });

    const tbodyEdad = document.querySelector("#tabla-edades tbody");
    tbodyEdad.innerHTML = "";

    const conteoEdades = {};
    filtrados.forEach(r => {
        const rango = r.er || "(Sin dato)";
        if (!conteoEdades[rango]) {
            conteoEdades[rango] = { cant: 0, dnis: new Set() };
        }
        conteoEdades[rango].cant++;

        const dni = r.d;
        if (dni && dni !== "" && dni.toLowerCase() !== "nan" && dni.toLowerCase() !== "none" && dni.toLowerCase() !== "null" && dni.toLowerCase() !== "(sin dato)") {
            conteoEdades[rango].dnis.add(dni);
        }
    });

    const arrayEdades = Object.entries(conteoEdades)
        .map(([rango, info]) => ({
            rango,
            cantidad: info.cant,
            pacientes: info.dnis.size,
            frecuencia: total > 0 ? Math.round((info.cant / total) * 1000) / 10 : 0
        }))
        .sort((a, b) => {
            const ordA = ordenRangosEdad[a.rango] || 99;
            const ordB = ordenRangosEdad[b.rango] || 99;
            return ordA - ordB;
        });

    arrayEdades.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML =
            "<td>" + r.rango + "</td>" +
            "<td>" + r.cantidad + "</td>" +
            "<td>" + r.pacientes + "</td>" +
            "<td>" + r.frecuencia + "%</td>";
        tbodyEdad.appendChild(tr);
    });
}

comboOrigen.addEventListener("change", actualizar);
comboMes.addEventListener("change", actualizar);
comboPrest.addEventListener("change", actualizar);
comboFranja.addEventListener("change", actualizar);

comboOrigen.selectedIndex = 0;
comboMes.selectedIndex = 0;
comboPrest.selectedIndex = 0;
comboFranja.selectedIndex = 0;
actualizar();

</script>

</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════

def generar_informe(
    input_agendas: Path,
    input_fuera_agenda: Path,
    output_path: Path,
    log: LogFn,
    anio: int = 2026,
    input_internacion: Path | None = None,
    path_mapeo: Path | None = None,
) -> Path | None:
    """
    Consolida las prestaciones de Vacunatorio y genera el panel HTML poblacional.

    Args:
        input_agendas:      Carpeta de agendas consolidadas.
        input_fuera_agenda: Carpeta de prestaciones fuera de agenda.
        output_path:        Carpeta de salida del informe.
        log:                Callback para mensajes en consola.
        anio:               Año de reporte para filtrar.
        input_internacion:  Carpeta de internacion_andes (opcional).
        path_mapeo:         Ruta a conceptos_snomed_vacunatorio.csv o carpeta contenedora.
    """
    log("=" * 60)
    log(f"  INFORME DE VACUNATORIO — AÑO {anio}")
    log("=" * 60)
    log(f"  Agendas          : {input_agendas}")
    log(f"  Fuera de Agenda  : {input_fuera_agenda}")
    if input_internacion:
        log(f"  Internacion      : {input_internacion}")
    log(f"  Carpeta de Salida: {output_path}")

    # 1. Cargar Mapeo SNOMED
    if path_mapeo is None:
        cand1 = input_agendas.parent / "tablas_relacionales" / MAPEO_FILENAME
        cand2 = DEFAULT_TABLAS_RELACIONALES / MAPEO_FILENAME
        if cand1.exists():
            archivo_mapeo = cand1
        elif cand2.exists():
            archivo_mapeo = cand2
        else:
            archivo_mapeo = cand1
    elif path_mapeo.is_dir():
        archivo_mapeo = path_mapeo / MAPEO_FILENAME
    else:
        archivo_mapeo = path_mapeo

    mapeo_snomed = {}
    if archivo_mapeo.exists():
        log(f"\n  Cargando mapeo SNOMED desde: {archivo_mapeo.name}")
        try:
            df_map = pd.read_csv(archivo_mapeo, sep=";", encoding="utf-8-sig", dtype=str)
        except Exception:
            df_map = pd.read_csv(archivo_mapeo, sep=";", encoding="latin1", dtype=str)

        if "term" in df_map.columns and "tipo" in df_map.columns:
            mapeo_snomed = dict(zip(df_map["term"].astype(str).str.strip(), df_map["tipo"].astype(str).str.strip()))
            log(f"  [OK] Mapeo cargado: {len(mapeo_snomed):,} conceptos.")
        else:
            log(f"  [WARN] El archivo no tiene columnas 'term' y 'tipo'.")
    else:
        log(f"  [WARN] No se encontro el archivo de mapeo en: {archivo_mapeo}")

    # 2. Lectura - Agendas
    log("\n--- Lectura: Agendas Consolidadas ---")
    dfs_agendas = []
    if input_agendas.exists():
        archivos_ag = sorted(input_agendas.glob("*.csv"))
        log(f"  Encontrados {len(archivos_ag)} archivo(s) en agendas.")
        for archivo in archivos_ag:
            try:
                df_tmp = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False)
            except Exception:
                df_tmp = pd.read_csv(archivo, sep=";", encoding="latin1", dtype=str, low_memory=False)
            dfs_agendas.append(df_tmp)
            log(f"    [OK] {archivo.name} ({len(df_tmp):,} filas)")

    if dfs_agendas:
        df_ag = pd.concat(dfs_agendas, ignore_index=True)
        for col in ["localidad", "edad", "uniedad", "tipoprestacion", "idturno", "dni", "apellido", "horaturno", "snomedterm1", "snomedterm2", "snomedterm3"]:
            if col not in df_ag.columns:
                df_ag[col] = ""

        df_ag["fechaconsulta"] = pd.to_datetime(
            df_ag["fechaconsulta"].astype(str).str.strip(),
            format="mixed",
            dayfirst=True,
            errors="coerce"
        )
        df_ag = df_ag.dropna(subset=["fechaconsulta"]).copy()
        df_ag = df_ag[df_ag["fechaconsulta"].dt.year == anio]

        if "idturno" in df_ag.columns and df_ag["idturno"].astype(str).str.strip().any():
            df_ag = df_ag.drop_duplicates(subset="idturno")

        df_ag["origen"] = "agenda"
        df_ag["hora_raw"] = df_ag["horaturno"]
        df_ag = df_ag[["fechaconsulta", "tipoprestacion", "localidad", "edad", "uniedad", "origen", "dni", "apellido", "hora_raw", "snomedterm1", "snomedterm2", "snomedterm3"]].copy()
        log(f"  Registros validos de agendas ({anio}): {len(df_ag):,}")
    else:
        df_ag = pd.DataFrame(columns=["fechaconsulta", "tipoprestacion", "localidad", "edad", "uniedad", "origen", "dni", "apellido", "hora_raw", "snomedterm1", "snomedterm2", "snomedterm3"])
        log(f"  [INFO] Sin datos de agendas.")

    # 3. Lectura - Fuera de Agenda
    log("\n--- Lectura: Fuera de Agenda ---")
    dfs_fuera = []
    if input_fuera_agenda.exists():
        archivos_fu = sorted(input_fuera_agenda.glob("*.csv"))
        log(f"  Encontrados {len(archivos_fu)} archivo(s) en fuera de agenda.")
        for archivo in archivos_fu:
            try:
                df_tmp = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False)
            except Exception:
                df_tmp = pd.read_csv(archivo, sep=";", encoding="latin1", dtype=str, low_memory=False)
            dfs_fuera.append(df_tmp)
            log(f"    [OK] {archivo.name} ({len(df_tmp):,} filas)")

    if dfs_fuera:
        df_fu = pd.concat(dfs_fuera, ignore_index=True)
        for col in ["localidad", "edad", "uniedad", "tipoprestacion", "idprestacion", "dni", "apellido", "horaconsulta", "snomedterm1", "snomedterm2", "snomedterm3"]:
            if col not in df_fu.columns:
                df_fu[col] = ""

        df_fu["fechaconsulta"] = pd.to_datetime(
            df_fu["fechaconsulta"].astype(str).str.strip(),
            format="mixed",
            dayfirst=True,
            errors="coerce"
        )
        df_fu = df_fu.dropna(subset=["fechaconsulta"]).copy()
        df_fu = df_fu[df_fu["fechaconsulta"].dt.year == anio]

        if "idprestacion" in df_fu.columns and df_fu["idprestacion"].astype(str).str.strip().any():
            df_fu = df_fu.drop_duplicates(subset="idprestacion")

        df_fu["origen"] = "fuera_agenda"
        df_fu["hora_raw"] = df_fu["horaconsulta"]
        df_fu = df_fu[["fechaconsulta", "tipoprestacion", "localidad", "edad", "uniedad", "origen", "dni", "apellido", "hora_raw", "snomedterm1", "snomedterm2", "snomedterm3"]].copy()
        log(f"  Registros validos de fuera de agenda ({anio}): {len(df_fu):,}")
    else:
        df_fu = pd.DataFrame(columns=["fechaconsulta", "tipoprestacion", "localidad", "edad", "uniedad", "origen", "dni", "apellido", "hora_raw", "snomedterm1", "snomedterm2", "snomedterm3"])
        log(f"  [INFO] Sin datos de fuera de agenda.")

    # 4. Consolidación y Filtrado por Vacunatorio
    log("\n--- Consolidacion y Depuracion ---")
    df = pd.concat([df_ag, df_fu], ignore_index=True)
    log(f"  Total filas combinadas: {len(df):,}")

    if df.empty:
        log("  [ERROR] No hay registros cargados para procesar.")
        return None

    df["tipoprestacion_clean"] = df["tipoprestacion"].fillna("").astype(str).str.strip().str.lower()
    df_vac = df[df["tipoprestacion_clean"] == "procedimientos realizados en vacunatorio"].copy().reset_index(drop=True)
    log(f"  Prestaciones en vacunatorio antes de depurar: {len(df_vac):,}")

    if df_vac.empty:
        log("  [WARN] No se encontraron prestaciones correspondientes a 'procedimientos realizados en vacunatorio'.")
        return None

    # Depuración
    dni_vacio = df_vac["dni"].fillna("").astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "(sin dato)"])
    apellido_vacio = df_vac["apellido"].fillna("").astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "(sin dato)"])
    sin_identificacion = dni_vacio & apellido_vacio
    df_vac = df_vac[~sin_identificacion].copy().reset_index(drop=True)

    term1_vacio = df_vac["snomedterm1"].fillna("").astype(str).str.strip() == ""
    term2_vacio = df_vac["snomedterm2"].fillna("").astype(str).str.strip() == ""
    term3_vacio = df_vac["snomedterm3"].fillna("").astype(str).str.strip() == ""
    snomed_totalmente_vacio = term1_vacio & term2_vacio & term3_vacio
    dni_vacio_post = df_vac["dni"].fillna("").astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "(sin dato)"])
    apellido_vacio_post = df_vac["apellido"].fillna("").astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "(sin dato)"])
    turnos_fantasmas = (dni_vacio_post & apellido_vacio_post) & snomed_totalmente_vacio
    df_vac = df_vac[~turnos_fantasmas].copy().reset_index(drop=True)

    df_vac = df_vac.drop_duplicates()
    log(f"  Prestaciones depuradas finales: {len(df_vac):,}")

    # Procesamiento de variables
    df_vac["tipoprestacion_mapeada"] = df_vac.apply(lambda r: determinar_tipo_prestacion(r, mapeo_snomed), axis=1)
    df_vac["hora_clean"] = df_vac["hora_raw"].apply(extraer_hora)

    min_fecha = df_vac["fechaconsulta"].min()
    max_fecha = df_vac["fechaconsulta"].max()
    periodo_analizado = f"{min_fecha.strftime('%d/%m/%Y')} al {max_fecha.strftime('%d/%m/%Y')}"
    log(f"  Periodo analizado: {periodo_analizado}")

    df_vac["localidad_clean"] = df_vac["localidad"].apply(clean_localidad)
    edad_procesada = df_vac.apply(procesar_edad, axis=1)
    df_vac["edad_clean"] = [x[0] for x in edad_procesada]
    df_vac["edad_rango"] = [x[1] for x in edad_procesada]
    df_vac["dni_clean"] = df_vac["dni"].fillna("").astype(str).str.strip()

    df_vac["mes"] = df_vac["fechaconsulta"].dt.month
    df_vac["fecha_str"] = df_vac["fechaconsulta"].dt.strftime("%Y-%m-%d")

    df_json = df_vac[["origen", "mes", "tipoprestacion_mapeada", "fecha_str", "hora_clean", "localidad_clean", "edad_clean", "edad_rango", "dni_clean"]].copy()
    df_json.columns = ["o", "m", "t", "f", "h", "l", "e", "er", "d"]
    registros_lista = df_json.to_dict(orient="records")

    # 5. Generar archivo HTML
    log("\n--- Generacion de Reporte HTML ---")
    fecha_actual = datetime.now().strftime("%d_%m")
    html_salida = output_path / f"vacunatorio_poblacion_{fecha_actual}.html"

    html = (
        HTML_TEMPLATE
        .replace("__ANIO__", str(anio))
        .replace("__PERIODO_ANALIZADO__", periodo_analizado)
        .replace("__REGISTROS_JSON__", json.dumps(registros_lista, ensure_ascii=False))
    )

    output_path.mkdir(parents=True, exist_ok=True)
    html_salida.write_text(html, encoding="utf-8")

    log("=" * 60)
    log("  PROCESO FINALIZADO EXITOSAMENTE")
    log(f"  Reporte generado en : {html_salida}")
    log("=" * 60)
    return html_salida
