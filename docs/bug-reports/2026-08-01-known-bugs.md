# autotools 알려진 버그 리포트 (2026-08-01)

4-앱 재구조화 완료 시점 기준, 미해결로 남아 있는 버그 2건. 구조 이동(리팩터링)은
동작 보존이 목적이었으므로 아래 버그들은 재구조화 전부터 존재했고 그대로 이어졌다.

---

## 버그 #1 — 여러 감지점이 흩어져 있으면 엉뚱한(감지 안 된) 좌표를 클릭한다

### 심각도
높음 (기능의 정확성에 직접 영향)

### 증상
감시 영역 안에서 변화점/색일치 픽셀이 **여러 군데 흩어져** 나타나면, 커서가
그 점들 중 하나가 아니라 **점들 사이의 빈 공간(변화가 없는 곳)** 으로 이동한다.
사용자 관찰 예: 분홍색 변화점 5개가 갈색 원을 둘러싸듯 분포했을 때, 정작 감지되지
않은 가운데 갈색 지점의 좌표가 도출됨.

### 재현
1. "변경 감지"(motion-capture) 또는 "컬러 감지"(color-capture)로 넓은 영역을 감시.
2. 그 영역 안에서 서로 떨어진 여러 지점이 동시에 변하거나(또는 지정 색과 일치).
3. 도출된 클릭 좌표가 어느 감지점과도 일치하지 않고, 감지점들의 기하학적 중심으로 감.

### 원인 (핵심)
감지된 픽셀 전체의 좌표 **평균(무게중심, centroid)** 을 클릭 지점으로 계산한다.
흩어진 점들의 평균은 "점들 사이 가운데"가 되며, 그 지점은 실제로는 감지되지 않은 곳이다.
(시계판 12·3·6·9시에 점이 있을 때 평균 위치가 정중앙이 되는 것과 동일.)

- `apps/motion-capture/core/monitor.py` (변경 감지):
  ```python
  ys, xs = np.where(mask)          # 변화 감지된 모든 픽셀 좌표
  fx = xs.mean() / w_px            # ← x 좌표 평균
  fy = ys.mean() / h_px            # ← y 좌표 평균
  cx = self.region["left"] + fx * self.region["width"]
  cy = self.region["top"]  + fy * self.region["height"]
  ```
- `apps/color-capture/core/color_monitor.py` (컬러 감지): 동일 패턴(`xs.mean()/ys.mean()`).

두 파일 모두 감지 판정 임계값(`MIN_CHANGED=15` / `MIN_MATCHED=15`)만 넘으면 매칭 픽셀
집합 전체의 평균을 하나의 좌표로 축약한다. "한 덩어리"일 때는 잘 맞지만 "여러 덩어리"일 때
깨진다.

### 영향
감지점이 여러 개인 화면(여러 좌석/버튼/아이콘 등)에서 오클릭. 티켓팅처럼 여러 후보가
동시에 뜨는 상황에서 특히 문제.

### 해결 방향 (택1, 정책 결정 필요)
1. **가장 큰 연결 덩어리(연속된 픽셀 그룹) 하나의 중심을 클릭** — 흩어진 점 중 가장 크고
   뚜렷한 하나를 자동 선택. 대부분의 경우 가장 자연스러움. (예: `scipy.ndimage.label`
   또는 간단한 flood-fill로 연결 성분 분리 후 최대 성분의 centroid.)
2. **변화/일치가 가장 강한 단일 픽셀을 클릭** — diff 최대 지점. 구현 단순.
3. **규칙 기반 단일 선택** — 예: 가장 왼쪽 위 덩어리.

> motion-capture와 color-capture 둘 다 같은 방식을 쓰므로, 방향을 정하면 두 곳을 동일하게
> 고치는 것을 권장한다. (감지 코어는 앱별로 분리돼 있으니 각 앱에서 수정.)

---

## 버그 #2 — GPU/3D 가속이 없는 환경에서 "색 지정"·"영역 선택" 오버레이가 앱을 죽인다

### 심각도
높음 (해당 환경에서 기능 사용 불가)

### 증상
그래픽 카드가 없거나 3D 가속 드라이버가 없는 Windows 환경(사무실 PC, UTM/QEMU VM 등)에서
"색 지정" 또는 "변경 감지 시작(영역 선택)" 버튼을 누르면, **에러 메시지 없이 프로세스가
즉시 종료**된다. 커서가 잠깐 십자 모양이 됐다가 풀리며 앱이 꺼짐.

### 재현
1. 3D 가속이 없는 환경에서 실행 (확인된 케이스: UTM의 virtio-gpu "DOD" 드라이버,
   그래픽카드 없는 사무실 PC).
2. 색 지정/영역 선택 오버레이를 띄우는 동작 실행.
3. 파이썬 예외조차 없이 앱 전체가 종료.

### 원인 (분석)
오버레이 창들이 **반투명 레이어드 창**(`WA_TranslucentBackground` + 프레임리스 + 항상 위)
으로 만들어진다:
- `shared/src/autotools_shared/overlay/color_picker.py`
- `shared/src/autotools_shared/overlay/point_picker.py`
- `shared/src/autotools_shared/overlay/region_select.py`
  ```python
  self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
  self.setAttribute(Qt.WA_TranslucentBackground)
  ```
이런 창을 화면에 실제로 합성(compositing)하려면 Windows DWM의 GPU 가속 경로가 필요한데,
GPU/드라이버가 없어 소프트웨어 폴백으로 동작하는 환경에서는 이 경로가 깨지며 Qt 내부(C++)
레벨에서 프로세스가 죽는다. 파이썬 예외 훅으로는 잡히지 않는다.

**진단 근거 (이 프로젝트에서 직접 확인함):** VM에서 `region_select`의
`WA_TranslucentBackground` 한 줄만 임시로 껐더니 크래시가 사라지고 영역 선택이 정상
동작했다(반투명은 회색 불투명으로 대체됨). "반투명 켬 → 100% 크래시 / 끔 → 정상"이 정확히
대조돼, 반투명 레이어드 창이 원인임이 사실상 확정됨. 단, 최종 재현 환경은 GPU 없는 PC/VM에
한정되며 정상 GPU가 있는 일반 PC에서는 재현되지 않는다.

### 현재 상태 — 부분 완화 적용됨(미검증)
재구조화 중 공통 부트스트랩 `shared/src/autotools_shared/bootstrap.py`의 `create_app()`에
소프트웨어 렌더링 강제를 넣었고, 4개 앱이 모두 이걸 통해 QApplication을 만든다:
```python
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
app = QApplication(...)
app.setStyle("Fusion")
```
`AA_UseSoftwareOpenGL`은 Qt에게 GPU 대신 CPU 렌더링을 강제한다. 이것이 위 크래시를
막아줄 가능성이 있으나, **실제로 크래시가 나던 그 환경(GPU 없는 PC/VM)에서 아직 재검증하지
못했다.** 확정하려면 그 환경에서 재빌드 후 색 지정/영역 선택을 다시 시도해야 한다.

### 추가 해결책 (완화가 불충분할 경우)
`AA_UseSoftwareOpenGL`로도 여전히 죽는다면, 오버레이 방식을 근본적으로 바꾼다:
- **스크린샷을 미리 캡처해 오버레이 배경으로 그리기.** 오버레이를 띄우기 전에 화면을 한 번
  `mss`로 캡처해 그 이미지를 배경으로 그리면, OS 레벨 반투명 합성이 필요 없어져
  `WA_TranslucentBackground` 없이 **완전 불투명 창**으로 만들 수 있다. 사용자에겐 실제 화면이
  비쳐 보이는 것과 시각적으로 동일하고(정지 스냅샷), 색 샘플링도 그 이미지에서 직접 읽으면
  되어 더 빠르고 안전하다.

### 참고 — 진단 인프라(이미 존재)
- `apps/*/main.py`의 크래시 로거: 잡히지 않은 예외를 홈 디렉터리 로그 파일
  (`~/<app>-crash.log`)에 기록. (단, 이 크래시는 파이썬 레벨을 벗어나 로그가 안 남을 수 있음.)
- (구 `auto-capture`에 있던 콘솔 디버그 빌드는 재구조화 과정에서 제거됨 — 필요 시
  새 앱에 다시 추가 가능.)

---

## 요약

| # | 버그 | 심각도 | 상태 | 위치 |
|---|------|--------|------|------|
| 1 | 여러 감지점 흩어지면 centroid 평균 → 오좌표 | 높음 | 미수정 | `apps/motion-capture/core/monitor.py`, `apps/color-capture/core/color_monitor.py` |
| 2 | GPU 없는 환경 반투명 오버레이 크래시 | 높음 | 완화 적용(미검증) | `shared/.../overlay/*.py`, 완화: `shared/.../bootstrap.py` |

둘 다 이번 4-앱 재구조화 범위 밖으로 남겨둔 항목이며, 별도 작업으로 진행 가능하다.
