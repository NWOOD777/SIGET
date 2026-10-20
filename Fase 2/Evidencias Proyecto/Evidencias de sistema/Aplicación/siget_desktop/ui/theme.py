"""Tema de escritorio basado en los mockups de media fidelidad de SIGET."""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ESTILO_GLOBAL = """
QWidget {
    color: #172b4d;
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog, QWidget#loginWindow { background: #f1f5f9; }
QLabel { background: transparent; }
QLabel#tituloPrincipal { font-size: 22px; font-weight: 700; color: #10213d; }
QLabel#subtitulo { color: #64748b; font-size: 12px; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #172b4d; }
QLabel#brandMark { background: #1d4ed8; color: white; border-radius: 8px; font-size: 18px; font-weight: 800; padding: 8px; }
QLabel#brandName { color: white; font-size: 18px; font-weight: 800; }
QLabel#brandCaption { color: #94a3b8; font-size: 11px; }
QLabel#navigationCaption { color: #8294af; font-size: 10px; font-weight: 700; padding: 16px 18px 8px; }
QLabel#sidebarFooter { color: #94a3b8; padding: 16px; font-size: 11px; }
QFrame#desktopSidebar, QFrame#loginBrand { background: #101b30; border: none; }
QFrame#desktopHeader { background: white; border-bottom: 1px solid #dce5f0; }
QLabel#headerCaption { color: #64748b; font-size: 12px; }
QLabel#userName { color: #172b4d; font-weight: 600; }
QFrame#loginCard, QFrame#profileCard, QFrame#permissionsCard, QFrame[moduleCard="true"], QFrame#filterBar {
    background: white; border: 1px solid #dce5f0; border-radius: 8px;
}
QLabel#loginHeadline { color: white; font-size: 25px; font-weight: 700; }
QLabel#loginDescription { color: #c1cede; font-size: 13px; }
QLabel#badgeRolAdmin { background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe; border-radius: 4px; padding: 4px 8px; font-size: 11px; }
QLabel#badgeRolTecnico { background: #e0f2fe; color: #075985; border: 1px solid #bae6fd; border-radius: 4px; padding: 4px 8px; font-size: 11px; }
QLabel#badgeRol { background: #f1f5f9; color: #475569; border: 1px solid #dce5f0; border-radius: 4px; padding: 4px 8px; font-size: 11px; }
QLabel[messageTone="info"] { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px 12px; }
QLabel[messageTone="empty"] { background: white; color: #64748b; border: 1px dashed #cbd5e1; border-radius: 6px; padding: 12px; }
QLabel[messageTone="error"] { background: #fff1f2; color: #9f1239; border: 1px solid #fecdd3; border-radius: 6px; padding: 10px 12px; }
QLabel[messageTone="success"] { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; border-radius: 6px; padding: 10px 12px; }
QLineEdit, QComboBox {
    background: white; color: #172b4d; border: 1px solid #d3deec; border-radius: 5px;
    padding: 8px 10px; min-height: 18px; selection-background-color: #dbeafe; selection-color: #1e3a8a;
}
QLineEdit { placeholder-text-color: #64748b; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #2563eb; }
QLineEdit:disabled, QComboBox:disabled { background: #f1f5f9; color: #64748b; }
QComboBox { padding-right: 28px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: none; }
QComboBox::down-arrow { image: url("__FLECHA_ABAJO__"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: white; color: #172b4d; border: 1px solid #cbd5e1; outline: none;
    selection-background-color: #dbeafe; selection-color: #1e3a8a; padding: 4px;
}
QComboBox QAbstractItemView::item { min-height: 28px; padding: 4px 8px; }
QComboBox QAbstractItemView::item:selected { background: #dbeafe; color: #1e3a8a; }
QPushButton { background: #1d4ed8; color: white; border: 1px solid #1d4ed8; border-radius: 5px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #1e40af; border-color: #1e40af; }
QPushButton:pressed { background: #1e3a8a; }
QPushButton:focus { border: 2px solid #60a5fa; }
QPushButton:disabled { background: #e2e8f0; color: #64748b; border: 1px solid #cbd5e1; }
QPushButton#btnSecundario { background: white; color: #334155; border: 1px solid #d3deec; }
QPushButton#btnSecundario:hover { background: #eff6ff; color: #1d4ed8; border-color: #93c5fd; }
QPushButton#btnPeligro { background: #be123c; color: white; border-color: #be123c; }
QPushButton#btnPeligro:hover { background: #9f1239; }
QPushButton#btnSecundario:disabled, QPushButton#btnPeligro:disabled { background: #f1f5f9; color: #64748b; border-color: #dce5f0; }
QTableWidget {
    background: white; alternate-background-color: #f8fafc; color: #172b4d;
    border: 1px solid #dce5f0; border-radius: 7px; gridline-color: #edf2f7;
    selection-background-color: #dbeafe; selection-color: #172b4d; outline: none;
}
QTableWidget::item { padding: 8px; border-bottom: 1px solid #edf2f7; }
QTableWidget::item:selected { background: #dbeafe; color: #172b4d; }
QHeaderView { background: #f8fafc; }
QHeaderView::section { background: #f8fafc; color: #64748b; padding: 10px 8px; border: none; border-bottom: 1px solid #dce5f0; font-size: 11px; font-weight: 600; }
QTableCornerButton::section { background: #f8fafc; border: none; }
QListWidget#desktopNavigation { background: #101b30; border: none; outline: none; padding: 0 10px; }
QListWidget#desktopNavigation::item { color: #c1cede; padding: 12px 10px; margin: 2px 0; border-radius: 5px; }
QListWidget#desktopNavigation::item:hover { background: #1e2d47; color: white; }
QListWidget#desktopNavigation::item:selected { background: #1d4ed8; color: white; font-weight: 600; }
QListWidget#desktopNavigation::item:disabled { color: #8294af; background: transparent; }
QProgressBar { background: #dbeafe; border: none; border-radius: 2px; text-align: center; color: #1e40af; }
QProgressBar::chunk { background: #2563eb; border-radius: 2px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f1f5f9; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #cbd5e1; min-height: 25px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #f1f5f9; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #cbd5e1; min-width: 25px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip { background: #172b4d; color: white; border: none; padding: 6px; }
QMenu { background: white; color: #172b4d; border: 1px solid #dce5f0; }
QMenu::item:selected { background: #dbeafe; color: #1e3a8a; }
""".replace("__FLECHA_ABAJO__", (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix())


def aplicar_tema(app: QApplication) -> None:
    """Fija el estilo y la paleta para que los controles no hereden el tema del sistema."""
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f1f5f9",
        QPalette.ColorRole.WindowText: "#172b4d",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f8fafc",
        QPalette.ColorRole.Text: "#172b4d",
        QPalette.ColorRole.Button: "#ffffff",
        QPalette.ColorRole.ButtonText: "#172b4d",
        QPalette.ColorRole.Highlight: "#dbeafe",
        QPalette.ColorRole.HighlightedText: "#172b4d",
        QPalette.ColorRole.PlaceholderText: "#64748b",
        QPalette.ColorRole.ToolTipBase: "#172b4d",
        QPalette.ColorRole.ToolTipText: "#ffffff",
        QPalette.ColorRole.Link: "#1d4ed8",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#64748b"))
    app.setPalette(palette)
    app.setFont(QFont("Sans Serif", 10))
    app.setStyleSheet(ESTILO_GLOBAL)
