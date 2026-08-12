import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QStyle, QStyleOptionSlider, QWidget,
)

from autotools_shared.alert import alert


def _preview_async(volume: float) -> None:
    threading.Thread(target=alert, args=(volume,), daemon=True).start()


class _Slider(QSlider):
    """트랙의 아무 지점이나 클릭하면 단계별 이동 없이 그 위치로 바로 점프한다.

    일반 QSlider는 핸들이 아닌 트랙을 클릭하면 pageStep만큼만 이동하고,
    핸들을 직접 드래그할 때만 sliderReleased를 emit한다. 두 동작 모두
    이 위젯에서 기대하는 "클릭한 위치로 바로 이동 + 항상 미리듣기" 동작과
    맞지 않아 마우스 이벤트를 직접 처리한다.
    """

    released_by_user = Signal()

    def _value_at(self, x: int) -> int:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = self.style()
        groove = style.subControlRect(QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderGroove, self)
        handle = style.subControlRect(QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self)
        span = groove.width() - handle.width()
        pos = min(max(x - groove.x() - handle.width() // 2, 0), span)
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), pos, span)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._value_at(int(event.position().x())))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._value_at(int(event.position().x())))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.released_by_user.emit()


class VolumeControl(QWidget):
    """알림음 볼륨 슬라이더. 슬라이더를 놓으면 현재 볼륨으로 미리듣기를 재생한다."""

    volume_changed = Signal(int)

    def __init__(self, play=_preview_async, parent=None):
        super().__init__(parent)
        self._play = play

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("볼륨:")
        label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        label.setFixedWidth(36)
        layout.addWidget(label)

        self._slider = _Slider(Qt.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(100)
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #2a2a4e; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #4ecca3; border-radius: 2px; }
            QSlider::handle:horizontal {
                width: 12px; height: 12px; margin: -4px 0;
                background: #4ecca3; border-radius: 6px;
            }
        """)
        self._slider.valueChanged.connect(self._on_value_changed)
        self._slider.released_by_user.connect(self._on_slider_released)
        layout.addWidget(self._slider)

        self._pct_label = QLabel("100%")
        self._pct_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self._pct_label.setFixedWidth(36)
        layout.addWidget(self._pct_label)

    @property
    def value(self) -> int:
        return self._slider.value()

    @property
    def volume(self) -> float:
        return self._slider.value() / 100

    def _on_value_changed(self, value: int) -> None:
        self._pct_label.setText(f"{value}%")
        self.volume_changed.emit(value)

    def _on_slider_released(self) -> None:
        self._play(self.volume)
