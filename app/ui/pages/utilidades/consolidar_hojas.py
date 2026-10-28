"""
consolidar_hojas.py  (UI page)
==============================
Pagina de la utilidad Consolidar Hojas.

Layout:
  - Campo Input  : archivo Excel   + [Abrir carpeta] [Seleccionar archivo]
  - Campo Output : carpeta del Excel + [Abrir carpeta] [Seleccionar carpeta]
  - Boton [Procesar]
  - Consola de output (read-only, monoespaciado)
  - Botones [Copiar] [Limpiar]

El procesamiento corre en un QThread para no bloquear la UI.
"""
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFileDialog,
    QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor, QFont

from app.config import theme
from app.modules.utilidades.consolidar_hojas.processor import (
    consolidar_hojas,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_PATH,
)


# ══════════════════════════════════════════════════════════════
#  WORKER THREAD
# ══════════════════════════════════════════════════════════════

class _ConsolidarHojasWorker(QThread):
    log_signal      = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, input_file: Path, output_path: Path):
        super().__init__()
        self._input  = input_file
        self._output = output_path

    def run(self):
        try:
            consolidar_hojas(self._input, self._output, self.log_signal.emit)
        except Exception as e:
            self.log_signal.emit(f"\n[ERROR CRITICO] {e}")
        finally:
            self.finished_signal.emit()


# ══════════════════════════════════════════════════════════════
#  PAGINA
# ══════════════════════════════════════════════════════════════

class ConsolidarHojasPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _ConsolidarHojasWorker | None = None
        self._build_ui()
        self._set_defaults()

    # ── Construccion UI ──────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 32)
        root.setSpacing(0)

        title = QLabel("Limpiar Excel Quirófano")
        title.setObjectName("page_title")
        root.addWidget(title)
        root.addSpacing(4)

        subtitle = QLabel(
            "Une todas las hojas de un Excel en una única hoja (nuevo archivo Excel): "
            "toma los encabezados de la primera hoja y conserva solo las filas que "
            "tienen dato en la columna J."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        root.addSpacing(28)

        # ── Input ────────────────────────────────────────────────
        root.addWidget(self._make_section_label("Archivo Excel (input)"))
        root.addSpacing(6)
        self._input_field, input_row = self._make_file_row()
        root.addLayout(input_row)
        root.addSpacing(18)

        # ── Output ───────────────────────────────────────────────
        root.addWidget(self._make_section_label("Carpeta de salida (output)"))
        root.addSpacing(6)
        self._output_field, output_row = self._make_folder_row()
        root.addLayout(output_row)
        root.addSpacing(18)

        # ── Boton Procesar ───────────────────────────────────────
        self._run_btn = QPushButton("Procesar")
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

        run_row = QHBoxLayout()
        run_row.addWidget(self._run_btn)
        run_row.addStretch()
        root.addLayout(run_row)
        root.addSpacing(24)

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

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {theme.COLOR_TEXT_SECONDARY};"
            f"font-size: {theme.FONT_SIZE_SMALL}px;"
            f"text-transform: uppercase;"
            f"letter-spacing: 1px;"
        )
        return lbl

    def _make_path_field(self) -> QLineEdit:
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
        return field

    def _make_file_row(self):
        field = self._make_path_field()
        open_btn   = self._make_action_btn("Abrir carpeta")
        select_btn = self._make_action_btn("Seleccionar archivo")
        open_btn.clicked.connect(self._open_file_folder)
        select_btn.clicked.connect(self._select_file)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(field)
        row.addWidget(open_btn)
        row.addWidget(select_btn)
        return field, row

    def _make_folder_row(self):
        field = self._make_path_field()
        open_btn   = self._make_action_btn("Abrir carpeta")
        select_btn = self._make_action_btn("Seleccionar carpeta")
        open_btn.clicked.connect(lambda: self._open_folder(field))
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
        self._input_field.setText("")
        self._output_field.setText(str(DEFAULT_OUTPUT_PATH))

    # ── Acciones de archivo / carpeta ────────────────────────────

    def _select_file(self):
        current = self._input_field.text().strip()
        start_dir = str(Path(current).parent) if current else str(DEFAULT_INPUT_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo Excel", start_dir,
            "Archivos Excel (*.xlsx *.xlsm *.xls);;Todos los archivos (*)",
        )
        if path:
            self._input_field.setText(str(Path(path)))

    def _open_file_folder(self):
        current = self._input_field.text().strip()
        folder = Path(current).parent if current else DEFAULT_INPUT_DIR
        if folder.is_dir():
            subprocess.Popen(f'explorer "{folder}"')
        else:
            self._log(f"  [ERROR] La carpeta no existe: {folder}")

    def _select_folder(self, field: QLineEdit):
        path = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta", field.text().strip()
        )
        if path:
            field.setText(str(Path(path)))

    def _open_folder(self, field: QLineEdit):
        path = field.text().strip()
        if path:
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(f'explorer "{p}"')

    # ── Ejecucion ────────────────────────────────────────────────

    def _run(self):
        input_path  = self._input_field.text().strip()
        output_path = self._output_field.text().strip()

        if not input_path:
            self._log("  [ERROR] Selecciona el archivo Excel.")
            return
        if not output_path:
            self._log("  [ERROR] Selecciona una carpeta de salida.")
            return

        inp = Path(input_path)
        if not inp.is_file():
            self._log(f"  [ERROR] El archivo no existe: {inp}")
            return

        self._run_btn.setEnabled(False)
        self._worker = _ConsolidarHojasWorker(inp, Path(output_path))
        self._worker.log_signal.connect(self._log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self):
        self._run_btn.setEnabled(True)

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
