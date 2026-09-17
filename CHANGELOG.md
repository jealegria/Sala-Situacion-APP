# Changelog

## [0.5.0-beta] - 2026-09-17

### Agregado
- Soporte para grupos de menu colapsables en la barra lateral (Sidebar) y navegacion en MainWindow.
- Modulo Informes:
  - Submodulo Guardia:
    - Logica completa de consolidacion y generacion de reporte HTML epidemiologico semanal (reporte_guardias_semanal.html).
    - Vistas para Guardia Adultos, Guardia Pediatria y Consolidado General.
    - Filtros dinamicos por semana epidemiologica, analisis por causas (respiratorias, gastrointestinales, cardiovasculares, TEC, ponzonosos, inmunoprevenibles), consultas por hora, tiempos de permanencia y tabla de triage.
    - UI con selectores independientes para guardia adultos, guardia pediatria, carpeta de salida, seleccion de anio y consola con hilos en segundo plano.
  - Submodulo SM y Tocogineco:
    - Consolidacion de agendas y generacion de informe HTML interactivo para Salud Mental y Tocoginecologia.
    - Mapeo de terminos SNOMED y cruce con calendario epidemiologico relacional.
    - UI con selectores de ruta, anio, ejecucion en segundo plano y consola.
  - Submodulo Vacunatorio:
    - Consolidacion de agendas y prestaciones fuera de agenda para vacunatorio.
    - Depuracion de registros sin identificacion y descarte de turnos invalidos.
    - Mapeo de conceptos SNOMED y generacion de panel interactivo poblacional HTML con distribucion por mes, tipo de prestacion, franjas horarias, localidades y rangos etarios.
    - UI con selectores para agendas, fuera de agenda, internacion andes, carpeta de salida, anio y consola.
  - Submodulo Imagenes (estructura y pagina placeholder).
- Respaldo de scripts fuente originales en la carpeta _legacy/.
