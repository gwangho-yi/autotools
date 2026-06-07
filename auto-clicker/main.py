import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt


def main():
    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("auto-clicker")
    win.setFixedSize(560, 400)
    win.setStyleSheet("background-color: #1a1a2e;")
    lbl = QLabel("auto-clicker")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: white; font-size: 24px;")
    QVBoxLayout(win).addWidget(lbl)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
