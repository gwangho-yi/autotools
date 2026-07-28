import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, Qt


def create_app(argv=None) -> QApplication:
    """모든 앱 공통 QApplication 초기화. GPU 없는 환경 대응 소프트웨어 렌더링 포함.

    AA_UseSoftwareOpenGL은 QApplication 생성 전에 설정해야 유효하다.
    """
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setStyle("Fusion")
    return app
