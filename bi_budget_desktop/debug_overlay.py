# debug_overlay.py

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit
)
from PySide6.QtCore import Qt


class DebugOverlay(QWidget):
    def __init__(self):
        # Make it a NORMAL WINDOW (this fixes everything)
        super().__init__(None)

        self.setWindowTitle("Debug Console")

        # Normal window + always on top
        self.setWindowFlags(
            Qt.Window |                 # <-- REAL WINDOW
            Qt.WindowStaysOnTopHint     # stays above your app
        )

        self.setMinimumSize(420, 260)

        # -------------------------
        # STYLING
        # -------------------------
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 230);
                color: white;
                border: 2px solid #ff4444;
                border-radius: 8px;
                font-size: 14px;
            }
            QLabel#header {
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
                background-color: rgba(255, 0, 0, 180);
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 40);
                border: 1px solid #ffffff;
                border-radius: 4px;
                padding: 2px 6px;
                color: white;
            }
            QTextEdit {
                background-color: rgba(0, 0, 0, 120);
                color: #dddddd;
                border: none;
                padding: 6px;
            }
        """)

        # -------------------------
        # LAYOUT
        # -------------------------
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # HEADER BAR
        header_bar = QWidget()
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(6, 4, 6, 4)

        self.header = QLabel("DEBUG CONSOLE")
        self.header.setObjectName("header")

        # Snap button
        snap_btn = QPushButton("↖")
        snap_btn.setFixedWidth(28)
        snap_btn.clicked.connect(self.snap_top_left)

        header_layout.addWidget(self.header)
        header_layout.addWidget(snap_btn)

        main_layout.addWidget(header_bar)

        # INFO PANEL
        self.info_label = QLabel("Debug info will appear here")
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        # LOG AREA
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)

    # -------------------------
    # SNAP BUTTON
    # -------------------------
    def snap_top_left(self):
        self.move(10, 10)

    # -------------------------
    # UPDATE INFO PANEL
    # -------------------------
    def update_text(self, text: str):
        self.info_label.setText(text)

    # -------------------------
    # LOGGING
    # -------------------------
    def log(self, message: str):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
