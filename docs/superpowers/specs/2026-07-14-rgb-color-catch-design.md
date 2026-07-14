# RGB Color Catch Catch — 컬러 감지 모드 설계

## Goal

`docs/new-version.md`에서 제기된 문제: 기존 auto-capture의 픽셀-변화 감지는 화면이 주기적으로 새로고침되는 환경(예: 전체 리렌더링되는 페이지)에서 오작동한다. 이를 해결하기 위해 "지정한 RGB 값이 감시 영역에 나타나는지"를 감지하는 새로운 모드("컬러캡쳐" / "컬러클리커")를 기존 모드와 나란히 추가한다. 기존 픽셀-diff 플로우는 완전히 그대로 유지하고, 신규 모드는 탭으로 분리한다.

## Architecture

- **UI 레벨**: `auto-capture`, `auto-clicker` 양쪽 모두 최상단에 `QTabWidget`을 도입한다. 탭1 = 기존 화면(무변경), 탭2 = 신규 컬러 모드 화면. 두 탭은 상호 배타적으로 동작하며 동시 실행을 허용하지 않는다.
- **IPC 레벨**: 기존 소켓(`127.0.0.1:54321`)과 연결 절차는 그대로 재사용한다. 메시지 타입만 확장한다 — 기존 `"motion"` 이벤트는 완전히 무변경, 신규 `"color_match"` 이벤트(좌표 포함)를 추가한다. 하위호환 확장이며 프로토콜 교체가 아니다.
- **감지 로직 레벨**: 픽셀-diff(`MonitorThread`)와 RGB-매칭(신규 `ColorMonitorThread`)은 알고리즘이 근본적으로 다르므로 별도 클래스로 분리한다. 단, mss 기반 화면 캡처·영역 처리 패턴은 동일하게 따른다.
- **클릭 실행 레벨**: 기존 `ClickEngine`의 "포인트 순서대로 순회하며 클릭"하는 핵심 루프(`_points` 순회)는 그대로 재사용한다. 새 진입점(`start_from_color`)만 추가한다. 완전히 새로운 동작인 연속 클릭(`ContinuousClickEngine`)만 별개 클래스로 신설한다 — 재사용할 기존 로직이 없기 때문.

**Tech Stack:** 기존과 동일 — Python, PySide6, mss(캡처), pynput(클릭 실행), TCP 소켓 IPC.

---

## 1. 확정된 요구사항 (브레인스토밍 결과)

문서(`docs/new-version.md`)의 모호했던 부분들을 다음과 같이 확정했다:

| 항목 | 결정 |
|---|---|
| 플로우 4번(클릭 포인트 순서 지정)과 7번(감지 시 수행할 클릭 순서)의 관계 | **동일한 하나의 목록.** 컬러클리커도 기본 탭의 `ClickPoint` 목록을 그대로 재사용한다. |
| RGB 값 지정 방법 | **화면 픽셀 클릭으로 샘플링.** 수동 hex/숫자 입력 없음. |
| RGB 매칭 허용오차 | **허용오차 둠.** 채널별 최대 차이가 임계값 이내면 매칭으로 판단, UI에서 조정 가능. |
| 감지 후 클릭 위치 | **감지된 실제 좌표로 이동 후 클릭.** 기존 motion 이벤트(커서 위치 클릭, 좌표 무시)와 다른 동작. |
| 연속 클릭 시 간격 불규칙화 알고리즘 | **가우시안(정규분포) 지터.** 범위의 중간값을 평균, 양끝을 표준편차 기준으로 샘플링(범위 밖은 clip). |
| 모드 전환 UI | **QTabWidget 도입.** 두 앱 모두 현재 탭 개념이 전혀 없었음(auto-capture는 320×440 고정창, auto-clicker는 단일 리스트 화면) — 신규 도입. |
| 연속 클릭 영역의 의미 | **단일 지점.** 사각형 영역 내 랜덤 위치 클릭이 아니라, 고정된 하나의 좌표를 반복 클릭. |

## 2. 컴포넌트

### auto-capture — 신규 파일

- **`core/color_monitor.py` → `ColorMonitorThread(QThread)`**: `MonitorThread`와 동일한 mss 폴링 구조(0.5s 간격, 감시 영역 기반)를 따르되, 프레임 간 diff 대신 목표 RGB와의 채널별 최대 차이(`max(|Δr|,|Δg|,|Δb|) <= tolerance`)로 매칭 픽셀을 탐색한다. 노이즈 방지를 위해 기존 `MIN_CHANGED`/`ALERT_COOLDOWN` 패턴을 그대로 차용 — 매칭 픽셀 수가 최소 임계값 이상일 때만, 그리고 마지막 감지 후 쿨다운이 지났을 때만 감지로 판단한다. 매칭 시 `color_detected(x, y)` 시그널 발신(매칭 마스크의 중심 좌표 — 기존 `motion_detected` 계산 방식과 동일한 스타일).
- **`ui/color_picker.py` → `pick_pixel_color()`**: `point_picker.py`의 풀스크린 오버레이 패턴을 재사용하되, 클릭 시 해당 좌표의 실제 화면 RGB를 mss로 샘플링해 `(x, y, (r, g, b))`를 반환한다. 마우스 이동 시마다 **돋보기(loupe) 패널**을 커서 오른쪽에 실시간 렌더링한다 — 커서 주변 15×15px 영역을 mss로 캡처해 8배 확대(nearest-neighbor, 결과 120×120px)하고, 중앙(= 실제 선택될 픽셀)은 강조 테두리로 표시, 하단에 현재 RGB 값을 텍스트로 함께 표시한다. 커서가 화면 우측 경계에 가까우면(패널 폭만큼 여유가 없으면) 패널을 커서 왼쪽으로 flip한다.
- **`ui/color_capture_tab.py` → `ColorCaptureTab` 위젯**: RGB 샘플 버튼 + 색상 스와치 미리보기, 허용오차 스핀박스, 감시영역 지정 버튼(기존 `region_select.select_region()` 재사용), 시작/정지 버튼, 상태 라벨.

### auto-capture — 기존 파일 확장

- **`core/ipc_client.py`**: `send_color_match(x, y)` 메서드 추가. 기존 `send_motion`과 동일한 패턴이며 이벤트 타입만 `"color_match"`.
- **`ui/launcher.py`**: `QTabWidget`으로 기존 콘텐츠를 탭1에 이식, 탭2에 `ColorCaptureTab` 추가. 고정창 크기(320×440)를 탭바 + 신규 컨트롤을 수용하도록 조정.

### auto-clicker — 신규 파일

- **`core/continuous_click_engine.py` → `ContinuousClickEngine(QThread)`**: 고정 좌표를 가우시안 지터 간격(`min_ms`~`max_ms` 범위, 밖으로 벗어나면 clip)으로 반복 클릭. `stop()` 호출 시 즉시 중단.
- **`ui/color_clicker_tab.py` → `ColorClickerTab` 위젯**: 연속클릭 지점 지정(`point_picker.pick_point()` 재사용), ms 범위 스핀박스 2개(min/max), 시작/정지 버튼, 상태 라벨. 기본 탭의 `ClickPoint` 목록을 참조해 감지 후 시퀀스에 사용한다.

### auto-clicker — 기존 파일 확장

- **`core/click_engine.py`**: 포인트 순회 로직을 `_run_points_sequence()`로 추출해 `start_standalone`/`start_from_capture`/신규 `start_from_color(x, y, click_type)` 세 진입점이 모두 공유한다. `start_from_color`는 지정 좌표로 마우스 이동 후 클릭하고, 이어서 `_run_points_sequence()`를 호출한다.
- **`core/ipc_server.py`**: `msg.get("event") == "color_match"` 분기를 추가해 신규 시그널 `color_match_received(x, y)`를 발신한다. 기존 `motion` 분기는 무변경.
- **`ui/main_window.py`**: `QTabWidget`으로 기존 콘텐츠를 탭1에 이식, 탭2에 `ColorClickerTab` 추가. `color_match_received` 수신 시 `ContinuousClickEngine.stop()` → `ClickEngine.start_from_color(x, y)` 순서로 연결.

## 3. 데이터 흐름

1. auto-capture 컬러 탭: RGB 픽셀 선택(`pick_pixel_color`, 커서 이동 중 돋보기 패널로 확대 미리보기) → 스와치 표시 / 감시영역 지정(`region_select` 재사용).
2. auto-clicker 컬러 탭: 연속클릭 지점 지정(`point_picker` 재사용) / ms 범위 지정.
3. auto-clicker 기본 탭: 기존 순서 클릭 포인트 목록 확인·편집(변경 없음, 재사용 대상).
4. 양쪽 "시작" → auto-clicker: `ContinuousClickEngine`이 지정 좌표를 가우시안 지터 간격으로 연속 클릭 시작. auto-capture: `ColorMonitorThread`가 지정 영역 내 목표 RGB(허용오차 내)를 감시 시작.
5. 매칭 감지 → auto-capture가 `{"event": "color_match", "x": x, "y": y}`를 소켓으로 전송.
6. auto-clicker: `color_match_received(x, y)` 수신 → `ContinuousClickEngine.stop()` → `ClickEngine.start_from_color(x, y)` 호출 → 해당 좌표로 이동 후 클릭 → 이어서 기존 포인트 순서대로 클릭(`_run_points_sequence`).
7. 시퀀스 종료 → 대기 상태로 복귀(기존과 동일).

## 4. 에러 처리

- `ColorMonitorThread`: 화면 grab 실패(해상도 변경 등) 시 기존 `MonitorThread`와 동일하게 예외 발생 시 스레드 종료.
- 동시 실행 방지: 컬러 탭 활성 중엔 기본 탭의 시작 버튼을 비활성화하고(역방향도 동일), `ContinuousClickEngine`과 `ClickEngine`이 동시에 `isRunning()`이면 시작 요청을 무시한다 — 기존 `_capture_blocked` 패턴을 그대로 적용.
- IPC 연결 끊김 시 컬러 모드도 기존 `client_disconnected` 흐름을 그대로 타 자동 정지 및 상태 라벨 갱신(신규 분기 불필요).
- 허용오차/ms 범위 등 사용자 입력값은 스핀박스 range로 UI 레벨에서 제한(기존 스타일과 동일), 별도 방어적 예외처리는 두지 않는다.
- 돋보기 패널의 실시간 mss 캡처가 화면 경계 근처(멀티 모니터 경계 등)에서 실패할 경우, 해당 프레임은 조용히 건너뛰고 다음 `mouseMoveEvent`에서 재시도한다(전체 오버레이를 중단하지 않음).

## 5. 테스트

- `tests/test_color_monitor.py`(신규, `test_monitor.py` 패턴 참고): 허용오차 경계값(정확히 tolerance, tolerance+1) 매칭 여부 검증.
- `tests/test_click_engine.py`(확장): `start_from_color` 호출 시 좌표 이동 여부(mock Controller)를 검증.
- `tests/test_ipc_server.py`(확장): `color_match` 이벤트 파싱 테스트.
- `tests/test_continuous_click_engine.py`(신규): N회 클릭 간격을 샘플링해 `[min_ms, max_ms]` 범위 내에 있는지 통계적으로 검증.

## 6. 범위 밖 (Out of Scope)

- 사각형 영역 내 랜덤 위치 클릭(연속 클릭은 단일 고정 좌표로 한정).
- RGB 수동 hex/숫자 입력 UI.
- 다중 RGB 타겟 동시 감시(한 번에 하나의 목표 RGB만 지원).
