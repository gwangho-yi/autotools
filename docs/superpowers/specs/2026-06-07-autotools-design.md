# autotools Monorepo Design

## Goal

현재 ticketure 레포를 `autotools` 모노레포로 재구성하고, `auto-clicker` 앱을 새로 추가한다.

## Architecture

uv workspace 기반 모노레포. `auto-capture`(기존 ticketure)와 `auto-clicker`가 독립 패키지로 공존한다. 두 앱은 TCP 소켓으로 통신하며, `auto-clicker`는 `auto-capture` 없이도 단독 동작한다.

**Tech Stack:** Python 3.14+, PySide6, uv workspace, pynput(클릭 실행)

---

## 1. 모노레포 구조

```
autotools/
├── pyproject.toml          # [tool.uv.workspace] members 정의만
├── auto-capture/           # 기존 ticketure 패키지 이름 변경
│   ├── pyproject.toml
│   ├── main.py
│   ├── core/
│   │   ├── alert.py        # auto-clicker 신호 전송 추가
│   │   └── monitor.py
│   ├── ui/
│   ├── assets/
│   └── scripts/
└── auto-clicker/           # 신규 패키지
    ├── pyproject.toml
    ├── main.py
    ├── core/
    │   ├── click_engine.py # 시퀀스 실행 엔진
    │   └── ipc_server.py   # TCP 서버 (localhost:54321)
    └── ui/
        ├── main_window.py  # 메인 UI
        └── point_picker.py # 화면 오버레이 포인트 지정
```

워크스페이스 루트 `pyproject.toml`:
```toml
[tool.uv.workspace]
members = ["auto-capture", "auto-clicker"]
```

---

## 2. auto-capture 변경사항

기존 ticketure에서 이름만 변경. 기능 변경은 `core/alert.py` 하나.

### core/alert.py 추가 로직

motion 감지 시 localhost:54321로 TCP 메시지 전송 (fire-and-forget):

```
{"event": "motion", "x": 850, "y": 420}
```

- 연결 실패(auto-clicker 미실행)는 조용히 무시
- 기존 알림음(`notify.wav`) 재생은 그대로 유지
- 전송은 별도 스레드에서 non-blocking으로 처리

---

## 3. auto-clicker

### 3-1. UI (main_window.py)

```
┌─────────────────────────────────────┐
│  auto-clicker                       │
│                                     │
│  [+ 포인트 추가]                      │
│                                     │
│  ┌───┬──────────┬──────┬───────┬──┐ │
│  │ # │ 위치     │딜레이 │ 종류  │  │ │
│  ├───┼──────────┼──────┼───────┼──┤ │
│  │ 1 │ (320,240)│ 0.5s │ 좌클릭 │✕│ │
│  │ 2 │ (800,400)│ 1.2s │ 더블  │✕│ │
│  └───┴──────────┴──────┴───────┴──┘ │
│                                     │
│  [▶ 시작]              [⬤ auto-capture 연결] │
└─────────────────────────────────────┘
```

- 포인트 추가: "포인트 추가" 버튼 클릭 → 화면 오버레이 → 마우스로 위치 클릭 → 포인트 등록
- 딜레이 입력: 시/분/초/ms 각각 입력 (숫자 스핀박스)
- 클릭 종류: 왼쪽 / 오른쪽 / 더블 (드롭다운)
- 포인트 드래그로 순서 변경 가능
- 시작 버튼: 1회 실행 후 대기 상태 복귀

### 3-2. 포인트 지정 (point_picker.py)

- "포인트 추가" 클릭 시 전체 화면 반투명 오버레이 표시
- 마우스 이동 시 십자선(crosshair) + 현재 좌표 표시
- 클릭하면 해당 좌표를 포인트로 등록하고 오버레이 닫힘
- ESC로 취소

### 3-3. 클릭 실행 엔진 (click_engine.py)

시퀀스 실행은 별도 QThread에서 처리.

**단독(standalone) 모드 — 시작 버튼 클릭 시:**
```
point[0]: delay → 커서 이동 → 클릭
point[1]: delay → 커서 이동 → 클릭
...
완료 → 대기 상태
```

**auto-capture 연동 모드 — 신호 수신 시:**
```
즉시: 현재 커서 위치 클릭 (포인트 설정 없음, 딜레이 없음)
point[0]: delay → 커서 이동 → 클릭
point[1]: delay → 커서 이동 → 클릭
...
완료 → 다음 신호 대기
```

실행 중 새 신호가 와도 현재 시퀀스를 완료 후 처리 (큐잉 없음, 드롭).

### 3-4. TCP 서버 (ipc_server.py)

- `QThread` 기반 TCP 서버, localhost:54321 listen
- "auto-capture 연결" 버튼 클릭 시 서버 시작
- 연결 상태: 대기중 / 연결됨 표시
- 수신 메시지: `{"event": "motion", "x": int, "y": int}` (JSON line)
- 수신 시 `motion_received` Signal emit → click_engine 트리거

---

## 4. 소켓 프로토콜

| 방향 | 내용 |
|------|------|
| auto-capture → auto-clicker | `{"event": "motion", "x": 850, "y": 420}\n` |

- 단방향 전송 (ACK 없음)
- 인코딩: UTF-8, 개행 구분
- 포트: 54321 (고정)
- auto-capture는 매 motion 이벤트마다 새 TCP 연결 생성 후 전송 후 닫음 (persistent connection 불필요)

---

## 5. 빌드 / 패키징

- 각 패키지 독립 빌드 스크립트 (`auto-capture/build.sh`, `auto-clicker/build.sh`)
- Windows: `auto-capture/build-windows.bat`, `auto-clicker/build-windows.bat`
- PyInstaller spec 각각 유지
- 공통 assets(아이콘, 사운드)는 각 패키지에 별도 보관 (공유 없음)

---

## 6. 마이그레이션 순서

1. GitHub 레포 이름 `ticketure → autotools` 변경
2. 루트에 `auto-capture/` 폴더 생성, 기존 파일 이동
3. 루트 `pyproject.toml` workspace 설정으로 교체
4. `auto-clicker/` 패키지 신규 생성
5. `auto-capture/core/alert.py`에 소켓 전송 추가
