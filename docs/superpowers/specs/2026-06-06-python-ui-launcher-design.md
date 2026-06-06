# ticketure Python UI 런처 디자인

**날짜:** 2026-06-06  
**상태:** 승인됨  
**대상 플랫폼:** macOS (우선), Windows (추후)

---

## 개요

ticketure는 화면 특정 영역의 픽셀 변화를 감지해 커서를 자동 이동시키는 앱이다.
현재 CLI로만 동작하지만, 비개발자도 사용할 수 있도록 PySide6 기반 GUI 런처를 추가한다.
향후 pyinstaller 등으로 패키징해 설치 프로그램으로 배포하는 것을 목표로 한다.

---

## 사용자 흐름

```
앱 실행
  └→ 런처 창 표시
       └→ "시작" 클릭
            └→ 런처 창 숨김
                 └→ 영역 선택 오버레이 표시
                      └→ 사용자가 드래그로 영역 지정
                           └→ 모니터링 시작 + 트레이 아이콘 활성화
                                └→ 우클릭 → "중지" 선택
                                     └→ 모니터링 종료 + 런처 창 복귀
```

---

## 파일 구조

```
ticketure/
├── main.py              # 진입점 — QApplication 생성 + Launcher 실행
├── ui/
│   ├── launcher.py      # 런처 창 위젯
│   ├── tray.py          # 시스템 트레이 아이콘 및 컨텍스트 메뉴
│   └── region_select.py # 기존 영역 선택 위젯 (변경 없음)
└── core/
    ├── monitor.py       # 모니터링 루프 (QThread)
    └── alert.py         # 플랫폼별 알림음 분기
```

---

## 컴포넌트 상세

### 1. `ui/launcher.py` — 런처 창

- **창 크기:** 320×400px, 화면 중앙 배치
- **스타일:** 다크 테마 (배경 `#1a1a2e`, 텍스트 흰색)
- **구성 요소 (위→아래):**
  1. SVG 아이콘 — Qt QPainter로 렌더링한 티켓 형태 선형 아이콘, 64px
  2. 앱 이름 "ticketure" — 흰색 24px bold
  3. 한 줄 설명 — "화면 변화를 감지하고 커서를 이동합니다" (회색 12px)
  4. "시작" 버튼 — 강조색 `#4ecca3`, 클릭 시 영역 선택 시작
- **버튼 상태:**
  - 기본: "시작" 활성화
  - 클릭 후: 버튼 비활성화 + "영역을 선택하세요..." 상태 텍스트 표시
  - 영역 선택 완료: 창 숨김, 트레이로 전환

### 2. `ui/tray.py` — 시스템 트레이

- **아이콘:** 런처와 동일 SVG 디자인을 16px 비트맵으로 렌더링
- **플랫폼 동작:**
  - macOS: 메뉴바 상단
  - Windows: 우측 하단 알림 영역
- **컨텍스트 메뉴 (우클릭):**
  ```
  ● 모니터링 중...   (비활성 상태 표시)
  ─────────────────
  창 열기
  중지
  ─────────────────
  종료
  ```
- "중지" 선택 시: 모니터 스레드 종료 신호 → 런처 창 다시 표시
- "종료" 선택 시: 앱 완전 종료

### 3. `core/monitor.py` — 모니터 스레드

- `QThread` 서브클래스
- 기존 `main.py`의 `while True` 루프 로직을 그대로 이식
- **시그널:**
  - `motion_detected = Signal(int, int)` — 변화 감지 시 (x, y 좌표)
  - `stopped = Signal()` — 스레드 종료 완료 시
- **중지 방법:** `QThread.requestInterruption()` → 루프 내 `self.isInterruptionRequested()` 체크 후 종료
- 상수(`INTERVAL`, `PIXEL_DIFF`, `MIN_CHANGED`)는 기존 값 유지

### 4. `core/alert.py` — 알림음

```python
import sys, os

def alert():
    if sys.platform == "darwin":
        os.system("afplay /System/Library/Sounds/Glass.aiff &")
    elif sys.platform == "win32":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
```

플랫폼 분기를 한 파일에 격리해 Windows 포팅 시 수정 범위를 최소화한다.

---

## main.py 변경 사항

기존의 직접 실행 방식에서 런처 기동 방식으로 변경:

```python
# 변경 전
def main():
    region = select_region()
    ...모니터링 루프...

# 변경 후
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 트레이만 남아있어도 종료 안 됨
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec())
```

---

## 의존성

추가 패키지 없음. 기존 `pyside6>=6.11.1`으로 모든 기능 구현 가능.

---

## 향후 패키징 고려 사항

- pyinstaller 또는 cx_Freeze로 단일 실행파일 생성 예정
- SVG 아이콘을 Qt 리소스 시스템(`QRC`)으로 번들링하면 패키징 시 경로 문제 없음
- `core/alert.py`의 Windows 분기는 지금 미리 작성해두어 포팅 공수를 줄임
