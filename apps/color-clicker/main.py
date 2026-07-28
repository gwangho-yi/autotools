import sys
from autotools_shared.bootstrap import create_app
from ui.main_window import MainWindow


def main():
    app = create_app()
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
