"""
rendimiento_internacion.py  (UI page)
=====================================
Página del informe de Rendimiento de Internación.

Layout (igual que el resto de módulos de informes):
  - Campo Input  : archivo Excel de rendimiento + [Abrir] [Seleccionar]
  - Campo Output : carpeta de salida del HTML    + [Abrir] [Seleccionar]
  - Botones [Generar Informe] [Abrir Informe HTML]
  - Consola de output (read-only, monoespaciada)
  - Botones [Copiar] [Limpiar]

El procesamiento corre en un QThread para no bloquear la UI.
"""

from pathlib import Path
import subprocess
import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import theme
from app.modules.informes.rendimiento_internacion.reader import DEFAULT_EXCEL_PATH
from app.modules.informes.rendimiento_internacion.report import (
    DEFAULT_OUTPUT_DIR,
    HTML_OUTPUT_NAME,
    generar_informe,
)


# ══════════════════════════════════════════════════════════════
#  WORKER THREAD
# ══════════════════════════════════════════════════════════════

class _RendimientoWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, input_excel: Path, output_dir: Path):
        super().__init__()
        self._input_excel = input_excel
        self._output_dir = output_dir

    def run(self):
        try:
            generar_informe(
                input_excel=self._input_excel,
                output_dir=self._output_dir,
                log=self.log_signal.emit,
            )
        except Exception as e:
            self.log_signal.emit(f"\n[ERROR CRITICO] {e}")
        finally:
            self.finished_signal.emit()


# ══════════════════════════════════════════════════════════════
#  PAGINA
# ══════════════════════════════════════════════════════════════

class RendimientoInternacionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _RendimientoWorker | None = None
        self._build_ui()
        self._set_defaults()

    # ── Construccion UI ──────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 32)
        root.setSpacing(0)

        # Titulo
        title = QLabel("Rendimiento Internación")
        title.setObjectName("page_title")
        root.addWidget(title)
        root.addSpacing(4)

        subtitle = QLabel(
            "Consolida las estadísticas de internación general: ocupación de camas, "
            "giro, días de estada y tasas por servicio."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        root.addSpacing(24)

        # ── Campo Input ──────────────────────────────────────────
        root.addWidget(self._make_section_label("Archivo Excel de Rendimiento (input)"))
        root.addSpacing(6)
        self._input_excel_field, row_input = self._make_path_row(is_file=True)
        root.addLayout(row_input)
        root.addSpacing(14)

        # ── Campo Output ─────────────────────────────────────────
        root.addWidget(self._make_section_label("Carpeta de salida (output)"))
        root.addSpacing(6)
        self._output_field, row_output = self._make_path_row(is_file=False)
        root.addLayout(row_output)
        root.addSpacing(16)

        # ── Botones de ejecucion ─────────────────────────────────
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

        # ── Botones consola ──────────────────────────────────────
        copy_btn = self._make_console_btn("Copiar", self._copy_console)
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
        self._input_excel_field.setText(str(DEFAULT_EXCEL_PATH))
        self._output_field.setText(str(DEFAULT_OUTPUT_DIR))
        self._refresh_html_btn()

    # ── Acciones de archivo / carpeta ────────────────────────────

    def _select_file(self, field: QLineEdit):
        start = field.text() or str(Path.home())
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo Excel", start, "Archivos Excel (*.xlsx *.xls)"
        )
        if chosen:
            field.setText(chosen)

    def _select_folder(self, field: QLineEdit):
        start = field.text() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta", start)
        if path:
            field.setText(path)
            self._refresh_html_btn()

    def _open_folder(self, field: QLineEdit, is_file: bool = False):
        path = field.text().strip()
        if not path:
            return
        p = Path(path)
        if is_file:
            p = p.parent
        p.mkdir(parents=True, exist_ok=True)
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
        input_text = self._input_excel_field.text().strip()
        output_text = self._output_field.text().strip()

        if not input_text:
            self._log("  [ERROR] Selecciona el archivo Excel de entrada.")
            return
        if not output_text:
            self._log("  [ERROR] Selecciona una carpeta de salida.")
            return

        inp_excel = Path(input_text)
        if not inp_excel.exists():
            self._log(f"  [ERROR] No se encuentra el archivo: {inp_excel}")
            return

        self._console.clear()
        self._run_btn.setEnabled(False)
        self._open_html_btn.setEnabled(False)

        self._worker = _RendimientoWorker(inp_excel, Path(output_text))
        self._worker.log_signal.connect(self._log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self):
        self._run_btn.setEnabled(True)
        self._refresh_html_btn()
        self._log("\n[PROCESO FINALIZADO]")

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
