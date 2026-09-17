# ================================== #
# ===        IMPORTACIONES         === #
# ================================== #
import os
import re
import pandas as pd
import traceback
import json
from datetime import datetime as dt_datetime
from datetime import date
import base64
import warnings


# ================================== #
# === CONFIGURACIÓN Y ORIGEN DE DATOS === #
# ================================== #
RUTA_BASE = r"C:\Users\usuario\Desktop\base" 
ANIO_REPORTE = 2026 # <<--- AJUSTAR ESTE AÑO PARA FILTRAR LOS DATOS POR Año_se
PATH_FECHAS = os.path.join(RUTA_BASE, "tablas_relacionales", "calendario_se.csv")
CARPETA_ADULTOS = os.path.join(RUTA_BASE, "adultos")
CARPETA_PEDIATRIA = os.path.join(RUTA_BASE, "pediatria")
CARPETA_RESULTADOS_CSV = os.path.join(RUTA_BASE, "resultados_combinados")
CARPETA_REPORTE_HTML = r"C:\Users\usuario\Desktop\Juan\scripts para reportes\output"
PATH_LOGO = os.path.join(RUTA_BASE, "logo_hospital.png")


# ================================== #
# ===   FUNCIONES AUXILIARES     === #
# ================================== #

def cargar_tabla_fechas(path_fechas):
    print(f"Intentando cargar calendario desde: {path_fechas}")
    try:
        df_fechas = pd.read_csv(path_fechas, encoding='latin1', sep=';')
        required_cols = ['Fecha', 'Semana', 'Año_se']
        if not all(col in df_fechas.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df_fechas.columns]
            print(f"Error: El archivo de calendario no tiene las columnas requeridas. Faltan: {missing}")
            return None
        df_fechas = df_fechas[required_cols].copy()
        df_fechas['Fecha'] = pd.to_datetime(df_fechas['Fecha'], dayfirst=True, errors='coerce')
        df_fechas['Año_se'] = pd.to_numeric(df_fechas['Año_se'], errors='coerce')
        
        original_rows = len(df_fechas)
        df_fechas.dropna(subset=['Fecha', 'Año_se'], inplace=True)
        
        if len(df_fechas) < original_rows:
            print(f"Advertencia Calendario: Se eliminaron {original_rows - len(df_fechas)} filas por formato de fecha/Año_se inválido o valores faltantes.")
        
        if df_fechas.empty:
            print("Error: No quedaron filas válidas en el calendario después de procesar fechas y Año_se.")
            return None
            
        print(f"Calendario cargado y procesado: {len(df_fechas)} filas válidas.")
        return df_fechas
    except FileNotFoundError:
        print(f"Error Crítico: Archivo de calendario no encontrado en {path_fechas}")
        return None
    except Exception as e:
        print(f"Error crítico cargando archivo de fechas: {str(e)}")
        return None

def edad_a_dias(texto):
    if pd.isna(texto): return None
    texto_str = str(texto).lower().strip(); dias = 0; encontrado = False
    patrones = [(r'(\d+)\s*(?:a[nñ]os?|a\b)', 365), (r'(\d+)\s*mes(?:es)?', 30), (r'(\d+)\s*d[ií]as?', 1)]
    for patron, factor in patrones:
        matches = re.findall(patron, texto_str)
        for match in matches:
            try: dias += int(match) * factor; encontrado = True
            except ValueError: continue
    return dias if encontrado else None

def extraer_codigo_cie10(texto):
    if pd.isna(texto): return None
    match = re.match(r'^([A-Z]\d{2}(?:\.\d)?)', str(texto).strip())
    return match.group(1) if match else None

def clasificar_por_codigo(codigo, edad_dias=None):
    if not codigo or pd.isna(codigo): return None
    codigo_str = str(codigo).strip()
    grupos = {
        'NAC': ['J18.9'] + [f'J12.{i}' for i in range(10)] + ['J12'] + ['J17.8'],
        'Bronquitis': [f'J20.{i}' for i in range(10)] + ['J20'] + ['J40'],
        'Bronquiolitis': [f'J21.{i}' for i in range(10)] + ['J21'],
        'ETI': [f'J10.{i}' for i in range(10)] + [f'J11.{i}' for i in range(10)] + ['J10', 'J11'],
        'Laringitis': ['J04.0'],
        'CVAS': ['J06.9'] + [f'J02.{i}' for i in range(10)] + ['J02'] + ['J00', 'J03'],
        'Diarreas Sanguinolentas': ['A02.0', 'A03', 'A04', 'A04.0', 'A04.1', 'A04.2', 'A04.3', 'A04.4', 'A04.5', 'A04.6', 'A04.7', 'A04.8', 'A04.9'],
        'Gastro-Intestinales': ['A09'] + [f'A09.{i}' for i in range(10)],
        'IAM': ['I21.9'],
        'ACV': ['I64'] + [f'I64.{i}' for i in range(10)] + ['I61.9', 'I67.8'],
        'TEC': ['S06.9'],
        'Ofidismo': ['T63.0'],
        'Alacranismo': ['T63.2'],
        'Aracnoidismo': ['T63.3'],
        'Sarampión': ['B05'] + [f'B05.{i}' for i in range(10)],
        'Parotiditis Infecciosa': ['B26'] + [f'B26.{i}' for i in range(10)],
        'Coqueluche': ['A37', 'A37.0', 'A37.1', 'A37.8', 'A37.9']
    }
    EDAD_LIMITE_BQL = 3 * 365
    for grupo, codigos_grupo in grupos.items():
        if codigo_str in codigos_grupo:
            if grupo == 'Bronquiolitis' and edad_dias is not None and edad_dias >= EDAD_LIMITE_BQL:
                continue
            return grupo
    return None

def clasificar_por_texto(texto_diags, edad_dias):
    if pd.isna(texto_diags) or not str(texto_diags).strip(): return None
    texto_convertido = str(texto_diags).lower()
    patrones = {
        'NAC': r'\b(nmn|nac|neumon[ií]a|neumonitis)\b',
        'Bronquitis': r'\b(bqt|bor|irab|epoc|bronquitis aguda|bronquitis cronica)\b',
        'Bronquiolitis': r'\b(bql|sme bronquial? ob[?]structivo|bronquiolitis|sob)\b',
        'ETI': r'\b(influenza|gripe|eti|cuadro gripal|s[ií]ndrome gripal|sme\.? gripal)\b',
        'Laringitis': r'\b(laringitis)\b',
        'CVAS': r'\b(cvas|cuas|catarro|faringitis|amigdalitis|angina(?: roja| pult[aá]cea)?|garganta roja|rinofaringitis)\b',
        'Diarreas Sanguinolentas': r'\b(diarrea\s+(con\s+|y\s+)?sangre|sanguinolenta|disenter(i|í)a|melena|enterorragia)\b',
        'Gastro-Intestinales': r'\b(gastroenteritis|gea|diarrea|v[oó]mito[s]?|descomposici[oó]n|dolor abdominal agudo|c[oó]lico abdominal)\b',
        'IAM': r'\b(iam|infarto(\s+agudo\s+de\s+miocardio)?|ataque\s+card[ií]aco|angina\s+inestable|dolor\s+precordial|dolor\s+de\s+pecho\s+opresivo|sca|sindrome\s+coronario\s+agudo)\b',
        'ACV': r'\b(acv|accidente\s+cerebrovascular|derrame\s+cerebral|stroke|ataque\s+cerebral|ictus|hemorragia\s+cerebral|infarto\s+cerebral)\b',
        'TEC': r'\b(tec|traumatismo\s+encefalocraneano|traumatismo\s+de\s+cr[aá]neo|golpe\s+(en\s+la\s+)?cabeza|conmoci[oó]n\s+cerebral)\b',
        'Ofidismo': r'\b(ofidismo|mordedura\s+de\s+(serpiente|v[ií]bora|yarar[aá]))\b',
        'Alacranismo': r'\b(alacranismo|picadura\s+de\s+alacr[aá]n|escorpi[oó]n)\b',
        'Aracnoidismo': r'\b(aracnoidismo|picadura\s+de\s+ara[nñ]a|viuda\s+negra|loxoscelismo)\b',
        'Sarampión': r'\b(sarampi[oó]n)\b',
        'Parotiditis Infecciosa': r'\b(parotiditis|paperas)\b',
        'Coqueluche': r'\b(coqueluche|tos\s+ferina|tos\s+convulsa)\b'
    }
    EDAD_LIMITE_BQL = 3 * 365
    for grupo, patron in patrones.items():
        if re.search(patron, texto_convertido):
            if grupo == 'Bronquiolitis':
                if edad_dias is not None and edad_dias < EDAD_LIMITE_BQL: return grupo
                else: continue
            else: return grupo
    return None

def procesar_columna_fecha_hora_str(df, nombre_col_original, nuevo_nombre_fecha, nuevo_nombre_hora):
    if nombre_col_original in df.columns and not df[nombre_col_original].isna().all():
        temp_series = df[nombre_col_original].fillna("NA_placeholder NA_placeholder").astype(str).str.split(' ', n=1, expand=True)
        df[nuevo_nombre_fecha] = temp_series[0].replace("NA_placeholder", pd.NA)
        if temp_series.shape[1] > 1:
            df[nuevo_nombre_hora] = temp_series[1].replace("NA_placeholder", pd.NA)
        else:
            df[nuevo_nombre_hora] = pd.NA
    else:
        df[nuevo_nombre_fecha] = pd.NA
        df[nuevo_nombre_hora] = pd.NA
    return df

def combine_date_time_parts(date_series, time_series):
    def format_time(t_str):
        if pd.isna(t_str) or str(t_str).strip() == "" or str(t_str).lower() == 'na_placeholder':
            return '00:00:00'
        t_str = str(t_str).strip()
        if '.' in t_str and ':' not in t_str: 
             t_str = t_str.replace('.', ':', 1) 
             if '.' in t_str: 
                  t_str = t_str.replace('.', ':', 1)

        parts = t_str.split(':')
        if len(parts) == 1:
            return f"{parts[0].zfill(2)}:00:00"
        elif len(parts) == 2: 
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
        elif len(parts) == 3: 
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return '00:00:00' 

    formatted_time_series = time_series.apply(format_time)
    return date_series.astype(str) + ' ' + formatted_time_series.astype(str)


def calcular_tiempo_permanencia(row):
    fecha_atencion_dt = row.get('Fecha Atención_dt')
    fecha_egreso_dt = row.get('Fecha Egreso_dt')
    tipo_egreso = row.get('tipo_de_egreso')

    if tipo_egreso not in ['Internación', 'Derivación']:
        return pd.NA

    if pd.isna(fecha_atencion_dt) or pd.isna(fecha_egreso_dt):
        return pd.NA
    
    if not isinstance(fecha_atencion_dt, pd.Timestamp) or not isinstance(fecha_egreso_dt, pd.Timestamp):
        return pd.NA

    if fecha_egreso_dt < fecha_atencion_dt:
        return pd.NA 
        
    try:
        permanencia = fecha_egreso_dt - fecha_atencion_dt
        return permanencia.total_seconds() / 60
    except Exception:
        return pd.NA

def asignar_franja_horaria(hora_ingreso_str):
    if pd.isna(hora_ingreso_str) or str(hora_ingreso_str).strip() == "":
        return "Desconocida" 
    try:
        hora_str_limpia = str(hora_ingreso_str).strip()
        parsed_time = None
        for fmt in ('%H:%M:%S', '%H:%M', '%H.%M.%S', '%H.%M',
                    '%I:%M:%S %p', '%I:%M %p',
                    '%H:%M:%S.%f'):
            try:
                parsed_time = dt_datetime.strptime(hora_str_limpia, fmt).time()
                break
            except ValueError:
                continue
        
        if parsed_time is None:
            return "Error Formato Hora"

        if dt_datetime.strptime("00:00:00", "%H:%M:%S").time() <= parsed_time < dt_datetime.strptime("08:00:00", "%H:%M:%S").time():
            return "0-8 hs"
        elif dt_datetime.strptime("08:00:00", "%H:%M:%S").time() <= parsed_time < dt_datetime.strptime("16:00:00", "%H:%M:%S").time():
            return "8-16 hs"
        elif dt_datetime.strptime("16:00:00", "%H:%M:%S").time() <= parsed_time <= dt_datetime.strptime("23:59:59", "%H:%M:%S").time():
            return "16-24 hs"
        else:
            return "Desconocida" 
    except Exception:
        return "Error Procesando Hora"

def parse_hora_a_numero(hora_str):
    if pd.isna(hora_str) or str(hora_str).strip() == "": return pd.NA
    try:
        hora_str_limpia = str(hora_str).strip()
        parsed_time = None
        formatos_hora = [
            '%H:%M:%S', '%H:%M', '%H.%M.%S', '%H.%M', 
            '%I:%M:%S %p', '%I:%M %p',
            '%H:%M:%S.%f'
        ]
        for fmt in formatos_hora:
            try:
                parsed_time = dt_datetime.strptime(hora_str_limpia, fmt).time()
                break 
            except ValueError:
                continue
        return parsed_time.hour if parsed_time else pd.NA
    except Exception:
        return pd.NA

def get_image_as_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Advertencia: Archivo de logo no encontrado en {image_path}")
        return None
    except Exception as e:
        print(f"Error leyendo el archivo de logo {image_path}: {e}")
        return None

# ================================== #
# ===   PROCESAMIENTO DE DATOS   === #
# ================================== #
def combinar_csv_en_carpeta(carpeta, tipo_servicio_carpeta, df_fechas):
    global ANIO_REPORTE
    if not os.path.exists(carpeta):
        print(f"Advertencia: No se encontró la carpeta: {carpeta}"); return None
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith('.csv')]
    if not archivos: print(f"No se encontraron archivos CSV en {carpeta}"); return None
    
    print(f"\nProcesando {len(archivos)} archivos de {tipo_servicio_carpeta} en '{os.path.basename(carpeta)}'...")
    dfs = []
    columnas_imprescindibles_carga = {'fecha_de_ingreso', 'edad', 'id'}
    columnas_finales_deseadas = [
        'id', 'Fecha_Ingreso_dt_para_merge', 'Fecha Ingreso', 'Hora Ingreso', 'Hora_Ingreso_Num',
        'Fecha Atención', 'Hora Atención', 'Fecha Egreso', 'Hora Egreso',
        'Fecha Atención_dt', 'Fecha Egreso_dt',
        'Tiempo Permanencia (min)', 'Franja Horaria Ingreso',
        'edad', 'Edad_dias', 'Servicio', 'diag_definitivo', 'diag_presuntivo', 
        'codigo_cie10', 'Dx', 'tipo_de_egreso', 'motivo_de_consulta',
        'tipo_de_ingreso', 'triage'
    ]

    for archivo in archivos:
        path = os.path.join(carpeta, archivo)
        print(f"  - Leyendo {archivo}...", end=' ')
        try:
            df = pd.read_csv(path, encoding='utf-8-sig', sep=';', on_bad_lines='warn', low_memory=False)
            print(f"({len(df)} filas)", end=' ')
            columnas_faltantes = columnas_imprescindibles_carga - set(df.columns)
            if columnas_faltantes:
                print(f"¡Error! Faltan cols en {archivo}: {columnas_faltantes}. Saltando."); continue

            df = procesar_columna_fecha_hora_str(df, 'fecha_de_ingreso', 'Fecha Ingreso', 'Hora Ingreso')
            df['Fecha_Ingreso_dt_para_merge'] = pd.to_datetime(df['Fecha Ingreso'], dayfirst=True, errors='coerce')
            df['Hora_Ingreso_Num'] = df['Hora Ingreso'].apply(parse_hora_a_numero)

            df = procesar_columna_fecha_hora_str(df, 'fecha_de_atencion', 'Fecha Atención', 'Hora Atención')
            df = procesar_columna_fecha_hora_str(df, 'fecha_de_egreso', 'Fecha Egreso', 'Hora Egreso')
            
            df['Fecha Atención_dt_str_full'] = combine_date_time_parts(df['Fecha Atención'], df['Hora Atención'])
            df['Fecha Egreso_dt_str_full'] = combine_date_time_parts(df['Fecha Egreso'], df['Hora Egreso'])
            
            df['Fecha Atención_dt'] = pd.to_datetime(df['Fecha Atención_dt_str_full'], dayfirst=True, errors='coerce')
            df['Fecha Egreso_dt'] = pd.to_datetime(df['Fecha Egreso_dt_str_full'], dayfirst=True, errors='coerce')
            
            if 'tipo_de_egreso' not in df.columns:
                df['tipo_de_egreso'] = pd.NA 
            
            df['Tiempo Permanencia (min)'] = df.apply(calcular_tiempo_permanencia, axis=1)
            
            parse_failures = df['Fecha_Ingreso_dt_para_merge'].isna().sum()
            if parse_failures > 0: print(f"¡Adv! {parse_failures}/{len(df)} fechas ingreso no parseadas en {archivo}.", end=' ')

            df['Edad_dias'] = df['edad'].apply(edad_a_dias)
            df['codigo_cie10'] = df['codigo_cie10'].apply(extraer_codigo_cie10) if 'codigo_cie10' in df.columns else pd.NA
            df['Dx'] = pd.NA
            if 'codigo_cie10' in df.columns and df['codigo_cie10'].notna().any():
                mask_valido = df['codigo_cie10'].notna()
                df.loc[mask_valido, 'Dx'] = df[mask_valido].apply(
                    lambda row: clasificar_por_codigo(row['codigo_cie10'], row['Edad_dias']), axis=1)
            
            diag_def_col_data = df['diag_definitivo'] if 'diag_definitivo' in df.columns else pd.Series(pd.NA, index=df.index, dtype=str)
            diag_pres_col_data = df['diag_presuntivo'] if 'diag_presuntivo' in df.columns else pd.Series(pd.NA, index=df.index, dtype=str)
            df['combined_diag_text'] = diag_def_col_data.fillna('') + ' ' + diag_pres_col_data.fillna('')
            
            mask_dx_na = df['Dx'].isna()
            if mask_dx_na.any():
                 df.loc[mask_dx_na, 'Dx'] = df[mask_dx_na].apply(
                    lambda row: clasificar_por_texto(row['combined_diag_text'], row['Edad_dias']), axis=1)
            
            df['Franja Horaria Ingreso'] = df['Hora Ingreso'].apply(asignar_franja_horaria)
            
            cols_to_drop_temp = ['combined_diag_text', 'Fecha Atención_dt_str_full', 'Fecha Egreso_dt_str_full']
            df.drop(columns=cols_to_drop_temp, inplace=True, errors='ignore')

            if 'Servicio' not in df.columns: df['Servicio'] = tipo_servicio_carpeta
            else: df['Servicio'].fillna(tipo_servicio_carpeta, inplace=True)

            for col in columnas_finales_deseadas:
                if col not in df.columns:
                    df[col] = pd.NA
            df = df[columnas_finales_deseadas]

            dfs.append(df)
            print(" -> Procesado OK")
        except Exception as e:
            print(f"\nError procesando {archivo}: {str(e)}. Saltando archivo.\n{traceback.format_exc()}")
            continue
    if not dfs: print(f"\nNo se pudieron procesar archivos para {tipo_servicio_carpeta}."); return None

    df_combinado = pd.concat(dfs, ignore_index=True)
    df_combinado = df_combinado.drop_duplicates(subset=['id'], keep='first')

    if df_fechas is not None and 'Fecha_Ingreso_dt_para_merge' in df_combinado.columns:
        print("Realizando merge con calendario...")
        original_rows = len(df_combinado)
        df_combinado.dropna(subset=['Fecha_Ingreso_dt_para_merge'], inplace=True)
        if 'Semana' not in df_combinado.columns: df_combinado['Semana'] = pd.NA 

        if len(df_combinado) < original_rows:
             print(f"Se eliminaron {original_rows - len(df_combinado)} filas por Fecha_Ingreso_dt inválida antes del merge.")
        if df_combinado.empty:
             print(f"Error: No quedaron datos válidos para {tipo_servicio_carpeta} después de limpiar fechas.");
        else:
            df_fechas['Fecha'] = pd.to_datetime(df_fechas['Fecha'], errors='coerce')
            df_fechas['Año_se'] = pd.to_numeric(df_fechas['Año_se'], errors='coerce')

            df_combinado = pd.merge(df_combinado, df_fechas[['Fecha', 'Semana', 'Año_se']].rename(
                                        columns={'Semana':'Semana_calendario', 'Año_se':'Año_se_calendario'}),
                                    left_on='Fecha_Ingreso_dt_para_merge', right_on='Fecha', how='left')
            
            if 'Semana_calendario' in df_combinado.columns:
                 df_combinado['Semana'] = df_combinado['Semana_calendario'].astype('Int64')
                 df_combinado.drop(columns=['Semana_calendario'], inplace=True, errors='ignore')

            if 'Año_se_calendario' in df_combinado.columns:
                print(f"Filtrando datos para el año {ANIO_REPORTE} (usando Año_se del calendario)...")
                original_rows_before_year_filter = len(df_combinado)
                df_combinado['Año_se_calendario'] = pd.to_numeric(df_combinado['Año_se_calendario'], errors='coerce')
                df_combinado = df_combinado[df_combinado['Año_se_calendario'] == ANIO_REPORTE].copy()
                rows_filtered_out = original_rows_before_year_filter - len(df_combinado)
                if rows_filtered_out > 0:
                    print(f"Se filtraron {rows_filtered_out} filas que no corresponden al año {ANIO_REPORTE} (Año_se).")
                if df_combinado.empty:
                    print(f"Advertencia: No quedaron datos para {tipo_servicio_carpeta} después de filtrar por el año {ANIO_REPORTE} (Año_se).")
                df_combinado.drop(columns=['Año_se_calendario'], inplace=True, errors='ignore')
            else:
                print(f"Advertencia: La columna 'Año_se_calendario' no está presente después del merge. No se puede filtrar por año {ANIO_REPORTE} (Año_se) usando el calendario.")

            df_combinado.drop(columns=['Fecha'], inplace=True, errors='ignore')

    elif 'Semana' not in df_combinado.columns:
        df_combinado['Semana'] = pd.NA
        print(f"Advertencia: No se pudo realizar el merge con el calendario. El filtrado por año ({ANIO_REPORTE}) (Año_se) no se aplicará usando el calendario.")

    print(f"\nProcesamiento de {tipo_servicio_carpeta} completado. Filas finales: {len(df_combinado)}")
    return df_combinado

# ================================== #
# ===   EXPORTACIÓN DE DATOS     === #
# ================================== #
def guardar_con_verificacion(df, path):
    if df is None or df.empty:
        print(f"No hay datos para guardar en {os.path.basename(path)}. Archivo no generado."); return
    print(f"Guardando archivo en: {path}")
    try:
        df_to_save = df.copy()
        cols_to_drop_for_csv = ['Fecha_Ingreso_dt_para_merge', 'Fecha Atención_dt', 'Fecha Egreso_dt', 'Hora_Ingreso_Num']
        
        for col in cols_to_drop_for_csv:
            if col in df_to_save.columns:
                df_to_save.drop(columns=[col], inplace=True, errors='ignore')
        
        df_to_save.to_csv(path, index=False, encoding='utf-8-sig', sep=';', float_format='%.1f')
        print(f"  Archivo guardado exitosamente.")
    except Exception as e:
        print(f"Error al guardar el archivo {path}: {str(e)}")

# ================================== #
# === GENERACIÓN DE REPORTE HTML === #
# ================================== #

def preparar_datos_para_reporte(df_source, nombre_vista):
    if df_source is None or df_source.empty:
        print(f"No hay datos fuente para {nombre_vista}.")
        return ("[]", None, None, "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]")

    min_w_grafico_global = float('inf')
    max_w_grafico_global = float('-inf')
    all_semanas_in_source = []
    if 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        try:
            semanas_validas = pd.to_numeric(df_source['Semana'], errors='coerce').dropna().astype(int)
            if not semanas_validas.empty:
                min_semana = semanas_validas.min()
                max_semana = semanas_validas.max()
                # Creamos una lista completa de todas las semanas en el rango de datos.
                all_semanas_in_source = list(range(min_semana, max_semana + 1))
        except Exception as e:
            print(f"Advertencia: no se pudo determinar el rango de semanas completo. {e}")
            all_semanas_in_source = []
   

    # --- Diagnósticos Respiratorios ---
    json_grafico_dx_resp = "[]"
    dx_respiratorios = ['NAC', 'Bronquitis', 'Bronquiolitis', 'ETI', 'Laringitis', 'CVAS']
    
    # Para el reporte de adultos, no graficamos Bronquiolitis (es pediátrica)
    if "Adultos" in nombre_vista:
        if 'Bronquiolitis' in dx_respiratorios:
            dx_respiratorios.remove('Bronquiolitis')

    if 'Dx' in df_source.columns and 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        df_plot_dx_resp = df_source[df_source['Dx'].isin(dx_respiratorios)].dropna(subset=['Dx', 'Semana']).copy()
        if not df_plot_dx_resp.empty:
            try: df_plot_dx_resp['Semana'] = pd.to_numeric(df_plot_dx_resp['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_plot_dx_resp = pd.DataFrame()
        # El bloque ahora se ejecuta incluso si df_plot_dx_resp está vacío para asegurar que se generen ceros.
        if all_semanas_in_source:
            counts_series = df_plot_dx_resp.groupby(['Semana', 'Dx']).size() if not df_plot_dx_resp.empty else pd.Series()
            # Usamos la lista completa de semanas.
            full_idx = pd.MultiIndex.from_product([all_semanas_in_source, dx_respiratorios], names=['Semana', 'Dx'])
            df_counts_dx_resp = counts_series.reindex(full_idx, fill_value=0).reset_index(name='Conteo').sort_values('Semana')
            
            if not df_counts_dx_resp.empty:
                json_grafico_dx_resp = df_counts_dx_resp.to_json(orient='records')
                min_w_grafico_global = min(min_w_grafico_global, int(df_counts_dx_resp['Semana'].min()))
                max_w_grafico_global = max(max_w_grafico_global, int(df_counts_dx_resp['Semana'].max()))

    # --- Diagnósticos Gastro-Intestinales ---
    json_grafico_dx_gastro = "[]"
    dx_gastro_groups = ['Gastro-Intestinales', 'Diarreas Sanguinolentas']
    if 'Dx' in df_source.columns and 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        df_plot_dx_gastro = df_source[df_source['Dx'].isin(dx_gastro_groups)].dropna(subset=['Dx', 'Semana']).copy()
        if not df_plot_dx_gastro.empty:
            try: df_plot_dx_gastro['Semana'] = pd.to_numeric(df_plot_dx_gastro['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_plot_dx_gastro = pd.DataFrame()
        if all_semanas_in_source:
            counts_series = df_plot_dx_gastro.groupby(['Semana', 'Dx']).size() if not df_plot_dx_gastro.empty else pd.Series()
            full_idx = pd.MultiIndex.from_product([all_semanas_in_source, dx_gastro_groups], names=['Semana', 'Dx'])
            df_counts_dx_gastro = counts_series.reindex(full_idx, fill_value=0).reset_index(name='Conteo').sort_values('Semana')
            
            if not df_counts_dx_gastro.empty:
                json_grafico_dx_gastro = df_counts_dx_gastro.to_json(orient='records')
                min_w_grafico_global = min(min_w_grafico_global, int(df_counts_dx_gastro['Semana'].min()))
                max_w_grafico_global = max(max_w_grafico_global, int(df_counts_dx_gastro['Semana'].max()))

    # --- Diagnósticos Cardio-Vasculares ---
    json_grafico_dx_cardio = "[]"
    dx_cardio = ['IAM', 'ACV']
    if 'Dx' in df_source.columns and 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        df_plot_dx_cardio = df_source[df_source['Dx'].isin(dx_cardio)].dropna(subset=['Dx', 'Semana']).copy()
        if not df_plot_dx_cardio.empty:
            try: df_plot_dx_cardio['Semana'] = pd.to_numeric(df_plot_dx_cardio['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_plot_dx_cardio = pd.DataFrame()
        if all_semanas_in_source:
            counts_series = df_plot_dx_cardio.groupby(['Semana', 'Dx']).size() if not df_plot_dx_cardio.empty else pd.Series()
            full_idx = pd.MultiIndex.from_product([all_semanas_in_source, dx_cardio], names=['Semana', 'Dx'])
            df_counts_dx_cardio = counts_series.reindex(full_idx, fill_value=0).reset_index(name='Conteo').sort_values('Semana')
            
            if not df_counts_dx_cardio.empty:
                json_grafico_dx_cardio = df_counts_dx_cardio.to_json(orient='records')
                min_w_grafico_global = min(min_w_grafico_global, int(df_counts_dx_cardio['Semana'].min()))
                max_w_grafico_global = max(max_w_grafico_global, int(df_counts_dx_cardio['Semana'].max()))

    # --- Diagnósticos TEC ---
    json_grafico_dx_tec = "[]"
    dx_tec = ['TEC']
    if 'Dx' in df_source.columns and 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        df_plot_dx_tec = df_source[df_source['Dx'].isin(dx_tec)].dropna(subset=['Dx', 'Semana']).copy()
        if not df_plot_dx_tec.empty:
            try: df_plot_dx_tec['Semana'] = pd.to_numeric(df_plot_dx_tec['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_plot_dx_tec = pd.DataFrame()
        if all_semanas_in_source:
            counts_series = df_plot_dx_tec.groupby(['Semana', 'Dx']).size() if not df_plot_dx_tec.empty else pd.Series()
            full_idx = pd.MultiIndex.from_product([all_semanas_in_source, dx_tec], names=['Semana', 'Dx'])
            df_counts_dx_tec = counts_series.reindex(full_idx, fill_value=0).reset_index(name='Conteo').sort_values('Semana')
            
            if not df_counts_dx_tec.empty:
                json_grafico_dx_tec = df_counts_dx_tec.to_json(orient='records')
                min_w_grafico_global = min(min_w_grafico_global, int(df_counts_dx_tec['Semana'].min()))
                max_w_grafico_global = max(max_w_grafico_global, int(df_counts_dx_tec['Semana'].max()))

    # --- Diagnósticos Ponzoñosos ---
    json_grafico_dx_ponzonosos = "[]"
    dx_ponzonosos_groups = ['Ofidismo', 'Alacranismo', 'Aracnoidismo']
    if 'Dx' in df_source.columns and 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        df_plot_dx_ponzonosos = df_source[df_source['Dx'].isin(dx_ponzonosos_groups)].dropna(subset=['Dx', 'Semana']).copy()
        if not df_plot_dx_ponzonosos.empty:
            try: df_plot_dx_ponzonosos['Semana'] = pd.to_numeric(df_plot_dx_ponzonosos['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_plot_dx_ponzonosos = pd.DataFrame()
        if all_semanas_in_source:
            counts_series = df_plot_dx_ponzonosos.groupby(['Semana', 'Dx']).size() if not df_plot_dx_ponzonosos.empty else pd.Series()
            full_idx = pd.MultiIndex.from_product([all_semanas_in_source, dx_ponzonosos_groups], names=['Semana', 'Dx'])
            df_counts_dx_ponzonosos = counts_series.reindex(full_idx, fill_value=0).reset_index(name='Conteo').sort_values('Semana')
            
            if not df_counts_dx_ponzonosos.empty:
                json_grafico_dx_ponzonosos = df_counts_dx_ponzonosos.to_json(orient='records')
                min_w_grafico_global = min(min_w_grafico_global, int(df_counts_dx_ponzonosos['Semana'].min()))
                max_w_grafico_global = max(max_w_grafico_global, int(df_counts_dx_ponzonosos['Semana'].max()))

    # --- Diagnósticos Inmunoprevenibles ---
    json_grafico_dx_inmuno = "[]"
    dx_inmunoprevenibles_groups = ['Sarampión', 'Parotiditis Infecciosa', 'Coqueluche']
    if 'Dx' in df_source.columns and 'Semana' in df_source.columns and not df_source['Semana'].isna().all():
        df_plot_dx_inmuno = df_source[df_source['Dx'].isin(dx_inmunoprevenibles_groups)].dropna(subset=['Dx', 'Semana']).copy()
        if not df_plot_dx_inmuno.empty:
            try: df_plot_dx_inmuno['Semana'] = pd.to_numeric(df_plot_dx_inmuno['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_plot_dx_inmuno = pd.DataFrame()
        if all_semanas_in_source:
            counts_series = df_plot_dx_inmuno.groupby(['Semana', 'Dx']).size() if not df_plot_dx_inmuno.empty else pd.Series()
            full_idx = pd.MultiIndex.from_product([all_semanas_in_source, dx_inmunoprevenibles_groups], names=['Semana', 'Dx'])
            df_counts_dx_inmuno = counts_series.reindex(full_idx, fill_value=0).reset_index(name='Conteo').sort_values('Semana')
            
            if not df_counts_dx_inmuno.empty:
                json_grafico_dx_inmuno = df_counts_dx_inmuno.to_json(orient='records')
                min_w_grafico_global = min(min_w_grafico_global, int(df_counts_dx_inmuno['Semana'].min()))
                max_w_grafico_global = max(max_w_grafico_global, int(df_counts_dx_inmuno['Semana'].max()))

    # (El resto de la función no necesita cambios, se pega igual)
    # ...
    json_tabla_egresos = "[]"; tipos_egreso_esperados = ['Alta médica', 'Defunción', 'Derivación', 'Internación']
    if 'Semana' in df_source.columns and 'tipo_de_egreso' in df_source.columns and not df_source['Semana'].isna().all():
        df_tabla_eg_prep = df_source.dropna(subset=['Semana', 'tipo_de_egreso']).copy()
        if not df_tabla_eg_prep.empty:
            try: df_tabla_eg_prep['Semana'] = pd.to_numeric(df_tabla_eg_prep['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_tabla_eg_prep = pd.DataFrame()
            if not df_tabla_eg_prep.empty and 'Semana' in df_tabla_eg_prep.columns and df_tabla_eg_prep['Semana'].notna().any():
                df_eg_counts = df_tabla_eg_prep.groupby(['Semana', 'tipo_de_egreso']).size().reset_index(name='Cantidad')
                if not df_eg_counts.empty:
                    df_tabla_eg_pivot = df_eg_counts.pivot_table(index='Semana', columns='tipo_de_egreso', values='Cantidad', fill_value=0).reset_index()
                    for col_egreso in tipos_egreso_esperados:
                        if col_egreso not in df_tabla_eg_pivot.columns: df_tabla_eg_pivot[col_egreso] = 0
                    cols_tabla_eg_final = ['Semana'] + [col for col in tipos_egreso_esperados if col in df_tabla_eg_pivot.columns]
                    json_tabla_egresos = df_tabla_eg_pivot[cols_tabla_eg_final].sort_values('Semana').to_json(orient='records')

    json_grafico_int_der = "[]"
    if 'Semana' in df_source.columns and 'tipo_de_egreso' in df_source.columns and not df_source['Semana'].isna().all():
        df_int_der_prep = df_source[df_source['tipo_de_egreso'].isin(['Internación', 'Derivación'])].dropna(subset=['Semana']).copy()
        if not df_int_der_prep.empty:
            try: df_int_der_prep['Semana'] = pd.to_numeric(df_int_der_prep['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_int_der_prep = pd.DataFrame()
            if not df_int_der_prep.empty and 'Semana' in df_int_der_prep.columns and df_int_der_prep['Semana'].notna().any():
                df_counts_int_der = df_int_der_prep.groupby(['Semana', 'tipo_de_egreso']).size().reset_index(name='Conteo').sort_values('Semana')
                if not df_counts_int_der.empty and not df_counts_int_der['Semana'].empty: 
                    json_grafico_int_der = df_counts_int_der.to_json(orient='records')
                    if not df_counts_int_der['Semana'].empty:
                        min_w_grafico_global = min(min_w_grafico_global, int(df_counts_int_der['Semana'].min()))
                        max_w_grafico_global = max(max_w_grafico_global, int(df_counts_int_der['Semana'].max()))
    
    json_tabla_franjas = "[]"; franjas_esperadas_tabla = ['0-8 hs', '8-16 hs', '16-24 hs']
    if 'Semana' in df_source.columns and 'Franja Horaria Ingreso' in df_source.columns and not df_source['Semana'].isna().all():
        df_tabla_fh_prep = df_source.dropna(subset=['Semana', 'Franja Horaria Ingreso']).copy()
        df_tabla_fh_prep = df_tabla_fh_prep[df_tabla_fh_prep['Franja Horaria Ingreso'].isin(franjas_esperadas_tabla)]
        if not df_tabla_fh_prep.empty:
            try: df_tabla_fh_prep['Semana'] = pd.to_numeric(df_tabla_fh_prep['Semana'], errors='coerce').dropna().astype(int)
            except Exception: df_tabla_fh_prep = pd.DataFrame()
            if not df_tabla_fh_prep.empty and 'Semana' in df_tabla_fh_prep.columns and df_tabla_fh_prep['Semana'].notna().any():
                df_fh_counts = df_tabla_fh_prep.groupby(['Semana', 'Franja Horaria Ingreso']).size().reset_index(name='Cantidad')
                if not df_fh_counts.empty:
                    df_tabla_fh_pivot = df_fh_counts.pivot_table(index='Semana', columns='Franja Horaria Ingreso', values='Cantidad', fill_value=0).reset_index()
                    for col_franja in franjas_esperadas_tabla:
                        if col_franja not in df_tabla_fh_pivot.columns: df_tabla_fh_pivot[col_franja] = 0
                    cols_tabla_fh_final = ['Semana'] + [col for col in franjas_esperadas_tabla if col in df_tabla_fh_pivot.columns]
                    json_tabla_franjas = df_tabla_fh_pivot[cols_tabla_fh_final].sort_values('Semana').to_json(orient='records')

    json_grafico_consultas_hora = "[]"
    if 'Semana' in df_source.columns and 'Hora_Ingreso_Num' in df_source.columns and \
       not df_source['Semana'].isna().all() and not df_source['Hora_Ingreso_Num'].isna().all():
        df_ch_prep = df_source.dropna(subset=['Semana', 'Hora_Ingreso_Num']).copy()
        if not df_ch_prep.empty:
            try:
                df_ch_prep['Semana'] = pd.to_numeric(df_ch_prep['Semana'], errors='coerce').dropna().astype(int)
                df_ch_prep['Hora_Ingreso_Num'] = pd.to_numeric(df_ch_prep['Hora_Ingreso_Num'], errors='coerce').dropna().astype(int)
            except Exception: df_ch_prep = pd.DataFrame()
            if not df_ch_prep.empty and 'Semana' in df_ch_prep.columns and df_ch_prep['Semana'].notna().any():
                all_semanas_presentes = df_ch_prep['Semana'].unique()
                all_horas_dia = range(24)
                idx = pd.MultiIndex.from_product([all_semanas_presentes, all_horas_dia], names=['Semana', 'Hora_Ingreso_Num'])
                df_counts_ch = df_ch_prep.groupby(['Semana', 'Hora_Ingreso_Num']).size().reset_index(name='Cantidad')
                if not df_counts_ch.empty:
                    df_counts_ch = df_counts_ch.set_index(['Semana', 'Hora_Ingreso_Num']).reindex(idx, fill_value=0).reset_index()
                    json_grafico_consultas_hora = df_counts_ch.sort_values(['Semana', 'Hora_Ingreso_Num']).to_json(orient='records')

    json_tiempo_permanencia = "[]"
    if 'Semana' in df_source.columns and 'Tiempo Permanencia (min)' in df_source.columns and \
       'tipo_de_egreso' in df_source.columns and not df_source['Semana'].isna().all():
        
        df_tp_prep = df_source[df_source['tipo_de_egreso'].isin(['Internación', 'Derivación'])].copy()
        df_tp_prep.dropna(subset=['Semana', 'Tiempo Permanencia (min)'], inplace=True) 
        
        if not df_tp_prep.empty:
            try:
                df_tp_prep['Semana'] = pd.to_numeric(df_tp_prep['Semana'], errors='coerce').dropna().astype(int)
            except Exception: 
                df_tp_prep = pd.DataFrame() 

            if not df_tp_prep.empty and 'Semana' in df_tp_prep.columns and df_tp_prep['Semana'].notna().any():
                df_tp_prep['Tiempo Permanencia (min)'] = pd.to_numeric(df_tp_prep['Tiempo Permanencia (min)'], errors='coerce')
                df_tp_avg = df_tp_prep.groupby('Semana')['Tiempo Permanencia (min)'].mean().round(1).reset_index(name='PermanenciaPromedio')
                if not df_tp_avg.empty and df_tp_avg['PermanenciaPromedio'].notna().any(): 
                    json_tiempo_permanencia = df_tp_avg.sort_values('Semana').to_json(orient='records')
                elif not df_tp_avg.empty:
                     print(f"Advertencia para {nombre_vista}: Todos los promedios de tiempo de permanencia son NaN o la tabla está vacía después del groupby.")


    json_porcentaje_sin_dx = "[]"
    cols_for_sin_dx_check = ['Semana', 'Fecha Atención_dt', 'Fecha Egreso_dt', 
                             'diag_definitivo', 'diag_presuntivo', 'codigo_cie10']
    if all(col in df_source.columns for col in cols_for_sin_dx_check) and \
       not df_source['Semana'].isna().all():
        df_sin_dx_prep = df_source.copy()
        df_sin_dx_prep = df_sin_dx_prep.dropna(subset=['Semana', 'Fecha Atención_dt', 'Fecha Egreso_dt'])

        if not df_sin_dx_prep.empty:
            try:
                df_sin_dx_prep['Semana'] = pd.to_numeric(df_sin_dx_prep['Semana'], errors='coerce').dropna().astype(int)
            except Exception:
                df_sin_dx_prep = pd.DataFrame()

            if not df_sin_dx_prep.empty and 'Semana' in df_sin_dx_prep.columns and df_sin_dx_prep['Semana'].notna().any():
                total_evaluable_per_semana = df_sin_dx_prep.groupby('Semana').size().reset_index(name='TotalEvaluables')
                
                def is_missing_diag_field(val):
                    return pd.isna(val) or str(val).strip() == ""

                df_sin_dx_prep['SinDx_Def'] = df_sin_dx_prep['diag_definitivo'].apply(is_missing_diag_field)
                df_sin_dx_prep['SinDx_Pres'] = df_sin_dx_prep['diag_presuntivo'].apply(is_missing_diag_field)
                df_sin_dx_prep['SinDx_CIE10_Orig'] = df_sin_dx_prep['codigo_cie10'].apply(is_missing_diag_field)
                
                df_sin_dx_prep['PacienteSinDiagnostico'] = df_sin_dx_prep['SinDx_Def'] & \
                                                          df_sin_dx_prep['SinDx_Pres'] & \
                                                          df_sin_dx_prep['SinDx_CIE10_Orig']

                sin_dx_counts = df_sin_dx_prep[df_sin_dx_prep['PacienteSinDiagnostico']].groupby('Semana').size().reset_index(name='CantidadSinDx')

                if not total_evaluable_per_semana.empty:
                    df_porcentaje_sin_dx_calc = pd.merge(total_evaluable_per_semana, sin_dx_counts, on='Semana', how='left')
                    df_porcentaje_sin_dx_calc['CantidadSinDx'] = df_porcentaje_sin_dx_calc['CantidadSinDx'].fillna(0).astype(int)
                    
                    df_porcentaje_sin_dx_calc['PorcentajeSinDx'] = 0.0 
                    mask_valid_total = df_porcentaje_sin_dx_calc['TotalEvaluables'] > 0
                    df_porcentaje_sin_dx_calc.loc[mask_valid_total, 'PorcentajeSinDx'] = \
                        (df_porcentaje_sin_dx_calc.loc[mask_valid_total, 'CantidadSinDx'] / \
                         df_porcentaje_sin_dx_calc.loc[mask_valid_total, 'TotalEvaluables'] * 100).round(1)
                    
                    df_porcentaje_sin_dx_final = df_porcentaje_sin_dx_calc[['Semana', 'PorcentajeSinDx']]
                    if not df_porcentaje_sin_dx_final.empty:
                        json_porcentaje_sin_dx = df_porcentaje_sin_dx_final.sort_values('Semana').to_json(orient='records')
    
    json_tabla_triage = "[]"
    json_triage_column_order = "[]"
    required_cols_for_triage = ['Semana', 'triage', 'tipo_de_ingreso']

    if all(col in df_source.columns for col in required_cols_for_triage):
        df_triage_temp = df_source.copy()
        df_triage_temp['triage'] = df_triage_temp['triage'].fillna('Sin especificar')
        df_triage_temp['triage'] = df_triage_temp['triage'].astype(str).str.strip().str.capitalize()
        df_triage_temp['triage'] = df_triage_temp['triage'].replace(['', 'None', 'Nan', 'Na', '<Na>'], 'Sin especificar')
        
        df_triage_temp['tipo_de_ingreso'] = df_triage_temp['tipo_de_ingreso'].fillna('')
        df_triage_temp['tipo_de_ingreso'] = df_triage_temp['tipo_de_ingreso'].astype(str).str.strip().str.capitalize()
        
        condicion_ambulancia_sin_triage = \
            (df_triage_temp['tipo_de_ingreso'] == 'Ambulancia') & \
            (df_triage_temp['triage'] == 'Sin especificar')
        df_triage_temp.loc[condicion_ambulancia_sin_triage, 'triage'] = 'Rojo'
        
        df_triage_sem = df_triage_temp.dropna(subset=['Semana'])

        if not (df_triage_sem.empty or df_triage_sem['Semana'].isna().all()):
            try:
                df_triage_sem['Semana'] = pd.to_numeric(df_triage_sem['Semana'], errors='coerce').dropna().astype(int)
                if df_triage_sem['Semana'].empty: 
                    df_triage_sem = pd.DataFrame() 
            except Exception:
                 df_triage_sem = pd.DataFrame() 

            if not df_triage_sem.empty and 'Semana' in df_triage_sem.columns and df_triage_sem['Semana'].notna().any():
                triage_counts = df_triage_sem.groupby(['Semana', 'triage']).size().reset_index(name='Cantidad')
                
                if not triage_counts.empty:
                    triage_pivot = triage_counts.pivot_table(index='Semana', columns='triage', values='Cantidad', fill_value=0)
                    triage_pivot.columns.name = None
                    triage_pivot = triage_pivot.sort_index().reset_index()

                    preferred_order = ['Rojo', 'Naranja', 'Amarillo', 'Verde', 'Azul', 'Sin especificar']
                    current_triage_columns = [col for col in triage_pivot.columns if col != 'Semana']
                    
                    final_column_order = ['Semana']
                    for p_col in preferred_order:
                        if p_col in current_triage_columns: final_column_order.append(p_col)
                    for c_col in sorted(current_triage_columns):
                        if c_col not in final_column_order: final_column_order.append(c_col)
                    
                    triage_pivot = triage_pivot.reindex(columns=final_column_order, fill_value=0)
                    for col in final_column_order:
                        if col != 'Semana': triage_pivot[col] = triage_pivot[col].astype(int)

                    triage_cols_for_sum = [col for col in final_column_order if col != 'Semana']
                    triage_pivot['TotalSemana'] = triage_pivot[triage_cols_for_sum].sum(axis=1)
                    
                    data_for_json = []
                    for _, row_data in triage_pivot.iterrows():
                        record = {'Semana': int(row_data['Semana'])} 
                        total_semana = int(row_data['TotalSemana']) 
                        for col_name in triage_cols_for_sum:
                            abs_val = int(row_data[col_name]) 
                            pct_val = (abs_val / total_semana * 100) if total_semana > 0 else 0.0
                            record[col_name] = {'abs': abs_val, 'pct': round(pct_val, 1)}
                        data_for_json.append(record)
                    
                    json_tabla_triage = json.dumps(data_for_json)
                    json_triage_column_order = json.dumps(final_column_order)


    final_min_w = min_w_grafico_global if min_w_grafico_global != float('inf') else None
    final_max_w = max_w_grafico_global if max_w_grafico_global != float('-inf') else None
    
    return (json_grafico_dx_resp, final_min_w, final_max_w, 
            json_tabla_egresos, json_grafico_int_der, json_tabla_franjas, 
            json_grafico_consultas_hora, json_tiempo_permanencia,
            json_grafico_dx_gastro, json_grafico_dx_cardio, json_grafico_dx_tec,
            json_grafico_dx_ponzonosos, json_grafico_dx_inmuno,
            json_porcentaje_sin_dx, json_tabla_triage, json_triage_column_order)


def generar_reporte_html_interactivo(datos_vistas_dict, output_folder, global_min_week, global_max_week, logo_base64_str, anio_reporte):
    def escape_json_for_js(json_string):
        if not isinstance(json_string, str):
            json_string = str(json_string)
        return json_string.replace('\\', '\\\\').replace("'", "\\'")

    logo_html = ""
    if logo_base64_str:
        logo_html = f'<div class="logo-container"><img src="data:image/png;base64,{logo_base64_str}" alt="Logo Hospital"></div>'

    fecha_actual_str = date.today().strftime("%d/%m/%Y")
    info_superior_derecha_html = f'<div class="info-superior-derecha">Neuquén<br>{fecha_actual_str}</div>'

    # --- INICIO DE LA CORRECCIÓN ---
    # Sacamos los bloques de JavaScript conflictivos de la f-string principal.
    js_color_definitions = """
        const colorPalette = ['#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8', '#6f42c1', '#fd7e14', '#20c997', '#6610f2', '#e83e8c'];
        const specificDxColors = {
            'Diarreas Sanguinolentas': '#dc3545', // Red
            'Gastro-Intestinales': '#007bff'    // Blue
        };
        const triageHeaderColors = {
            'Verde': '#90EE90', 'Amarillo': '#FFFFE0', 'Rojo': '#FFB6C1',
            'Naranja': '#FFDAB9', 'Azul': '#ADD8E6', 'Sin especificar': '#D3D3D3'
        };
    """

    js_menu_listeners = """
        servicioMenuTrigger.addEventListener('click', function() {
            servicioSubmenu.classList.toggle('open');
            this.innerHTML = `Servicio de Guardia ${servicioSubmenu.classList.contains('open') ? '&#9652;' : '&#9662;'}`;
        });
        diagnosticosMenuTrigger.addEventListener('click', function() {
            diagnosticosSubmenu.classList.toggle('open');
            this.innerHTML = `Guardia Diagnósticos ${diagnosticosSubmenu.classList.contains('open') ? '&#9652;' : '&#9662;'}`;
        });
    """
    # --- FIN DE LA CORRECCIÓN ---

    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Semanal de Vigilancia Epidemiológica - {anio_reporte}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #f4f4f4; color: #333; display: flex; height: 100vh; }}
        .sidebar {{ width: 180px; background-color: #333; color: white; padding: 15px; overflow-y: auto; flex-shrink: 0; }}
        .sidebar h3 {{ margin-top: 0; border-bottom: 1px solid #555; padding-bottom: 10px; }}
        .sidebar ul {{ list-style-type: none; padding: 0; margin:0; }}
        .sidebar ul li a, .sidebar ul li .submenu-trigger {{ 
            color: #ddd; text-decoration: none; display: block; 
            padding: 10px 15px; border-radius: 4px; cursor: pointer; font-size: 0.95em;
        }}
        .sidebar ul li a:hover, .sidebar ul li .submenu-trigger:hover, 
        .sidebar ul li a.active {{ 
            background-color: #555; color: white; 
        }}
        .sidebar .submenu {{
            list-style-type: none; padding-left: 15px; /* Indent submenu items */
            max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out;
        }}
        .sidebar .submenu.open {{ max-height: 500px; }}
        .main-content {{ 
            flex-grow: 1; padding: 20px; overflow-y: auto; background-color: #fff; 
            margin:10px; border-radius:8px; box-shadow: 0 0 10px rgba(0,0,0,0.1);
            position: relative; 
        }}
        .logo-container {{ position: absolute; top: 15px; left: 20px; z-index: 1000; }}
        .logo-container img {{ height: 50px; width: auto; }}
        .info-superior-derecha {{
           position: absolute; top: 15px; right: 20px;
           text-align: right; font-size: 0.9em; color: #555; z-index: 1000;
        }}
        .report-intro {{
            text-align: center; font-size: 1em; margin-bottom: 25px; padding: 10px;
            background-color: #e9f7fd; border-left: 5px solid #007bff; color: #333;
            margin-top: 70px; 
        }}
        h1, h2 {{ color: #0056b3; text-align: center; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
        h1 {{font-size: 1.8em; border-bottom-width: 2px; margin-top: 0; }}
        h2 {{font-size: 1.4em; margin-top: 40px;}}
        .controls {{ 
            margin-bottom: 20px; padding: 10px; background-color: #e9ecef; border-radius: 5px; 
            display: flex; flex-wrap: wrap; justify-content: space-around; align-items: center; 
        }}
        .control-group {{ display: flex; flex-direction: column; align-items: center; margin: 5px 10px;}}
        .control-group label {{ margin-bottom: 5px; font-size: 0.9em; }}
        .control-group input[type="range"] {{ width: 180px; }}
        .chart-container {{ margin-top: 20px; padding: 15px; background-color:#fdfdfd; border: 1px solid #ddd; border-radius: 5px; position: relative; height:45vh; width:100%;}}
        
        .table-container {{ margin-top: 30px; }}
        table.custom-table, table.modern-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.85em; }}
        
        table.custom-table th, table.custom-table td,
        table.modern-table th, table.modern-table td {{ 
            border: 1px solid #ddd; padding: 8px; text-align: center;
        }}
        
        table.custom-table th {{ 
            background-color: #e9ecef; color: #333; font-weight: bold;
        }}
        table.custom-table td:first-child {{ text-align: center; font-weight: bold; }}
        table.custom-table td {{ text-align: right; }}

        table.modern-table th {{
            background-color: #e9ecef;
            color: #333;
            font-weight: 600;
        }}
        table.modern-table th:first-child,
        table.modern-table td:first-child {{
            text-align: left; font-weight: bold;
            background-color: #fdfdfd !important; 
            color: #333 !important;
        }}
        table.modern-table td {{ text-align: center; }}
        table.modern-table tbody tr:nth-of-type(even) {{ background-color: #f8f9fa; }}
        table.modern-table tbody tr:hover {{ background-color: #e9ecef; }}

        .info-box {{
            margin-top: 20px; padding: 15px; background-color: #e9f7fd; border: 1px solid #b3e0f2; 
            border-radius: 5px; text-align: center; font-size: 1.1em;
        }}
        .info-box p {{ margin: 5px 0; }}
        .info-box .value {{ font-weight: bold; color: #0056b3; }}
        .info-box small {{ display: block; margin-top: 10px; font-size: 0.85em; color: #555; }}
        canvas {{ max-width: 100%; max-height: 100%; }}
        footer {{ margin-top: 30px; text-align: center; font-size: 0.9em; color: #777; }}
        #noDataMessageTriage {{
            text-align: center; font-style: italic; color: #777; padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>Navegación</h3>
        <ul>
            <li>
                <div class="submenu-trigger" id="servicioMenuTrigger">Servicio de Guardia &#9662;</div>
                <ul class="submenu" id="servicioSubmenu">
                    <li><a href="#" data-view="servicio_adultos">Adultos</a></li>
                    <li><a href="#" data-view="servicio_pediatria">Pediatría</a></li>
                </ul>
            </li>
            <li>
                <div class="submenu-trigger" id="diagnosticosMenuTrigger">Guardia Diagnósticos &#9662;</div>
                <ul class="submenu" id="diagnosticosSubmenu">
                    <li><a href="#" data-view="diagnosticos_adultos">Adultos</a></li>
                    <li><a href="#" data-view="diagnosticos_pediatria">Pediatría</a></li>
                </ul>
            </li>
        </ul>
    </div>
    <div class="main-content">
        {logo_html}
        {info_superior_derecha_html}
        <h1 id="reportTitle">Reporte Guardia</h1>
        <p class="report-intro">Este es un informe generado a partir de las bases de datos de la guardia de INTRANET. 
           Los datos presentados corresponden a los registros consolidados de las atenciones en los servicios de guardia HPN para el año {anio_reporte}. 
           Utilice los controles deslizantes para filtrar los datos por semana epidemiológica.</p>
        
        <div id="diagnosticosReportContent">
            <h2 id="titleDxResp">Diagnósticos agrupados por causa respiratoria. {anio_reporte}</h2>
            <div class="controls" id="controlsDxResp">
                <div class="control-group">
                    <label for="minWeekSliderDxResp">Desde Semana: <span id="minWeekValueDxResp">{global_min_week}</span></label>
                    <input type="range" id="minWeekSliderDxResp" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
                <div class="control-group">
                    <label for="maxWeekSliderDxResp">Hasta Semana: <span id="maxWeekValueDxResp">{global_max_week}</span></label>
                    <input type="range" id="maxWeekSliderDxResp" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartDxResp"></canvas>
            </div>

            <h2 id="titleDxGastro">Diagnósticos agrupados por causa gastro-entérica (diarrea). {anio_reporte}</h2>
            <div class="controls" id="controlsDxGastro">
                <div class="control-group">
                    <label for="minWeekSliderDxGastro">Desde Semana: <span id="minWeekValueDxGastro">{global_min_week}</span></label>
                    <input type="range" id="minWeekSliderDxGastro" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
                <div class="control-group">
                    <label for="maxWeekSliderDxGastro">Hasta Semana: <span id="maxWeekValueDxGastro">{global_max_week}</span></label>
                    <input type="range" id="maxWeekSliderDxGastro" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartDxGastro"></canvas>
            </div>

            <div id="sectionDxCardio">
                <h2 id="sectionTitleDxCardio">Diagnósticos agrupados por enfermedad cardio-vascular (IAM y ACV). {anio_reporte}</h2>
                <div class="controls" id="controlsDxCardio">
                    <div class="control-group">
                        <label for="minWeekSliderDxCardio">Desde Semana: <span id="minWeekValueDxCardio">{global_min_week}</span></label>
                        <input type="range" id="minWeekSliderDxCardio" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="maxWeekSliderDxCardio">Hasta Semana: <span id="maxWeekValueDxCardio">{global_max_week}</span></label>
                        <input type="range" id="maxWeekSliderDxCardio" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                    </div>
                </div>
                <div class="chart-container" id="containerDxCardio">
                    <canvas id="chartDxCardio"></canvas>
                </div>
            </div>

            <h2 id="titleDxTec">Diagnósticos agrupados por TEC. {anio_reporte}</h2>
            <div class="controls" id="controlsDxTec">
                <div class="control-group">
                    <label for="minWeekSliderDxTec">Desde Semana: <span id="minWeekValueDxTec">{global_min_week}</span></label>
                    <input type="range" id="minWeekSliderDxTec" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
                <div class="control-group">
                    <label for="maxWeekSliderDxTec">Hasta Semana: <span id="maxWeekValueDxTec">{global_max_week}</span></label>
                    <input type="range" id="maxWeekSliderDxTec" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartDxTec"></canvas>
            </div>

            <h2 id="titleDxPonzonosos">Envenenamiento por animales ponzoñosos. {anio_reporte}</h2>
            <div class="controls" id="controlsDxPonzonosos">
                <div class="control-group">
                    <label for="minWeekSliderDxPonzonosos">Desde Semana: <span id="minWeekValueDxPonzonosos">{global_min_week}</span></label>
                    <input type="range" id="minWeekSliderDxPonzonosos" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
                <div class="control-group">
                    <label for="maxWeekSliderDxPonzonosos">Hasta Semana: <span id="maxWeekValueDxPonzonosos">{global_max_week}</span></label>
                    <input type="range" id="maxWeekSliderDxPonzonosos" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartDxPonzonosos"></canvas>
            </div>

            <h2 id="titleDxInmuno">Diagnósticos agrupados por enfermedades inmunoprevenibles. {anio_reporte}</h2>
            <div class="controls" id="controlsDxInmuno">
                <div class="control-group">
                    <label for="minWeekSliderDxInmuno">Desde Semana: <span id="minWeekValueDxInmuno">{global_min_week}</span></label>
                    <input type="range" id="minWeekSliderDxInmuno" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
                <div class="control-group">
                    <label for="maxWeekSliderDxInmuno">Hasta Semana: <span id="maxWeekValueDxInmuno">{global_max_week}</span></label>
                    <input type="range" id="maxWeekSliderDxInmuno" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartDxInmuno"></canvas>
            </div>

            <h2 id="titleInfoSinDx">% de Pacientes sin diagnóstico. Según semana elegida. {anio_reporte}</h2>
            <div class="controls" id="controlsSinDx">
                <div class="control-group">
                    <label for="weekSliderSinDx">Seleccionar Semana: <span id="weekValueSinDx">{global_min_week}</span></label>
                    <input type="range" id="weekSliderSinDx" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
            </div>
            <div id="infoSinDx" class="info-box">
                <p>% de Pacientes sin diagnóstico en Semana <span id="sinDxSemana" class="value">{global_min_week}</span>: <span id="sinDxValor" class="value">N/A</span> %</p>
                <small>Un paciente sin diagnóstico es un paciente que tiene fecha de atención y fecha de egreso, pero no tiene datos en las col diag_definitivo, diag_presuntivo y codigo_cie10.</small>
            </div>
        </div>

        <div id="servicioReportContent">
            <h2 id="titleChartIntDer">Internaciones y Derivaciones. Por semana. {anio_reporte}</h2>
            <div class="controls" id="controlsIntDer">
                <div class="control-group">
                    <label for="minWeekSliderIntDer">Desde Semana: <span id="minWeekValueIntDer">{global_min_week}</span></label>
                    <input type="range" id="minWeekSliderIntDer" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
                <div class="control-group">
                    <label for="maxWeekSliderIntDer">Hasta Semana: <span id="maxWeekValueIntDer">{global_max_week}</span></label>
                    <input type="range" id="maxWeekSliderIntDer" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartIntDer"></canvas>
            </div>

            <div class="table-container" id="containerTableEgresos">
                <h2>Tipos de Egreso - Semanal. {anio_reporte}</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="minWeekSliderTableEg">Desde Semana: <span id="minWeekValueTableEg">{global_min_week}</span></label>
                        <input type="range" id="minWeekSliderTableEg" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="maxWeekSliderTableEg">Hasta Semana: <span id="maxWeekValueTableEg">{global_max_week}</span></label>
                        <input type="range" id="maxWeekSliderTableEg" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                    </div>
                </div>
                <table class="custom-table" id="tableEgresos">
                    <thead>
                        <tr>
                            <th>Semana</th><th>Alta médica</th><th>Defunción</th><th>Derivación</th><th>Internación</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="table-container" id="containerTableFranjas">
                <h2>Consultas por Franja Horaria - Semanal. {anio_reporte}</h2>
                <div class="controls">
                    <div class="control-group">
                        <label for="minWeekSliderTableFr">Desde Semana: <span id="minWeekValueTableFr">{global_min_week}</span></label>
                        <input type="range" id="minWeekSliderTableFr" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="maxWeekSliderTableFr">Hasta Semana: <span id="maxWeekValueTableFr">{global_max_week}</span></label>
                        <input type="range" id="maxWeekSliderTableFr" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                    </div>
                </div>
                <table class="custom-table" id="tableFranjas">
                    <thead>
                        <tr>
                            <th>Semana</th><th>0-8 hs</th><th>8-16 hs</th><th>16-24 hs</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
            
            <h2 id="titleChartFranjaHora">Consultas por Hora del Día. {anio_reporte}</h2>
            <div class="controls" id="controlsFranjaHora">
                <div class="control-group">
                    <label for="weekSliderFranjaHora">Seleccionar Semana: <span id="weekValueFranjaHora">{global_min_week}</span></label>
                    <input type="range" id="weekSliderFranjaHora" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
            </div>
            <div class="chart-container">
                <canvas id="chartFranjaHora"></canvas>
            </div>

            <h2 id="titleInfoPermanencia">Tiempo de permanencia promedio. Según semana elegida. {anio_reporte}</h2>
            <div class="controls" id="controlsPermanencia">
                <div class="control-group">
                    <label for="weekSliderPermanencia">Seleccionar Semana: <span id="weekValuePermanencia">{global_min_week}</span></label>
                    <input type="range" id="weekSliderPermanencia" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                </div>
            </div>
            <div id="infoPermanencia" class="info-box">
                <p>Tiempo de permanencia promedio en Semana <span id="permanenciaSemana" class="value">{global_min_week}</span>: <span id="permanenciaValor" class="value">N/A</span> minutos</p>
                <small>Tiempo de permanencia se refiere al tiempo transcurrido entre el inicio de la prestación médica hasta el egreso (se calcula sobre los pacientes que requirieron internaciones o derivaciones).</small>
            </div>

            <div class="table-container" id="containerTableTriage">
                <h2>Tabla de Triage - Semanal. {anio_reporte}</h2>
                 <div class="controls" id="controlsTriageTable">
                    <div class="control-group">
                        <label for="minWeekSliderTriage">Desde Semana: <span id="minWeekValueTriage">{global_min_week}</span></label>
                        <input type="range" id="minWeekSliderTriage" min="{global_min_week}" max="{global_max_week}" value="{global_min_week}">
                    </div>
                    <div class="control-group">
                        <label for="maxWeekSliderTriage">Hasta Semana: <span id="maxWeekValueTriage">{global_max_week}</span></label>
                        <input type="range" id="maxWeekSliderTriage" min="{global_min_week}" max="{global_max_week}" value="{global_max_week}">
                    </div>
                </div>
                <table id="triageTable" class="modern-table">
                    <thead></thead>
                    <tbody></tbody>
                </table>
                <div id="noDataMessageTriage" style="display: none;">No hay datos de Triage para el rango de semanas seleccionado.</div>
            </div>

        </div>

        <footer><p><em>Reporte generado en el Departamento de Epidemiología y Estadística HPN - Fuente: INTRANET</em></p></footer>
    </div>

    <script>
        const G_MIN_WEEK = {global_min_week};
        const G_MAX_WEEK = {global_max_week};
        const ANIO_REPORTE_JS = {anio_reporte};
        
        const reportData = {{ 
            general: {{ 
                graficoDxResp: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoDxResp', "[]"))}'),
                graficoDxGastro: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoDxGastro', "[]"))}'),
                graficoDxCardio: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoDxCardio', "[]"))}'),
                graficoDxTec: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoDxTec', "[]"))}'),
                graficoDxPonzonosos: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoDxPonzonosos', "[]"))}'),
                graficoDxInmuno: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoDxInmuno', "[]"))}'),
                tablaEgresos: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_tablaEgresos', "[]"))}'),
                graficoIntDer: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoIntDer', "[]"))}'),
                tablaFranjas: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_tablaFranjas', "[]"))}'),
                graficoConsultasHora: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_graficoConsultasHora', "[]"))}'),
                tiempoPermanencia: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_tiempoPermanencia', "[]"))}'),
                porcentajeSinDx: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_porcentajeSinDx', "[]"))}'),
                tablaTriage: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_tablaTriage', "[]"))}'),
                triageColumnOrder: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('general_triageColumnOrder', "[]"))}')
            }},
            adultos: {{ 
                graficoDxResp: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoDxResp', "[]"))}'),
                graficoDxGastro: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoDxGastro', "[]"))}'),
                graficoDxCardio: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoDxCardio', "[]"))}'),
                graficoDxTec: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoDxTec', "[]"))}'),
                graficoDxPonzonosos: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoDxPonzonosos', "[]"))}'),
                graficoDxInmuno: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoDxInmuno', "[]"))}'),
                tablaEgresos: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_tablaEgresos', "[]"))}'),
                graficoIntDer: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoIntDer', "[]"))}'),
                tablaFranjas: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_tablaFranjas', "[]"))}'),
                graficoConsultasHora: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_graficoConsultasHora', "[]"))}'),
                tiempoPermanencia: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_tiempoPermanencia', "[]"))}'),
                porcentajeSinDx: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_porcentajeSinDx', "[]"))}'),
                tablaTriage: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_tablaTriage', "[]"))}'),
                triageColumnOrder: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('adultos_triageColumnOrder', "[]"))}')
            }},
            pediatria: {{ 
                graficoDxResp: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoDxResp', "[]"))}'),
                graficoDxGastro: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoDxGastro', "[]"))}'),
                graficoDxCardio: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoDxCardio', "[]"))}'), 
                graficoDxTec: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoDxTec', "[]"))}'),
                graficoDxPonzonosos: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoDxPonzonosos', "[]"))}'),
                graficoDxInmuno: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoDxInmuno', "[]"))}'),
                tablaEgresos: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_tablaEgresos', "[]"))}'),
                graficoIntDer: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoIntDer', "[]"))}'),
                tablaFranjas: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_tablaFranjas', "[]"))}'),
                graficoConsultasHora: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_graficoConsultasHora', "[]"))}'),
                tiempoPermanencia: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_tiempoPermanencia', "[]"))}'),
                porcentajeSinDx: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_porcentajeSinDx', "[]"))}'),
                tablaTriage: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_tablaTriage', "[]"))}'),
                triageColumnOrder: JSON.parse('{escape_json_for_js(datos_vistas_dict.get('pediatria_triageColumnOrder', "[]"))}')
            }}
        }};

        let currentPopulationType = 'adultos'; 
        let currentReportType = 'servicio';   
        let currentData = reportData[currentPopulationType]; 

        const minWeekSliderDxResp = document.getElementById('minWeekSliderDxResp');
        const maxWeekSliderDxResp = document.getElementById('maxWeekSliderDxResp');
        const minWeekValueDxResp = document.getElementById('minWeekValueDxResp');
        const maxWeekValueDxResp = document.getElementById('maxWeekValueDxResp');
        const minWeekSliderDxGastro = document.getElementById('minWeekSliderDxGastro');
        const maxWeekSliderDxGastro = document.getElementById('maxWeekSliderDxGastro');
        const minWeekValueDxGastro = document.getElementById('minWeekValueDxGastro');
        const maxWeekValueDxGastro = document.getElementById('maxWeekValueDxGastro');
        const minWeekSliderDxCardio = document.getElementById('minWeekSliderDxCardio');
        const maxWeekSliderDxCardio = document.getElementById('maxWeekSliderDxCardio');
        const minWeekValueDxCardio = document.getElementById('minWeekValueDxCardio');
        const maxWeekValueDxCardio = document.getElementById('maxWeekValueDxCardio');
        const sectionDxCardio = document.getElementById('sectionDxCardio');
        const minWeekSliderDxTec = document.getElementById('minWeekSliderDxTec');
        const maxWeekSliderDxTec = document.getElementById('maxWeekSliderDxTec');
        const minWeekValueDxTec = document.getElementById('minWeekValueDxTec');
        const maxWeekValueDxTec = document.getElementById('maxWeekValueDxTec');
        const minWeekSliderDxPonzonosos = document.getElementById('minWeekSliderDxPonzonosos');
        const maxWeekSliderDxPonzonosos = document.getElementById('maxWeekSliderDxPonzonosos');
        const minWeekValueDxPonzonosos = document.getElementById('minWeekValueDxPonzonosos');
        const maxWeekValueDxPonzonosos = document.getElementById('maxWeekValueDxPonzonosos');
        const minWeekSliderDxInmuno = document.getElementById('minWeekSliderDxInmuno');
        const maxWeekSliderDxInmuno = document.getElementById('maxWeekSliderDxInmuno');
        const minWeekValueDxInmuno = document.getElementById('minWeekValueDxInmuno');
        const maxWeekValueDxInmuno = document.getElementById('maxWeekValueDxInmuno');
        const weekSliderSinDx = document.getElementById('weekSliderSinDx');
        const weekValueSinDx = document.getElementById('weekValueSinDx');
        const sinDxSemanaEl = document.getElementById('sinDxSemana');
        const sinDxValorEl = document.getElementById('sinDxValor');
        
        const minWeekSliderIntDer = document.getElementById('minWeekSliderIntDer');
        const maxWeekSliderIntDer = document.getElementById('maxWeekSliderIntDer');
        const minWeekValueIntDer = document.getElementById('minWeekValueIntDer');
        const maxWeekValueIntDer = document.getElementById('maxWeekValueIntDer');
        const minWeekSliderTableEg = document.getElementById('minWeekSliderTableEg');
        const maxWeekSliderTableEg = document.getElementById('maxWeekSliderTableEg');
        const minWeekValueTableEg = document.getElementById('minWeekValueTableEg');
        const maxWeekValueTableEg = document.getElementById('maxWeekValueTableEg');
        const minWeekSliderTableFr = document.getElementById('minWeekSliderTableFr');
        const maxWeekSliderTableFr = document.getElementById('maxWeekSliderTableFr');
        const minWeekValueTableFr = document.getElementById('minWeekValueTableFr');
        const maxWeekValueTableFr = document.getElementById('maxWeekValueTableFr');
        const weekSliderFranjaHora = document.getElementById('weekSliderFranjaHora');
        const weekValueFranjaHora = document.getElementById('weekValueFranjaHora');
        const weekSliderPermanencia = document.getElementById('weekSliderPermanencia');
        const weekValuePermanencia = document.getElementById('weekValuePermanencia');
        const permanenciaSemanaEl = document.getElementById('permanenciaSemana');
        const permanenciaValorEl = document.getElementById('permanenciaValor');

        const minWeekSliderTriage = document.getElementById('minWeekSliderTriage');
        const maxWeekSliderTriage = document.getElementById('maxWeekSliderTriage');
        const minWeekValueTriage = document.getElementById('minWeekValueTriage');
        const maxWeekValueTriage = document.getElementById('maxWeekValueTriage');
        const triageTableBody = document.querySelector('#triageTable tbody');
        const triageTableHead = document.querySelector('#triageTable thead');
        const noDataMessageTriageDiv = document.getElementById('noDataMessageTriage');

        const reportTitle = document.getElementById('reportTitle');
        
        const ctxDxResp = document.getElementById('chartDxResp').getContext('2d');
        const ctxDxGastro = document.getElementById('chartDxGastro').getContext('2d');
        const ctxDxCardio = document.getElementById('chartDxCardio').getContext('2d');
        const ctxDxTec = document.getElementById('chartDxTec').getContext('2d');
        const ctxDxPonzonosos = document.getElementById('chartDxPonzonosos').getContext('2d');
        const ctxDxInmuno = document.getElementById('chartDxInmuno').getContext('2d');
        const ctxIntDer = document.getElementById('chartIntDer').getContext('2d');
        const ctxFranjaHora = document.getElementById('chartFranjaHora').getContext('2d');
        
        let chartDxResp = null; 
        let chartDxGastro = null;
        let chartDxCardio = null;
        let chartDxTec = null;
        let chartDxPonzonosos = null;
        let chartDxInmuno = null;
        let chartIntDer = null;
        let chartFranjaHora = null;

        const tableEgresosBody = document.getElementById('tableEgresos').getElementsByTagName('tbody')[0];
        const tableFranjasBody = document.getElementById('tableFranjas').getElementsByTagName('tbody')[0];
        
        const servicioMenuTrigger = document.getElementById('servicioMenuTrigger');
        const servicioSubmenu = document.getElementById('servicioSubmenu');
        const diagnosticosMenuTrigger = document.getElementById('diagnosticosMenuTrigger');
        const diagnosticosSubmenu = document.getElementById('diagnosticosSubmenu');

        {js_color_definitions}
        {js_menu_listeners}

        function setupSlider(sliderMin, sliderMax, valueMin, valueMax, updateFunction) {{
            sliderMin.min = G_MIN_WEEK; sliderMin.max = G_MAX_WEEK; sliderMin.value = String(G_MIN_WEEK);
            sliderMax.min = G_MIN_WEEK; sliderMax.max = G_MAX_WEEK; sliderMax.value = String(G_MAX_WEEK);
            valueMin.textContent = String(G_MIN_WEEK);
            valueMax.textContent = String(G_MAX_WEEK);
            
            const onInput = (event) => {{
                let minVal = parseInt(sliderMin.value);
                let maxVal = parseInt(sliderMax.value);
                if (minVal > maxVal) {{
                    if (event && event.target === sliderMin) sliderMax.value = String(minVal);
                    else if (event && event.target === sliderMax) sliderMin.value = String(maxVal);
                    else sliderMin.value = String(maxVal); 
                }}
                valueMin.textContent = sliderMin.value;
                valueMax.textContent = sliderMax.value;
                if (updateFunction) updateFunction();
            }};
            sliderMin.addEventListener('input', onInput);
            sliderMax.addEventListener('input', onInput);
        }}
        
        function setupSingleWeekSlider(slider, valueDisplay, updateFunction) {{
            slider.min = G_MIN_WEEK; slider.max = G_MAX_WEEK; slider.value = String(G_MIN_WEEK);
            valueDisplay.textContent = String(G_MIN_WEEK);
            slider.addEventListener('input', () => {{
                valueDisplay.textContent = slider.value;
                if (updateFunction) updateFunction();
            }});
        }}

        function updateMainContentVisibility() {{
            document.getElementById('servicioReportContent').style.display = (currentReportType === 'servicio') ? 'block' : 'none';
            document.getElementById('diagnosticosReportContent').style.display = (currentReportType === 'diagnosticos') ? 'block' : 'none';

            if (sectionDxCardio) {{
                if (currentReportType === 'diagnosticos' && currentPopulationType === 'pediatria') {{
                    sectionDxCardio.style.display = 'none';
                }} else if (currentReportType === 'diagnosticos') {{ 
                    sectionDxCardio.style.display = 'block';
                }}
            }}
        }}

        function updateAllSlidersAndDisplayedValues() {{
            const slidersToUpdate = [
                {{minS: minWeekSliderDxResp, maxS: maxWeekSliderDxResp, minV: minWeekValueDxResp, maxV: maxWeekValueDxResp}},
                {{minS: minWeekSliderDxGastro, maxS: maxWeekSliderDxGastro, minV: minWeekValueDxGastro, maxV: maxWeekValueDxGastro}},
                {{minS: minWeekSliderDxCardio, maxS: maxWeekSliderDxCardio, minV: minWeekValueDxCardio, maxV: maxWeekValueDxCardio}},
                {{minS: minWeekSliderDxTec, maxS: maxWeekSliderDxTec, minV: minWeekValueDxTec, maxV: maxWeekValueDxTec}},
                {{minS: minWeekSliderDxPonzonosos, maxS: maxWeekSliderDxPonzonosos, minV: minWeekValueDxPonzonosos, maxV: maxWeekValueDxPonzonosos}},
                {{minS: minWeekSliderDxInmuno, maxS: maxWeekSliderDxInmuno, minV: minWeekValueDxInmuno, maxV: maxWeekValueDxInmuno}},
                {{minS: minWeekSliderIntDer, maxS: maxWeekSliderIntDer, minV: minWeekValueIntDer, maxV: maxWeekValueIntDer}},
                {{minS: minWeekSliderTableEg, maxS: maxWeekSliderTableEg, minV: minWeekValueTableEg, maxV: maxWeekValueTableEg}},
                {{minS: minWeekSliderTableFr, maxS: maxWeekSliderTableFr, minV: minWeekValueTableFr, maxV: maxWeekValueTableFr}},
                {{minS: minWeekSliderTriage, maxS: maxWeekSliderTriage, minV: minWeekValueTriage, maxV: maxWeekValueTriage}}
            ];
            slidersToUpdate.forEach(s => {{
                s.minS.min = G_MIN_WEEK; s.minS.max = G_MAX_WEEK; s.minS.value = String(G_MIN_WEEK);
                s.maxS.min = G_MIN_WEEK; s.maxS.max = G_MAX_WEEK; s.maxS.value = String(G_MAX_WEEK);
                s.minV.textContent = String(G_MIN_WEEK); 
                s.maxV.textContent = String(G_MAX_WEEK);
            }});
            
            weekSliderFranjaHora.min = G_MIN_WEEK; weekSliderFranjaHora.max = G_MAX_WEEK; weekSliderFranjaHora.value = String(G_MIN_WEEK);
            weekValueFranjaHora.textContent = String(G_MIN_WEEK);
            weekSliderPermanencia.min = G_MIN_WEEK; weekSliderPermanencia.max = G_MAX_WEEK; weekSliderPermanencia.value = String(G_MIN_WEEK);
            weekValuePermanencia.textContent = String(G_MIN_WEEK);
            weekSliderSinDx.min = G_MIN_WEEK; weekSliderSinDx.max = G_MAX_WEEK; weekSliderSinDx.value = String(G_MIN_WEEK);
            weekValueSinDx.textContent = String(G_MIN_WEEK);
        }}

        function initializeSliders() {{
            setupSlider(minWeekSliderDxResp, maxWeekSliderDxResp, minWeekValueDxResp, maxWeekValueDxResp, updateChartDxResp);
            setupSlider(minWeekSliderDxGastro, maxWeekSliderDxGastro, minWeekValueDxGastro, maxWeekValueDxGastro, updateChartDxGastro);
            setupSlider(minWeekSliderDxCardio, maxWeekSliderDxCardio, minWeekValueDxCardio, maxWeekValueDxCardio, updateChartDxCardio);
            setupSlider(minWeekSliderDxTec, maxWeekSliderDxTec, minWeekValueDxTec, maxWeekValueDxTec, updateChartDxTec);
            setupSlider(minWeekSliderDxPonzonosos, maxWeekSliderDxPonzonosos, minWeekValueDxPonzonosos, maxWeekValueDxPonzonosos, updateChartDxPonzonosos);
            setupSlider(minWeekSliderDxInmuno, maxWeekSliderDxInmuno, minWeekValueDxInmuno, maxWeekValueDxInmuno, updateChartDxInmuno);
            setupSingleWeekSlider(weekSliderSinDx, weekValueSinDx, updateInfoSinDx);

            setupSlider(minWeekSliderIntDer, maxWeekSliderIntDer, minWeekValueIntDer, maxWeekValueIntDer, updateChartIntDer);
            setupSlider(minWeekSliderTableEg, maxWeekSliderTableEg, minWeekValueTableEg, maxWeekValueTableEg, updateTableEgresos);
            setupSlider(minWeekSliderTableFr, maxWeekSliderTableFr, minWeekValueTableFr, maxWeekValueTableFr, updateTableFranjas);
            setupSingleWeekSlider(weekSliderFranjaHora, weekValueFranjaHora, updateChartFranjaHora);
            setupSingleWeekSlider(weekSliderPermanencia, weekValuePermanencia, updateInfoPermanencia);
            setupSlider(minWeekSliderTriage, maxWeekSliderTriage, minWeekValueTriage, maxWeekValueTriage, renderTriageTable); 
        }}

        function updateChartsAndTables() {{
            if (currentReportType === 'diagnosticos') {{
                updateChartDxResp();
                updateChartDxGastro();
                if (!(currentPopulationType === 'pediatria')) {{ 
                    updateChartDxCardio();
                }} else if (chartDxCardio) {{ 
                     chartDxCardio.destroy(); chartDxCardio = null;
                     ctxDxCardio.clearRect(0,0, ctxDxCardio.canvas.width, ctxDxCardio.canvas.height);
                }}
                updateChartDxTec();
                updateChartDxPonzonosos();
                updateChartDxInmuno();
                updateInfoSinDx(); 
            }} else if (currentReportType === 'servicio') {{
                updateChartIntDer();
                updateTableEgresos();
                updateTableFranjas();
                updateChartFranjaHora();
                updateInfoPermanencia();
                renderTriageTable(); 
            }}
        }}
        
        document.querySelectorAll('.sidebar a').forEach(link => {{ 
            link.addEventListener('click', function(e) {{ 
                e.preventDefault();
                document.querySelectorAll('.sidebar a').forEach(l => l.classList.remove('active'));
                this.classList.add('active');
                
                const viewParts = this.dataset.view.split('_'); 
                currentReportType = viewParts[0];
                currentPopulationType = viewParts[1];

                currentData = reportData[currentPopulationType] || {{ 
                    graficoDxResp: [], graficoDxGastro: [], graficoDxCardio: [], graficoDxTec: [],
                    graficoDxPonzonosos: [], graficoDxInmuno: [],
                    tablaEgresos: [], graficoIntDer: [], tablaFranjas: [], 
                    graficoConsultasHora: [], tiempoPermanencia: [], porcentajeSinDx: [],
                    tablaTriage: [], triageColumnOrder: [] 
                }}; 
                
                let populationText = '';
                if (currentPopulationType === 'general') populationText = 'General';
                else if (currentPopulationType === 'adultos') populationText = 'Adultos';
                else if (currentPopulationType === 'pediatria') populationText = 'Pediatría';

                let titleBase = '';
                if (currentReportType === 'servicio') {{
                    titleBase = 'Reporte Servicio de Guardia';
                }} else if (currentReportType === 'diagnosticos') {{
                    titleBase = 'Diagnósticos de Egreso';
                }}
                reportTitle.textContent = `${{titleBase}} - ${{populationText}} (${{ANIO_REPORTE_JS}})`;
                
                updateMainContentVisibility();
                updateAllSlidersAndDisplayedValues(); 
                updateChartsAndTables(); 
            }});
        }}); 

        function populateTable(tbodyElement, data, columns, noDataMsg, colSpan, sliderMinWeek, sliderMaxWeek) {{
            tbodyElement.innerHTML = ''; 
            const minW = parseInt(sliderMinWeek.value);
            const maxW = parseInt(sliderMaxWeek.value);
            const filteredData = data.filter(d => d.Semana >= minW && d.Semana <= maxW);

            if (!filteredData || filteredData.length === 0) {{
                const row = tbodyElement.insertRow();
                const cell = row.insertCell();
                cell.colSpan = colSpan; 
                cell.textContent = noDataMsg + (data.length > 0 ? " (para el rango de semanas seleccionado)" : "");
                cell.style.textAlign = 'center';
                return;
            }}
            filteredData.forEach(rowData => {{
                const row = tbodyElement.insertRow();
                columns.forEach(colName => {{
                    const cell = row.insertCell();
                    cell.textContent = rowData[colName] !== undefined ? rowData[colName] : 0;
                }});
            }});
        }}

        function updateTableEgresos() {{
            const dataForTable = currentData.tablaEgresos || [];
            const cols = ['Semana', 'Alta médica', 'Defunción', 'Derivación', 'Internación'];
            populateTable(tableEgresosBody, dataForTable, cols, 'No hay datos de egresos', cols.length, minWeekSliderTableEg, maxWeekSliderTableEg);
        }}

        function updateTableFranjas() {{
            const dataForTable = currentData.tablaFranjas || [];
            const cols = ['Semana', '0-8 hs', '8-16 hs', '16-24 hs'];
            populateTable(tableFranjasBody, dataForTable, cols, 'No hay datos de franjas horarias', cols.length, minWeekSliderTableFr, maxWeekSliderTableFr);
        }}
        
        function renderTriageTable() {{
            const minWeek = parseInt(minWeekSliderTriage.value);
            const maxWeek = parseInt(maxWeekSliderTriage.value);

            minWeekValueTriage.textContent = minWeek;
            maxWeekValueTriage.textContent = maxWeek;

            const allTriageDataForView = currentData.tablaTriage || [];
            const triageColsOrder = currentData.triageColumnOrder && currentData.triageColumnOrder.length > 0 ? currentData.triageColumnOrder : ['Semana'];

            const filteredData = allTriageDataForView.filter(row => row.Semana >= minWeek && row.Semana <= maxWeek);

            triageTableBody.innerHTML = '';
            triageTableHead.innerHTML = ''; 

            const triageTableElement = document.getElementById('triageTable');

            if (allTriageDataForView.length === 0) {{
                noDataMessageTriageDiv.textContent = "No hay datos de Triage disponibles para esta vista.";
                noDataMessageTriageDiv.style.display = 'block';
                if (triageTableElement) triageTableElement.style.display = 'none';
                return;
            }}
            
            if (filteredData.length === 0) {{
                noDataMessageTriageDiv.textContent = "No hay datos de Triage para el rango de semanas seleccionado.";
                noDataMessageTriageDiv.style.display = 'block';
                if (triageTableElement) triageTableElement.style.display = 'none';
                return;
            }}

            noDataMessageTriageDiv.style.display = 'none';
            if (triageTableElement) triageTableElement.style.display = '';

            const headerRow = triageTableHead.insertRow();
            triageColsOrder.forEach(colName => {{
                const th = document.createElement('th');
                th.textContent = colName;
                if (triageHeaderColors[colName]) {{
                    th.style.backgroundColor = triageHeaderColors[colName];
                    th.style.color = '#333'; 
                }} else if (colName !== 'Semana') {{
                    th.style.backgroundColor = '#e9ecef'; 
                    th.style.color = '#333';
                }}
                headerRow.appendChild(th);
            }});

            filteredData.forEach(rowData => {{
                const row = triageTableBody.insertRow();
                triageColsOrder.forEach(colName => {{
                    const cell = row.insertCell();
                    if (colName === 'Semana') {{
                        cell.textContent = rowData[colName];
                    }} else {{
                        const triageData = rowData[colName];
                        if (triageData && typeof triageData === 'object' && 'abs' in triageData && 'pct' in triageData) {{
                             cell.innerHTML = `${{triageData.abs}} (${{triageData.pct.toFixed(1)}}%)`;
                        }} else {{
                            cell.innerHTML = "0 (0.0%)"; 
                        }}
                    }}
                }});
            }});
        }}

        function createMultiLineChart(chartInstance, canvasContext, dataForChart, xLabel, yLabel, titlePrefix, sliderMinWeek, sliderMaxWeek, dataKey = 'Dx', specificDx = null, fullTitle = null) {{
            let currentChart = chartInstance;
            if (currentChart) {{ currentChart.destroy(); }}
            
            const canvas = canvasContext.canvas;
            canvasContext.clearRect(0, 0, canvas.width, canvas.height);

            const displayTitlePrefix = titlePrefix || "Gráfico"; 

            if (!dataForChart || dataForChart.length === 0) {{
                 canvasContext.font = "16px Arial"; canvasContext.fillStyle = "#888"; canvasContext.textAlign = "center";
                 canvasContext.fillText(`No hay datos para ${{displayTitlePrefix.toLowerCase()}}.`, canvas.width / 2, canvas.height / 2);
                 return null; 
            }}
            
            const minW = parseInt(sliderMinWeek.value);
            const maxW = parseInt(sliderMaxWeek.value);
            
            let filteredForDx = dataForChart;
            if (specificDx && Array.isArray(specificDx)) {{
                filteredForDx = dataForChart.filter(d => specificDx.includes(d[dataKey]));
            }} else if (specificDx && typeof specificDx === 'string') {{
                 filteredForDx = dataForChart.filter(d => d[dataKey] === specificDx);
            }}

            const filtered = filteredForDx.filter(d => d.Semana >= minW && d.Semana <= maxW);
            
            if (filtered.length === 0) {{ 
                 canvasContext.font = "16px Arial"; canvasContext.fillStyle = "#888"; canvasContext.textAlign = "center";
                 canvasContext.fillText(`No hay datos para ${{displayTitlePrefix.toLowerCase()}} en el rango seleccionado.`, canvas.width / 2, canvas.height / 2);
                 return null;
            }}

            const groupKeys = [...new Set(filtered.map(d => d[dataKey]))].sort();
            const weeks = [...new Set(filtered.map(d => d.Semana))].sort((a, b) => a - b);

            const datasets = groupKeys.map((key, index) => {{
                const counts = weeks.map(w => {{
                    const entry = filtered.find(d => d.Semana === w && d[dataKey] === key);
                    return entry ? entry.Conteo : 0;
                }});
                const assignedColor = specificDxColors[key] || colorPalette[index % colorPalette.length];
                return {{
                    label: key, data: counts, borderColor: assignedColor,
                    backgroundColor: assignedColor + '1A', fill: false, tension: 0.1, borderWidth: 2
                }};
            }});

            const chartTitleText = fullTitle ? fullTitle : ` ${{displayTitlePrefix}} (Semanas ${{minW}}-${{maxW}}). ${{ANIO_REPORTE_JS}}`;

            return new Chart(canvasContext, {{
                type: 'line',
                data: {{ labels: weeks, datasets: datasets }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{ 
                        legend: {{ position: 'top' }}, 
                        title: {{ display: true, text: chartTitleText }} 
                    }},
                    scales: {{
                        x: {{ title: {{ display: true, text: xLabel }}, 
                             ticks: {{ callback: function(v, i, t) {{ const maxT = 20; const lbl = this.getLabelForValue(v); if(weeks.length > maxT) {{ return (i % Math.ceil(weeks.length/maxT) === 0) ? lbl : null; }} return lbl; }} }}
                        }},
                        y: {{ title: {{ display: true, text: yLabel }}, beginAtZero: true, ticks: {{ precision: 0 }} }}
                    }}
                }}
            }});
        }}

        function createSingleLineTimeChart(chartInstance, canvasContext, dataForChart, selectedWeek, xLabel, yLabel, titlePrefix, fullTitle = null) {{
            if (chartInstance) {{ chartInstance.destroy(); }}
            const canvas = canvasContext.canvas;
            canvasContext.clearRect(0, 0, canvas.width, canvas.height);

            if (!dataForChart || dataForChart.length === 0) {{
                canvasContext.font = "16px Arial"; canvasContext.fillStyle = "#888"; canvasContext.textAlign = "center";
                canvasContext.fillText(`No hay datos de ${{titlePrefix.toLowerCase()}} disponibles.`, canvas.width / 2, canvas.height / 2);
                return null;
            }}
            
            const weekData = dataForChart.filter(d => d.Semana === selectedWeek);

            if (weekData.length === 0) {{
                canvasContext.font = "16px Arial"; canvasContext.fillStyle = "#888"; canvasContext.textAlign = "center";
                canvasContext.fillText(`No hay datos de ${{titlePrefix.toLowerCase()}} para la semana ${{selectedWeek}}.`, canvas.width / 2, canvas.height / 2);
                return null;
            }}
            
            const hours = Array.from({{ length: 24 }}, (_, i) => i); 
            const counts = hours.map(h => {{
                const entry = weekData.find(d => d.Hora_Ingreso_Num === h);
                return entry ? entry.Cantidad : 0;
            }});
            
            const chartTitleText = fullTitle ? `${{fullTitle}} (Semana ${{selectedWeek}})` : `${{titlePrefix}} (Semana ${{selectedWeek}}). ${{ANIO_REPORTE_JS}}`;

            return new Chart(canvasContext, {{
                type: 'line',
                data: {{
                    labels: hours.map(h => ` ${{h.toString().padStart(2,'0')}}:00`), 
                    datasets: [{{
                        label: `Consultas Semana ${{selectedWeek}}`,
                        data: counts,
                        borderColor: colorPalette[0],
                        backgroundColor: colorPalette[0] + '1A',
                        fill: false, tension: 0.1, borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{ legend: {{ position: 'top' }}, title: {{ display: true, text: chartTitleText }} }},
                    scales: {{
                        x: {{ title: {{ display: true, text: xLabel }} }},
                        y: {{ title: {{ display: true, text: yLabel }}, beginAtZero: true, ticks: {{ precision: 0 }} }}
                    }}
                }}
            }});
        }}

        function updateChartDxResp() {{
            chartDxResp = createMultiLineChart(chartDxResp, ctxDxResp, currentData.graficoDxResp, 'Semana Epidemiológica', 'Número de Casos', 'Diagnósticos Respiratorios', minWeekSliderDxResp, maxWeekSliderDxResp, 'Dx', null, `Diagnósticos agrupados por causa respiratoria (Semanas ${{minWeekSliderDxResp.value}}-${{maxWeekSliderDxResp.value}}). ${{ANIO_REPORTE_JS}}`);
        }}
        function updateChartDxGastro() {{
            chartDxGastro = createMultiLineChart(chartDxGastro, ctxDxGastro, currentData.graficoDxGastro, 'Semana Epidemiológica', 'Número de Casos', 'Diagnósticos Gastro-Intestinales', minWeekSliderDxGastro, maxWeekSliderDxGastro, 'Dx', null, `Diagnósticos agrupados por causa gastro-entérica (diarrea) (Semanas ${{minWeekSliderDxGastro.value}}-${{maxWeekSliderDxGastro.value}}). ${{ANIO_REPORTE_JS}}`);
        }}
        function updateChartDxCardio() {{
            if (currentReportType === 'diagnosticos' && currentPopulationType === 'pediatria') {{
                if(chartDxCardio) {{ chartDxCardio.destroy(); chartDxCardio = null; }}
                ctxDxCardio.clearRect(0,0, ctxDxCardio.canvas.width, ctxDxCardio.canvas.height);
                return; 
            }}
            chartDxCardio = createMultiLineChart(chartDxCardio, ctxDxCardio, currentData.graficoDxCardio, 'Semana Epidemiológica', 'Número de Casos', 'Diagnósticos Cardio-Vasculares', minWeekSliderDxCardio, maxWeekSliderDxCardio, 'Dx', null, `Diagnósticos agrupados por enfermedad cardio-vascular (IAM y ACV) (Semanas ${{minWeekSliderDxCardio.value}}-${{maxWeekSliderDxCardio.value}}). ${{ANIO_REPORTE_JS}}`);
        }}
        function updateChartDxTec() {{
            chartDxTec = createMultiLineChart(chartDxTec, ctxDxTec, currentData.graficoDxTec, 'Semana Epidemiológica', 'Número de Casos', 'Diagnósticos TEC', minWeekSliderDxTec, maxWeekSliderDxTec, 'Dx', null, `Diagnósticos agrupados por TEC (Semanas ${{minWeekSliderDxTec.value}}-${{maxWeekSliderDxTec.value}}). ${{ANIO_REPORTE_JS}}`);
        }}
        function updateChartDxPonzonosos() {{
            chartDxPonzonosos = createMultiLineChart(chartDxPonzonosos, ctxDxPonzonosos, currentData.graficoDxPonzonosos, 'Semana Epidemiológica', 'Número de Casos', 'Envenenamiento por Animales Ponzoñosos', minWeekSliderDxPonzonosos, maxWeekSliderDxPonzonosos, 'Dx', null, `Envenenamiento por animales ponzoñosos (Semanas ${{minWeekSliderDxPonzonosos.value}}-${{maxWeekSliderDxPonzonosos.value}}). ${{ANIO_REPORTE_JS}}`);
        }}
        function updateChartDxInmuno() {{
            chartDxInmuno = createMultiLineChart(chartDxInmuno, ctxDxInmuno, currentData.graficoDxInmuno, 'Semana Epidemiológica', 'Número de Casos', 'Diagnósticos Inmunoprevenibles', minWeekSliderDxInmuno, maxWeekSliderDxInmuno, 'Dx', null, `Diagnósticos agrupados por enfermedades inmunoprevenibles (Semanas ${{minWeekSliderDxInmuno.value}}-${{maxWeekSliderDxInmuno.value}}). ${{ANIO_REPORTE_JS}}`);
        }}

        function updateChartIntDer() {{
            chartIntDer = createMultiLineChart(
                chartIntDer, 
                ctxIntDer, 
                currentData.graficoIntDer, 
                'Semana Epidemiológica', 
                'Cantidad', 
                'Internaciones y Derivaciones', 
                minWeekSliderIntDer, 
                maxWeekSliderIntDer, 
                'tipo_de_egreso', 
                null, 
                `Internaciones y Derivaciones (Semanas ${{minWeekSliderIntDer.value}}-${{maxWeekSliderIntDer.value}}). Por semana. ${{ANIO_REPORTE_JS}}`
            );
        }}

        function updateChartFranjaHora() {{
            const selectedWeek = parseInt(weekSliderFranjaHora.value);
            chartFranjaHora = createSingleLineTimeChart(chartFranjaHora, ctxFranjaHora, currentData.graficoConsultasHora, selectedWeek, 'Hora del Día', 'Número de Consultas', 'Consultas por Hora', `Consultas por Hora del Día. ${{ANIO_REPORTE_JS}}`);
        }}

        function updateInfoPermanencia() {{
            const selectedWeek = parseInt(weekSliderPermanencia.value);
            permanenciaSemanaEl.textContent = selectedWeek;
            const dataPermanencia = currentData.tiempoPermanencia || [];
            const weekEntry = dataPermanencia.find(d => d.Semana === selectedWeek);
            
            if (weekEntry && weekEntry.PermanenciaPromedio !== undefined && weekEntry.PermanenciaPromedio !== null) {{
                permanenciaValorEl.textContent = weekEntry.PermanenciaPromedio.toFixed(1);
            }} else {{
                permanenciaValorEl.textContent = "N/A";
            }}
        }}

        function updateInfoSinDx() {{
            const selectedWeek = parseInt(weekSliderSinDx.value);
            sinDxSemanaEl.textContent = selectedWeek;
            const dataSinDx = currentData.porcentajeSinDx || [];
            const weekEntry = dataSinDx.find(d => d.Semana === selectedWeek);
            
            if (weekEntry && weekEntry.PorcentajeSinDx !== undefined && weekEntry.PorcentajeSinDx !== null) {{
                sinDxValorEl.textContent = weekEntry.PorcentajeSinDx.toFixed(1);
            }} else {{
                sinDxValorEl.textContent = "N/A";
            }}
        }}
        
        function initializeReport() {{
            servicioSubmenu.classList.add('open');
            servicioMenuTrigger.innerHTML = `Servicio de Guardia ${{servicioSubmenu.classList.contains('open') ? '&#9652;' : '&#9662;'}}`;
            
            diagnosticosSubmenu.classList.add('open');
            diagnosticosMenuTrigger.innerHTML = `Guardia Diagnósticos ${{diagnosticosSubmenu.classList.contains('open') ? '&#9652;' : '&#9662;'}}`; 
            
            document.querySelector('a[data-view="servicio_adultos"]').classList.add('active');

            currentPopulationType = 'adultos';
            currentReportType = 'servicio';
            currentData = reportData[currentPopulationType]; 
            reportTitle.textContent = `Reporte Servicio de Guardia - Adultos (${{ANIO_REPORTE_JS}})`;
            
            initializeSliders(); 
            updateMainContentVisibility(); 
            updateAllSlidersAndDisplayedValues(); 
            updateChartsAndTables(); 
        }}

        initializeReport();
    </script>
</body>
</html>"""
    report_path = os.path.join(output_folder, "reporte_guardias_semanal.html")
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Reporte HTML multi-vista guardado exitosamente en: {report_path}")
    except Exception as e:
        print(f"Error fatal al guardar el reporte HTML multi-vista: {str(e)}\n{traceback.format_exc()}")

# ================================== #
# ===     EJECUCIÓN PRINCIPAL    === #
# ================================== #
if __name__ == "__main__":
    print(f"INICIO DEL PROCESO DE CONSOLIDACIÓN Y REPORTE PARA EL AÑO {ANIO_REPORTE}")

    if not os.path.exists(CARPETA_RESULTADOS_CSV):
        print(f"Creando carpeta de resultados CSV: {CARPETA_RESULTADOS_CSV}")
        os.makedirs(CARPETA_RESULTADOS_CSV)
    
    if not os.path.exists(CARPETA_REPORTE_HTML):
        print(f"Creando carpeta para reporte HTML: {CARPETA_REPORTE_HTML}")
        os.makedirs(CARPETA_REPORTE_HTML, exist_ok=True)

    print("\n--- Carga de Datos Base ---")
    df_fechas = cargar_tabla_fechas(PATH_FECHAS)
    if df_fechas is None:
         print(f"\nADVERTENCIA: No se pudo cargar el archivo de calendario. El filtrado por año ({ANIO_REPORTE}) (Año_se) no se podrá realizar usando el calendario.")

    print("\n--- Procesamiento de Datos por Servicio ---")
    df_adultos_raw = combinar_csv_en_carpeta(CARPETA_ADULTOS, "Adultos", df_fechas)
    df_pediatria_raw = combinar_csv_en_carpeta(CARPETA_PEDIATRIA, "Pediatria", df_fechas)

    print("\n--- Creación de DataFrames para Reporte ---")
    df_guardia_adultos = df_adultos_raw.copy() if df_adultos_raw is not None else pd.DataFrame()
    df_guardia_pediatria = df_pediatria_raw.copy() if df_pediatria_raw is not None else pd.DataFrame()
    
    df_final = pd.DataFrame(); valid_dfs_for_final = []
    if not df_guardia_adultos.empty: valid_dfs_for_final.append(df_guardia_adultos)
    if not df_guardia_pediatria.empty: valid_dfs_for_final.append(df_guardia_pediatria)
    
    if valid_dfs_for_final: 
        df_final = pd.concat(valid_dfs_for_final, ignore_index=True)
        print(f"DataFrame Guardia General (df_final) creado con {len(df_final)} filas (datos para el año {ANIO_REPORTE} (Año_se) si el calendario fue aplicado).")
    else:
        print(f"DataFrame Guardia General (df_final) no se pudo crear (0 filas).")


    print("\n--- Exportación de Datos CSV ---")
    if not df_guardia_adultos.empty:
        guardar_con_verificacion(df_guardia_adultos, os.path.join(CARPETA_RESULTADOS_CSV, f"adultos_combinados_{ANIO_REPORTE}.csv"))
    if not df_guardia_pediatria.empty:
        guardar_con_verificacion(df_guardia_pediatria, os.path.join(CARPETA_RESULTADOS_CSV, f"pediatria_combinados_{ANIO_REPORTE}.csv"))
    if not df_final.empty:
        guardar_con_verificacion(df_final, os.path.join(CARPETA_RESULTADOS_CSV, f"todos_pacientes_general_{ANIO_REPORTE}.csv"))

    print("\n--- Preparación de Datos para Reporte HTML ---")
    (gDxResp_gen, min_g, max_g, tEg_gen, gID_gen, tFr_gen, gCH_gen, tP_gen, 
     gDxGastro_gen, gDxCardio_gen, gDxTec_gen, gDxPonz_gen, gDxInmuno_gen, pSinDx_gen,
     tablaTriage_gen, triageColOrder_gen) = preparar_datos_para_reporte(df_final, f"Guardia General ({ANIO_REPORTE})")
    
    (gDxResp_adu, min_a, max_a, tEg_adu, gID_adu, tFr_adu, gCH_adu, tP_adu,
     gDxGastro_adu, gDxCardio_adu, gDxTec_adu, gDxPonz_adu, gDxInmuno_adu, pSinDx_adu,
     tablaTriage_adu, triageColOrder_adu) = preparar_datos_para_reporte(df_guardia_adultos, f"Guardia Adultos ({ANIO_REPORTE})")

    (gDxResp_ped, min_p, max_p, tEg_ped, gID_ped, tFr_ped, gCH_ped, tP_ped,
     gDxGastro_ped, gDxCardio_ped, gDxTec_ped, gDxPonz_ped, gDxInmuno_ped, pSinDx_ped,
     tablaTriage_ped, triageColOrder_ped) = preparar_datos_para_reporte(df_guardia_pediatria, f"Guardia Pediatria ({ANIO_REPORTE})")
    
    datos_para_html = {
        'general_graficoDxResp': gDxResp_gen, 'general_graficoDxGastro': gDxGastro_gen, 
        'general_graficoDxCardio': gDxCardio_gen, 'general_graficoDxTec': gDxTec_gen,
        'general_graficoDxPonzonosos': gDxPonz_gen, 'general_graficoDxInmuno': gDxInmuno_gen,
        'general_tablaEgresos': tEg_gen, 'general_graficoIntDer': gID_gen, 
        'general_tablaFranjas': tFr_gen, 'general_graficoConsultasHora': gCH_gen, 
        'general_tiempoPermanencia': tP_gen, 'general_porcentajeSinDx': pSinDx_gen,
        'general_tablaTriage': tablaTriage_gen, 'general_triageColumnOrder': triageColOrder_gen,

        'adultos_graficoDxResp': gDxResp_adu, 'adultos_graficoDxGastro': gDxGastro_adu,
        'adultos_graficoDxCardio': gDxCardio_adu, 'adultos_graficoDxTec': gDxTec_adu,
        'adultos_graficoDxPonzonosos': gDxPonz_adu, 'adultos_graficoDxInmuno': gDxInmuno_adu,
        'adultos_tablaEgresos': tEg_adu, 'adultos_graficoIntDer': gID_adu, 
        'adultos_tablaFranjas': tFr_adu, 'adultos_graficoConsultasHora': gCH_adu, 
        'adultos_tiempoPermanencia': tP_adu, 'adultos_porcentajeSinDx': pSinDx_adu,
        'adultos_tablaTriage': tablaTriage_adu, 'adultos_triageColumnOrder': triageColOrder_adu,

        'pediatria_graficoDxResp': gDxResp_ped, 'pediatria_graficoDxGastro': gDxGastro_ped,
        'pediatria_graficoDxCardio': gDxCardio_ped, 'pediatria_graficoDxTec': gDxTec_ped,
        'pediatria_graficoDxPonzonosos': gDxPonz_ped, 'pediatria_graficoDxInmuno': gDxInmuno_ped,
        'pediatria_tablaEgresos': tEg_ped, 'pediatria_graficoIntDer': gID_ped, 
        'pediatria_tablaFranjas': tFr_ped, 'pediatria_graficoConsultasHora': gCH_ped, 
        'pediatria_tiempoPermanencia': tP_ped, 'pediatria_porcentajeSinDx': pSinDx_ped,
        'pediatria_tablaTriage': tablaTriage_ped, 'pediatria_triageColumnOrder': triageColOrder_ped,
    }
    
    all_min_weeks_from_data = [w for w in [min_g, min_a, min_p] if w is not None and not pd.isna(w)] 
    all_max_weeks_from_data = [w for w in [max_g, max_a, max_p] if w is not None and not pd.isna(w)]
    
    global_min_week = 1 
    global_max_week = 52 

    if all_min_weeks_from_data:
        global_min_week = int(min(all_min_weeks_from_data))
    if all_max_weeks_from_data:
        global_max_week = int(max(all_max_weeks_from_data))
    
    if global_min_week > global_max_week : 
        if all_min_weeks_from_data and not all_max_weeks_from_data:
            global_max_week = global_min_week
        elif not all_min_weeks_from_data and all_max_weeks_from_data:
            global_min_week = global_max_week
        else: 
             global_min_week, global_max_week = global_max_week, global_min_week 
    
    if global_min_week > global_max_week : 
        global_max_week = global_min_week 

    print(f"Rango global de semanas para sliders (año {ANIO_REPORTE}): {global_min_week} - {global_max_week}")

    print("\n--- Generación de Reporte HTML Interactivo ---")
    has_data_for_report = any( (isinstance(datos_para_html[key], str) and datos_para_html[key] != "[]" and datos_para_html[key] != "") for key in datos_para_html)
    
    logo_base64_data = get_image_as_base64(PATH_LOGO)

    if has_data_for_report or \
       any(datos_para_html.get(f"{view}_tablaTriage", "[]") != "[]" for view in ["general", "adultos", "pediatria"]):
         generar_reporte_html_interactivo(datos_para_html, CARPETA_REPORTE_HTML, global_min_week, global_max_week, logo_base64_data, ANIO_REPORTE)
    else:
        print(f"No hay datos suficientes en ninguna vista para generar el reporte HTML interactivo para el año {ANIO_REPORTE}.")

    print("\nPROCESO COMPLETADO")
    print(f"Archivos CSV para el año {ANIO_REPORTE} guardados en: {CARPETA_RESULTADOS_CSV}")
    print(f"Reporte HTML para el año {ANIO_REPORTE} guardado en: {CARPETA_REPORTE_HTML}")
