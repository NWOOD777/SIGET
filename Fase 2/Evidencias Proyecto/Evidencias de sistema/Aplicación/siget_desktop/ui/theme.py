"""
Estilos visuales y paleta corporativa para la interfaz de escritorio PySide6 de SIGET.
"""

ESTILO_GLOBAL = """
QMainWindow, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #f1f5f9;
}

QLabel {
    color: #f1f5f9;
}

QLabel#tituloPrincipal {
    font-size: 20px;
    font-weight: bold;
    color: #38bdf8;
}

QLabel#subtitulo {
    font-size: 13px;
    color: #94a3b8;
}

QLabel#badgeRolAdmin {
    background-color: #4c1d95;
    color: #c4b5fd;
    border: 1px solid #6d28d9;
    border-radius: 4px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 11px;
}

QLabel#badgeRolTecnico {
    background-color: #0c4a6e;
    color: #7dd3fc;
    border: 1px solid #0284c7;
    border-radius: 4px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 11px;
}

QLineEdit, QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
    selection-background-color: #0284c7;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
}

QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #0369a1;
}

QPushButton:pressed {
    background-color: #075985;
}

QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
}

QPushButton#btnSecundario {
    background-color: #1e293b;
    color: #cbd5e1;
    border: 1px solid #475569;
}

QPushButton#btnSecundario:hover {
    background-color: #334155;
    color: #f8fafc;
}

QPushButton#btnPeligro {
    background-color: #991b1b;
    color: #fee2e2;
}

QPushButton#btnPeligro:hover {
    background-color: #b91c1c;
}

QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    gridline-color: #334155;
    color: #f8fafc;
    selection-background-color: #0369a1;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #334155;
    font-weight: 600;
    font-size: 12px;
}

QListWidget {
    background-color: #0f172a;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 10px 14px;
    border-radius: 6px;
    color: #cbd5e1;
    font-weight: 500;
}

QListWidget::item:hover {
    background-color: #1e293b;
    color: #f8fafc;
}

QListWidget::item:selected {
    background-color: #0369a1;
    color: #ffffff;
    font-weight: 600;
}

QListWidget::item:disabled {
    color: #475569;
    background-color: transparent;
}

QProgressBar {
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    background-color: #1e293b;
}

QProgressBar::chunk {
    background-color: #0284c7;
    border-radius: 3px;
}

QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}
"""
