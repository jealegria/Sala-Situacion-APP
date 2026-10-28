"""
quirofano.py  (UI page)
=======================
Pagina del informe de Quirofano.

Layout (igual que el resto de modulos de informes):
  - Campo Input 1 : carpeta Programadas  + [Abrir] [Seleccionar]
  - Campo Input 2 : carpeta Urgencias    + [Abrir] [Seleccionar]
  - Campo Input 3 : carpeta Circulante   + [Abrir] [Seleccionar]
  - Campo Input 4 : archivo Calendario SE + [Abrir] [Seleccionar]
  - Campo Output  : carpeta de salida del HTML + [Abrir] [Seleccionar]
  - Campo Año     : año del reporte (por defecto: año actual)
  - Botones [Generar Informe] [Abrir Informe HTML]
  - Consola de output (read-only, monoespaciada)
  - Botones [Copiar] [Limpiar]

El procesamiento corre en un QThread para no bloquear la UI.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFileDialog,
    QSizePolicy, QSpinBox, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor, QFont

from app.config import theme
from app.modules.informes.quirofano.report import (
    generar_informe,
    DEFAULT_INPUT_PROGRAMADAS,
    DEFAULT_INPUT_URGENCIAS,
    DEFAULT_INPUT_CIRCULANTE,
    DEFAULT_CALENDARIO_FILE,
    DEFAULT_OUTPUT_PATH,
    HTML_OUTPUT_NAME,
)


# ══════════════════════════════════════════════════════════════
#  WORKER THREAD
# ══════════════════════════════════════════════════════════════

class _QuirofanoWorker(QThread):
    log_signal      = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, programadas: Path, urgencias: Path, circulante: Path,
                 calendario: Path, output_dir: Path, anio: int):
        super().__init__()
        self._programadas = programadas
        self._urgencias   = urgencias
        self._circulante  = circulante
        self._calendario  = calendario
        self._output      = output_dir
        self._anio        = anio

    def run(self):
        try:
            generar_informe(
                input_programadas=self._programadas,
                input_urgencias=self._urgencias,
                input_circulante=self._circulante,
                calendario_file=self._calendario,
                output_dir=self._output,
                log=self.log_signal.emit,
                anio=self._anio,
            )
        except Exception as e:
            self.log_signal.emit(f"\n[ERROR CRITICO] {e}")
        finally:
            self.finished_signal.emit()


# ══════════════════════════════════════════════════════════════
#  PAGINA
# ══════════════════════════════════════════════════════════════

class QuirofanoPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _QuirofanoWorker | None = None
        self._build_ui()
        self._set_defaults()

    # ── Construccion UI ──────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 32)
        root.setSpacing(0)

        # Titulo
        title = QLabel("Quirófano")
        title.setObjectName("page_title")
        root.addWidget(title)
        root.addSpacing(4)

        subtitle = QLabel(
            "Genera el informe interactivo HTML de Quirófano: carga de registros, "
            "suspensiones, servicios, tiempos, situación del paciente y demografía."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        root.addSpacing(24)

        # ── Inputs ───────────────────────────────────────────────
        self._programadas_field, row = self._make_path_row(is_file=False)
        self._add_field(root, "Carpeta Programadas (input)", row)

        self._urgencias_field, row = self._make_path_row(is_file=False)
        self._add_field(root, "Carpeta Urgencias (input)", row)

        self._circulante_field, row = self._make_path_row(is_file=False)
        self._add_field(root, "Carpeta Circulante (input)", row)

        self._calendario_field, row = self._make_path_row(is_file=True)
        self._add_field(root, "Archivo Calendario SE (input)", row)

        self._output_field, row = self._make_path_row(is_file=False)
        self._add_field(root, "Carpeta de salida (output)", row, last=True)

        # ── Año + botones ────────────────────────────────────────
        root.addWidget(self._make_section_label("Año del reporte"))
        root.addSpacing(6)

        self._anio_spin = QSpinBox()
        self._anio_spin.setRange(2020, 2100)
        self._anio_spin.setValue(datetime.now().year)
        self._anio_spin.setFixedHeight(36)
        self._anio_spin.setFixedWidth(100)
        self._anio_spin.setStyleSheet(
            f"QSpinBox {{"
            f"  background-color: {theme.COLOR_BG_SECONDARY};"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"  border: 1px solid {theme.COLOR_BORDER};"
            f"  border-radius: 5px;"
            f"  padding: 0 8px;"
            f"  font-size: {theme.FONT_SIZE_BASE}px;"
            f"}}"
            f"QSpinBox::up-button, QSpinBox::down-button {{"
            f"  background-color: {theme.COLOR_BG_SECONDARY};"
            f"  border: none;"
            f"}}"
        )

        self._run_btn = QPushButton("Generar Informe")
        self._run_btn.setFixedHeight(42)
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {theme.COLOR_BUTTON_ACTIVE};"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  font-size: {theme.FONT_SIZE_BASE}px;"
            f"  font-weight: bold;"
            f"  padding: 0 24px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {theme.COLOR_BUTTON_HOVER};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  background-color: #334155;"
            f"  color: #64748b;"
            f"}}"
        )
        self._run_btn.clicked.connect(self._run)

        self._open_html_btn = self._make_action_btn("Abrir Informe HTML")
        self._open_html_btn.setFixedHeight(42)
        self._open_html_btn.setEnabled(False)
        self._open_html_btn.clicked.connect(self._open_html)

        run_row = QHBoxLayout()
        run_row.setSpacing(12)
        run_row.addWidget(self._anio_spin)
        run_row.addWidget(self._run_btn)
        run_row.addWidget(self._open_html_btn)
        run_row.addStretch()
        root.addLayout(run_row)
        root.addSpacing(20)

        # ── Consola ──────────────────────────────────────────────
        root.addWidget(self._make_section_label("Consola"))
        root.addSpacing(6)

        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        font_console = QFont("Consolas", 10)
        font_console.setStyleHint(QFont.StyleHint.Monospace)
        self._console.setFont(font_console)
        self._console.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color: #0f0e0d;"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"  border: 1px solid {theme.COLOR_BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 10px;"
            f"}}"
        )
        root.addWidget(self._console)
        root.addSpacing(10)

        copy_btn  = self._make_console_btn("Copiar",  self._copy_console)
        clear_btn = self._make_console_btn("Limpiar", self._clear_console)

        console_btns = QHBoxLayout()
        console_btns.setSpacing(10)
        console_btns.addWidget(copy_btn)
        console_btns.addWidget(clear_btn)
        console_btns.addStretch()
        root.addLayout(console_btns)

    # ── Helpers de widgets ───────────────────────────────────────

    def _add_field(self, root: QVBoxLayout, label: str, row: QHBoxLayout, last: bool = False):
        root.addWidget(self._make_section_label(label))
        root.addSpacing(6)
        root.addLayout(row)
        root.addSpacing(16 if last else 14)

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {theme.COLOR_TEXT_SECONDARY};"
            f"font-size: {theme.FONT_SIZE_SMALL}px;"
            f"text-transform: uppercase;"
            f"letter-spacing: 1px;"
        )
        return lbl

    def _make_path_row(self, is_file: bool):
        field = QLineEdit()
        field.setReadOnly(True)
        field.setFixedHeight(36)
        field.setStyleSheet(
            f"QLineEdit {{"
            f"  background-color: {theme.COLOR_BG_SECONDARY};"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"  border: 1px solid {theme.COLOR_BORDER};"
            f"  border-radius: 5px;"
            f"  padding: 0 10px;"
            f"  font-size: {theme.FONT_SIZE_BASE}px;"
            f"}}"
        )

        open_btn = self._make_action_btn("Abrir carpeta")
        select_btn = self._make_action_btn(
            "Seleccionar archivo" if is_file else "Seleccionar carpeta"
        )

        open_btn.clicked.connect(lambda: self._open_folder(field, is_file))
        if is_file:
            select_btn.clicked.connect(lambda: self._select_file(field))
        else:
            select_btn.clicked.connect(lambda: self._select_folder(field))

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(field)
        row.addWidget(open_btn)
        row.addWidget(select_btn)
        return field, row

    def _make_action_btn(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {theme.COLOR_BG_SECONDARY};"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"  border: 1px solid {theme.COLOR_BORDER};"
            f"  border-radius: 5px;"
            f"  padding: 0 14px;"
            f"  font-size: {theme.FONT_SIZE_SMALL}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {theme.COLOR_BUTTON_HOVER};"
            f"  border-color: {theme.COLOR_BUTTON_HOVER};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: #64748b;"
            f"}}"
        )
        return btn

    def _make_console_btn(self, label: str, slot) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {theme.COLOR_BG_SECONDARY};"
            f"  color: {theme.COLOR_TEXT_SECONDARY};"
            f"  border: 1px solid {theme.COLOR_BORDER};"
            f"  border-radius: 5px;"
            f"  padding: 0 16px;"
            f"  font-size: {theme.FONT_SIZE_SMALL}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"  border-color: {theme.COLOR_TEXT_SECONDARY};"
            f"}}"
        )
        return btn

    # ── Defaults ─────────────────────────────────────────────────

    def _set_defaults(self):
        # Las rutas a las bases quedan vacias hasta definirlas en report.py
        self._programadas_field.setText(str(DEFAULT_INPUT_PROGRAMADAS or ""))
        self._urgencias_field.setText(str(DEFAULT_INPUT_URGENCIAS or ""))
        self._circulante_field.setText(str(DEFAULT_INPUT_CIRCULANTE or ""))
        self._calendario_field.setText(str(DEFAULT_CALENDARIO_FILE or ""))
        self._output_field.setText(str(DEFAULT_OUTPUT_PATH))
        self._refresh_html_btn()

    # ── Acciones de archivo / carpeta ────────────────────────────

    def _select_file(self, field: QLineEdit):
        current = field.text().strip()
        start = str(Path(current).parent) if current else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", start, "Archivos CSV (*.csv);;Todos los archivos (*)"
        )
        if path:
            field.setText(str(Path(path)))

    def _select_folder(self, field: QLineEdit):
        start = field.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta", start)
        if path:
            field.setText(str(Path(path)))
            self._refresh_html_btn()

    def _open_folder(self, field: QLineEdit, is_file: bool = False):
        path = field.text().strip()
        if not path:
            return
        p = Path(path)
        if is_file:
            p = p.parent
        if not p.is_dir():
            if field is self._output_field:
                p.mkdir(parents=True, exist_ok=True)
            else:
                self._log(f"  [ERROR] La carpeta no existe: {p}")
                return
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{p}"')
        else:
            subprocess.Popen(["xdg-open", str(p)])

    def _html_path(self) -> Path:
        return Path(self._output_field.text().strip()) / HTML_OUTPUT_NAME

    def _refresh_html_btn(self):
        self._open_html_btn.setEnabled(self._html_path().exists())

    def _open_html(self):
        out_file = self._html_path()
        if out_file.exists():
            if sys.platform == "win32":
                subprocess.Popen(f'start "" "{out_file}"', shell=True)
            else:
                subprocess.Popen(["xdg-open", str(out_file)])

    # ── Ejecucion ────────────────────────────────────────────────

    def _run(self):
        campos = [
            ("la carpeta de Programadas", self._programadas_field),
            ("la carpeta de Urgencias", self._urgencias_field),
            ("la carpeta de Circulante", self._circulante_field),
            ("el archivo de Calendario SE", self._calendario_field),
            ("una carpeta de salida", self._output_field),
        ]
        for nombre, campo in campos:
            if not campo.text().strip():
                self._log(f"  [ERROR] Selecciona {nombre}.")
                return

        self._console.clear()
        self._run_btn.setEnabled(False)
        self._open_html_btn.setEnabled(False)

        self._worker = _QuirofanoWorker(
            Path(self._programadas_field.text().strip()),
            Path(self._urgencias_field.text().strip()),
            Path(self._circulante_field.text().strip()),
            Path(self._calendario_field.text().strip()),
            Path(self._output_field.text().strip()),
            self._anio_spin.value(),
        )
        self._worker.log_signal.connect(self._log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self):
        self._run_btn.setEnabled(True)
        self._refresh_html_btn()

    # ── Consola ──────────────────────────────────────────────────

    def _log(self, text: str):
        self._console.append(text)
        self._console.moveCursor(QTextCursor.MoveOperation.End)

    def _copy_console(self):
        text = self._console.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _clear_console(self):
        self._console.clear()
