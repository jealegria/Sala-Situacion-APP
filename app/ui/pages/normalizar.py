"""
normalizar.py  (UI page)
=========================
Pagina de Normalizacion de archivos tabulares.

Layout:
  - Campo Input  : ruta + [Abrir] [Seleccionar]
  - Campo Output : ruta + [Abrir] [Seleccionar]
  - Boton [Normalizar]
  - Consola de output (read-only, monoespaciado)
  - Botones [Copiar] [Limpiar]

El procesamiento corre en un QThread para no bloquear la UI.
"""
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFileDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor, QFont, QClipboard
from PyQt6.QtWidgets import QApplication

from app.config import theme
from app.config.paths import get_module_input_path, get_module_output_path
from app.modules.normalizar.processor import procesar_carpeta


# ══════════════════════════════════════════════════════════════
#  WORKER THREAD — evita bloquear la UI durante el proceso
# ══════════════════════════════════════════════════════════════

class _NormalizarWorker(QThread):
    log_signal      = pyqtSignal(str)   # Emite cada linea de log
    finished_signal = pyqtSignal()      # Emite cuando termina

    def __init__(self, input_path: Path, output_path: Path):
        super().__init__()
        self._input  = input_path
        self._output = output_path

    def run(self):
        try:
            procesar_carpeta(self._input, self._output, self.log_signal.emit)
        except Exception as e:
            self.log_signal.emit(f"\n[ERROR CRITICO] {e}")
        finally:
            self.finished_signal.emit()


# ══════════════════════════════════════════════════════════════
#  PAGINA PRINCIPAL
# ══════════════════════════════════════════════════════════════

class NormalizarPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _NormalizarWorker | None = None
        self._build_ui()
        self._set_default_output()

    # ── Construccion de la UI ────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 32)
        root.setSpacing(0)

        # Titulo
        title = QLabel("Normalizar")
        title.setObjectName("page_title")
        root.addWidget(title)
        root.addSpacing(4)

        subtitle = QLabel(
            "Lee archivos CSV / Excel de una carpeta, normaliza columnas y formatos, "
            "y guarda los resultados."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        root.addSpacing(28)

        # ── Carpeta Input ────────────────────────────────────────
        root.addWidget(self._make_section_label("Carpeta de entrada"))
        root.addSpacing(6)
        self._input_field, input_row = self._make_path_row("input")
        root.addLayout(input_row)
        root.addSpacing(18)

        # ── Carpeta Output ───────────────────────────────────────
        root.addWidget(self._make_section_label("Carpeta de salida"))
        root.addSpacing(6)
        self._output_field, output_row = self._make_path_row("output")
        root.addLayout(output_row)
        root.addSpacing(28)

        # ── Boton Normalizar ─────────────────────────────────────
        self._run_btn = QPushButton("Normalizar")
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

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)
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

        # ── Botones de consola ───────────────────────────────────
        copy_btn  = self._make_console_btn("Copiar",  self._copy_console)
        clear_btn = self._make_console_btn("Limpiar", self._clear_console)

        console_btns = QHBoxLayout()
        console_btns.setSpacing(10)
        console_btns.addWidget(copy_btn)
        console_btns.addWidget(clear_btn)
        console_btns.addStretch()
        root.addLayout(console_btns)

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {theme.COLOR_TEXT_SECONDARY};"
            f"font-size: {theme.FONT_SIZE_SMALL}px;"
            f"text-transform: uppercase;"
            f"letter-spacing: 1px;"
        )
        return lbl

    def _make_path_row(self, field_id: str):
        """Crea un QLineEdit + boton Abrir + boton Seleccionar."""
        field = QLineEdit()
        field.setObjectName(f"path_field_{field_id}")
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

        open_btn   = self._make_action_btn("Abrir carpeta")
        select_btn = self._make_action_btn("Seleccionar carpeta")

        if field_id == "input":
            open_btn.clicked.connect(lambda: self._open_folder(self._input_field))
            select_btn.clicked.connect(lambda: self._select_folder(self._input_field))
        else:
            open_btn.clicked.connect(lambda: self._open_folder(self._output_field))
            select_btn.clicked.connect(lambda: self._select_folder(self._output_field))

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

    # ── Valores por defecto ──────────────────────────────────────

    def _set_default_output(self):
        self._input_field.setText(str(get_module_input_path("normalizar")))
        self._output_field.setText(str(get_module_output_path("normalizar")))

    # ── Acciones de carpeta ──────────────────────────────────────

    def _select_folder(self, field: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if path:
            field.setText(path)

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
            self._log("  [ERROR] Selecciona una carpeta de entrada.")
            return
        if not output_path:
            self._log("  [ERROR] Selecciona una carpeta de salida.")
            return

        inp = Path(input_path)
        out = Path(output_path)

        if not inp.is_dir():
            self._log(f"  [ERROR] La carpeta de entrada no existe: {inp}")
            return

        self._run_btn.setEnabled(False)
        self._worker = _NormalizarWorker(inp, out)
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
