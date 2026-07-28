# autotools 4-앱 분리 + 공유 패키지 추출 설계

**목표:** 현재 2개 앱(auto-capture, auto-clicker)을 4개의 독립 실행 앱으로 분리하고, 중복/공통 로직을 설치 가능한 로컬 공유 패키지 `autotools_shared`로 추출한다.

**아키텍처:** uv 워크스페이스 모노레포. 루트 아래 `shared/`(공유 패키지)와 `apps/`(4개 앱)을 두고, 각 앱은 `autotools_shared`를 경로 의존성으로 참조한다. 앱들은 2쌍의 IPC 소켓 통신으로 연결된다(감지 앱 = client, 클릭 앱 = server).

**기술 스택:** Python ≥3.14, PySide6, mss, numpy, pynput, uv(워크스페이스/빌드), PyInstaller(앱별 exe).

## Global Constraints

- 구현은 오케스트레이터가 직접 하지 않고 cmux 워커(surface:2, surface:3)에 `.omc/tasks/*.md` 스펙으로 위임한다.
- 각 마이그레이션 단계는 독립적으로 pytest 통과를 게이트로 삼는다(회귀 없음 확인 후 다음 단계).
- Python 버전 floor: `>=3.14` (기존 pyproject 유지).
- 앱 exe는 앱마다 1개씩, 총 4개. 각 앱은 독립 실행/빌드 가능해야 한다.
- 플랫폼: 개발=macOS, 배포=일반 Windows PC. macOS에서 pynput은 문자키 Listener 크래시 이슈가 있어 전역훅은 함수키/조합키만, ESC 리스너는 Windows 전용 분기 유지.

---

## 1. 최종 디렉터리 구조

```
autotools/
├─ pyproject.toml                 # uv 워크스페이스 루트 (members = shared + apps/*)
├─ uv.lock
├─ shared/
│  ├─ pyproject.toml              # 패키지명 autotools_shared
│  └─ src/autotools_shared/
│     ├─ __init__.py
│     ├─ overlay/
│     │  ├─ __init__.py
│     │  ├─ base.py               # 공통 오버레이 베이스(프레임리스+topmost+Tool, ESC 필터, Win pynput ESC 릴레이)
│     │  ├─ region_select.py      # 영역 드래그 선택
│     │  ├─ point_picker.py       # 단일 좌표 픽
│     │  └─ color_picker.py       # 색 픽 + 돋보기(loupe)
│     ├─ ipc/
│     │  ├─ __init__.py
│     │  ├─ client.py             # IpcClient (host/port 주입)
│     │  └─ server.py             # IpcServer (port 주입)
│     ├─ hotkey.py                # pynput 전역훅 릴레이 (HotkeyRelay)
│     ├─ alert.py                 # alert(volume) + AlertRepeater (클리커 상위집합 버전)
│     ├─ tray.py                  # 트레이 아이콘
│     ├─ models.py                # ClickPoint
│     ├─ click_engine.py          # ClickEngine (순서/캡쳐/색 시작 진입점)
│     ├─ continuous_click_engine.py
│     ├─ bootstrap.py             # QApplication 초기화(Fusion + 소프트웨어 렌더링 폴백)
│     ├─ spinbox_style.py         # 스핀박스 스타일 + 화살표 에셋 경로 헬퍼
│     ├─ clickpoint_list.py       # 클릭 포인트 목록 위젯(ClickPointRow + 리스트 컨테이너)
│     └─ assets/                  # 공용 사운드(notify.wav), 스핀박스 화살표 png
│  └─ tests/                      # 공유 로직 테스트
└─ apps/
   ├─ motion-capture/    (변경감지, IPC client, 포트 54321)
   ├─ motion-clicker/    (순서클릭, IPC server, 포트 54321)
   ├─ color-capture/     (컬러감지, IPC client, 포트 54322)
   └─ color-clicker/     (컬러클릭, IPC server, 포트 54322)
```

각 앱 디렉터리 구조(공통 형태):
```
apps/<app>/
├─ pyproject.toml        # autotools_shared 를 [tool.uv.sources] 경로 의존성으로 참조
├─ main.py               # 진입점: bootstrap → 윈도우 생성 → exec
├─ ui/                   # 이 앱 전용 위젯(런처/메인윈도우/탭)
├─ assets/               # 이 앱 전용 아이콘(icon.ico / icon.icns)
├─ scripts/make_icon.py  # 앱별 아이콘 생성(앱마다 다름)
├─ tests/                # 이 앱 전용 테스트
├─ <app>.spec            # macOS 빌드 spec
├─ <app>-windows-x64.spec# Windows 빌드 spec
└─ build-windows.bat / build.sh
```

## 2. 공유 패키지 `autotools_shared` 구성 요소

| 모듈 | 출처(현재) | 통합 방침 |
|---|---|---|
| `overlay/base.py` | region_select/point_picker/color_picker에 흩어진 공통 창 셋업 | 프레임리스+topmost+Tool 플래그, ESC 이벤트 필터, Windows 전용 pynput ESC 릴레이를 베이스로 추출 |
| `overlay/region_select.py` | auto-capture | 베이스 상속, 드래그 영역 선택 로직만 유지 |
| `overlay/point_picker.py` | auto-clicker | 베이스 상속, 단일 좌표 픽 |
| `overlay/color_picker.py` | auto-capture | 베이스 상속, 돋보기(loupe) + 색 샘플링 |
| `ipc/client.py` | auto-capture ipc_client | `HOST`/`PORT`를 생성자 인자로 주입(하드코딩 제거) |
| `ipc/server.py` | auto-clicker ipc_server | `PORT`를 생성자 인자로 주입 |
| `hotkey.py` | 양쪽 `_F6Relay`/`_EscRelay` 복붙 | 단일 `HotkeyRelay`(pynput 스레드 → Qt QueuedConnection 브릿지) |
| `alert.py` | auto-clicker 버전(상위집합) | `alert(volume)` + `AlertRepeater` 채택. auto-capture의 단순 버전은 폐기 |
| `tray.py` | auto-capture | 그대로 이동 |
| `models.py` | auto-clicker | `ClickPoint` 이동 |
| `click_engine.py` / `continuous_click_engine.py` | auto-clicker | 이동. 두 클리커 앱이 공유 |
| `clickpoint_list.py` | auto-clicker main_window의 포인트 목록 + `click_point_row.py` | 재사용 가능한 위젯으로 추출(두 클리커 앱이 각자 사용) |
| `spinbox_style.py` | auto-clicker main_window `_spinbox_style()` | frozen/소스 경로 모두 대응하는 에셋 로더 포함 |
| `bootstrap.py` | 신규 | `create_app()`: `QApplication(sys.argv)` + Fusion 스타일 + GPU 없는 환경 소프트웨어 렌더링 폴백(예: `AA_UseSoftwareOpenGL` 또는 `QT_OPENGL=software`) 공통 적용 |
| `assets/` | 양쪽 `notify.wav`(동일), 스핀박스 화살표 png | 공용화. `make_sound.py`는 공용(동일했음) |

**아이콘 예외:** `make_icon.py`/`icon.ico`/`icon.icns`는 앱마다 시각적 정체성이 달라 각 앱에 남긴다.

## 3. 4개 앱 명세

### motion-capture (변경감지)
- **역할:** 사용자가 드래그로 지정한 화면 영역(들)을 주기적으로 캡쳐, 픽셀 변화 감지 시 좌표를 IPC로 전송.
- **IPC:** client, 포트 **54321**.
- **전용 UI:** 기존 auto-capture launcher의 "변경 감지" 페이지 + 시작/일시정지/재시작/중지 스택.
- **공유 사용:** `overlay.region_select`, `ipc.client`, `hotkey`, `tray`, `bootstrap`.
- **감지 코어:** 기존 `core/monitor.py`(MonitorThread) — 이 앱 전용으로 유지(공유 아님).

### color-capture (컬러감지)
- **역할:** 영역 내에서 지정 RGB(±허용오차) 픽셀을 감지, 감지 시 좌표를 IPC로 전송. 감지 후 자동 일시정지.
- **IPC:** client, 포트 **54322**.
- **전용 UI:** 기존 `ColorCaptureTab`(RGB 스핀박스 3개[화살표 없음] + 색 지정 버튼 + 허용오차 + 시작/일시정지/중지 스택).
- **공유 사용:** `overlay.color_picker`, `ipc.client`, `hotkey`, `tray`, `bootstrap`.
- **감지 코어:** 기존 `core/color_monitor.py`(ColorMonitorThread) — 전용 유지.

### motion-clicker (순서클릭)
- **역할:** 클릭 포인트 목록을 편집하고, 단독 실행(시작 지연 포함) 또는 motion-capture 신호 수신 시 포인트 시퀀스를 순서대로 클릭.
- **IPC:** server, 포트 **54321**.
- **전용 UI:** 기존 auto-clicker의 "순서 클릭" 페이지(시작 지연 h/m/s + 시작/중지) + 공유 포인트 목록 위젯 + 알림음(mute/볼륨) 영역.
- **공유 사용:** `clickpoint_list`, `click_engine`, `models`, `ipc.server`, `overlay.point_picker`, `alert`, `hotkey`, `bootstrap`, `spinbox_style`.

### color-clicker (컬러클릭)
- **역할:** 클릭 포인트 목록 편집 + "연속 클릭 지점"을 사람처럼 불규칙 간격(min~max ms)으로 연속 클릭하다가, color-capture 감지 신호를 받으면 연속클릭 정지 → 감지 좌표 클릭 → 포인트 시퀀스 실행.
- **IPC:** server, 포트 **54322**.
- **전용 UI:** 기존 `ColorClickerTab`(연속 클릭 지점 + min/max ms + 상호 제약 검증) + 공유 포인트 목록 위젯 + 알림음 영역.
- **공유 사용:** `clickpoint_list`, `click_engine`, `continuous_click_engine`, `models`, `ipc.server`, `overlay.point_picker`, `alert`, `hotkey`, `bootstrap`, `spinbox_style`.

## 4. 데이터 흐름 (IPC)

두 쌍이 서로 다른 포트에서 독립적으로 동작:

```
motion-capture ──(motion x,y)──▶ 54321 ──▶ motion-clicker : 포인트 시퀀스 1회 실행
color-capture  ──(color x,y)──▶ 54322 ──▶ color-clicker  : 연속클릭 정지→감지좌표 클릭→시퀀스
```

- 감지 앱(client)은 앱 내 "연결" 토글로 해당 포트에 접속. 클릭 앱(server)은 시작 시 자기 포트에서 listen.
- 메시지 포맷은 기존 JSON 유지(`{"type": "motion"/"color_match", "x":..., "y":...}` 형태). 포트만 앱별로 분리.
- 포트는 공유 `ipc` 모듈에 하드코딩하지 않고 각 앱이 생성 시 주입(예: `IpcClient(port=54322)`).

## 5. 마이그레이션 단계 (각 단계 = 워커 작업 단위, pytest 게이트)

1. **워크스페이스 골격**: 루트 워크스페이스 pyproject + 빈 `shared/` 패키지(`autotools_shared` import 가능) 구성. 기존 2앱은 그대로 둔 채 워크스페이스에 편입만.
2. **공통 코드 이동 + 기존 2앱 전환**: alert/tray/models/click_engine/ipc/hotkey/overlay/spinbox_style/clickpoint_list/bootstrap/assets를 shared로 이동, 기존 auto-capture·auto-clicker가 shared를 import하도록 수정. 이 단계 끝에서 **기존 2앱이 동일하게 동작**(회귀 없음)해야 한다. IPC 포트/오버레이 통합/소프트웨어 렌더링 부트스트랩도 여기서 shared로 흡수.
3. **앱 분할**: `apps/motion-capture`, `apps/color-capture`(← auto-capture 분리), `apps/motion-clicker`, `apps/color-clicker`(← auto-clicker 분리) 생성. 각 앱은 자기 전용 UI/감지코어/아이콘만 보유.
4. **포트 분리 + 빌드/CI**: color 쌍을 54322로 이동. 앱별 `.spec` 4개 + `build-windows.bat`/`build.sh` + GitHub Actions 워크플로(4개 앱 빌드/릴리즈)로 확장. 구 `auto-capture`/`auto-clicker` 디렉터리 제거.

각 단계는 surface:2(clicker 계열)/surface:3(capture 계열) 워커에 나눠 발주 가능하며, 단계 2~4는 앞 단계 완료가 선행 조건이다.

## 6. 테스트 전략

- **공유 로직**: `shared/tests/`로 이동/통합(색 감지, 클릭 엔진, 모델, IPC, 오버레이 등 기존 테스트 중 공유 대상). 워크스페이스 루트에서 `uv run pytest`로 전체 실행 가능.
- **앱 전용 로직**: 각 앱 `tests/`(감지 코어, 앱별 탭 위젯).
- **게이트**: 각 마이그레이션 단계 커밋 전 관련 pytest 전부 통과 + 각 앱 `python -c "import main"` 스모크.
- **런타임 검증**: 오케스트레이터가 macOS에서 각 앱 실행/스크린샷으로 확인. Windows 전용(소프트웨어 렌더링, pynput ESC, 4-앱 IPC 짝)은 사용자 재빌드 후 확인.

## 7. 미해결 이슈와의 관계

이 재구조화는 **구조 이동에 집중**하고 기존 동작을 보존한다. 아래 알려진 버그는 별도 작업으로 다룬다(단, 관련 코드가 shared로 이동하므로 이후 수정은 shared 한 곳에서 이뤄짐):
- GPU 없는 환경 색 지정 크래시 → 단계 2의 `bootstrap.py` 소프트웨어 렌더링 폴백이 완화 후보(별도 검증).
- 다중 변화점 centroid 평균 → 엉뚱한 좌표 도출(변경감지/컬러감지 공통) → 별도 작업.
