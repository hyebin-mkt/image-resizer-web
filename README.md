
# Key Image Resizer (Web) — made by Chacha

하나의 이미지를 여러 사이즈로 자동 추출하는 **웹 앱(Streamlit)** 입니다.  
데스크톱 버전이 아닌 **웹 배포용** 코드만 포함합니다.

## 기능
- 프리셋 6종 (체크 선택) + 커스텀 사이즈(텍스트 입력)
- 출력 배율(기본 **2.0**), 포맷(JPG/JPEG/PNG), JPEG 품질
- 중앙 크롭(Fill) 방식으로 정확한 WxH 보장
- ZIP로 일괄 다운로드

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
> 브라우저가 자동으로 열립니다.

## Streamlit Cloud 배포 (추천)
1. 이 레포(또는 동일 파일)를 **GitHub 공개 저장소**에 업로드
2. https://streamlit.io/cloud → GitHub로 로그인 → **New app**
3. **Repository**: 본인/레포명, **Branch**: main, **App file**: `app.py`
4. **Deploy** → 완성된 URL 공유

## 파일 설명
- `app.py` — 메인 앱
- `requirements.txt` — 패키지 버전 고정
- `runtime.txt` — Python 3.11로 고정(Streamlit Cloud 호환)

## 변경 포인트
- 프리셋 수정: `PRESETS` 배열
- 기본 배율: `SCALE_OPTIONS`와 `index=SCALE_OPTIONS.index(2.0)`
- 메시지/텍스트: `app.py` 상단/하단 텍스트

## 주의
- 데스크톱(Tkinter) 코드는 포함하지 않습니다. (웹 배포 시 `tkinter` 사용 금지)
- 대형 이미지 변환 시 메모리/시간이 오래 걸릴 수 있습니다(호스팅 사양에 따라 다름).
