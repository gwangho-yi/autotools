import mss
import mss.tools

with mss.mss() as sct:
    monitor = sct.monitors[1]   # [0]은 전체 가상화면, [1]이 첫 번째 실제 모니터
    img = sct.grab(monitor)
    mss.tools.to_png(img.rgb, img.size, output="capture_test.png")
    print("저장 완료:", monitor)