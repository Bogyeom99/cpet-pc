# NGC CPET PC

차세대스포츠과학지원센터 운동부하검사 피드백지 제작 프로그램의 **완전 로컬 데스크톱 버전**입니다.

이 버전은 Streamlit, Flask, localhost 웹 서버, Supabase를 사용하지 않습니다. 화면은 PySide6 데스크톱 창으로 실행되고, 선수 정보와 측정 기록은 SQLite 파일에 저장됩니다.

## 보안 구조

프로그램 실행 중 선수 정보, Excel 원자료, 분석 결과, PDF와 Excel 결과는 외부 저장소로 전송하지 않습니다.

```text
NGC CPET PC 데스크톱 창
        ↓
Python 분석 모듈
        ↓
SQLite
data/cpet.db
```

브라우저를 열지 않고, localhost 포트도 사용하지 않습니다.

결과지 미리보기는 프로그램 내부의 Qt HTML 엔진에서만 표시되며, HTTP, HTTPS, FTP, WebSocket 요청은 코드에서 차단합니다.

## 주요 기능

- 선수 등록 및 기존 선수 불러오기
- 선수별 측정 기록 저장 및 수정
- Speed / Power 검사 지원
- 일반 운동 Stage 시간 설정
- Rest 시간 설정
- Excel Data / Lactate 시트 처리
- HR 및 VO2 분석
- 혈중 젖산염 그래프
- LT1 및 LT2 자동 계산
- HR, VO2, Lactate 통합 그래프
- A4 2페이지 결과지 생성
- 결과지 안에서 문구 직접 편집
- 글자색, 굵게, 기울임, 밑줄 적용
- PDF 및 Excel 결과 저장
- 로컬 SQLite 저장

## 처음 설치

Python 3.12 이상이 설치된 PC에서 명령 프롬프트 또는 VSCode 터미널을 열고 저장소 폴더로 이동합니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

설치 과정에서 PySide6, pandas, NumPy, openpyxl, Matplotlib 등이 해당 PC에 설치됩니다.

기관 PC가 인터넷 차단 환경이라면 인터넷이 가능한 PC에서 필요한 패키지를 준비한 뒤 오프라인 설치 방식으로 옮겨야 합니다.

## 실행

```powershell
.\.venv\Scripts\python.exe main.py
```

브라우저가 아니라 NGC CPET 전용 데스크톱 창이 열립니다.

## 데이터 저장

선수 및 측정 기록은 다음 파일에 저장됩니다.

```text
data/cpet.db
```

Git에는 실제 데이터베이스 파일이 올라가지 않도록 제외되어 있습니다.

백업할 때는 프로그램을 종료한 뒤 `data/cpet.db` 파일을 다른 안전한 위치에 복사하면 됩니다.

## 폴더 구조

```text
cpet-pc/
├─ main.py
├─ ui/
│  ├─ __init__.py
│  └─ main_window.py
├─ services/
│  ├─ athlete_store.py
│  ├─ excel_parser.py
│  ├─ input_template.py
│  ├─ lt_analysis.py
│  ├─ graph_service.py
│  ├─ workflow.py
│  ├─ report_service.py
│  └─ excel_export.py
├─ assets/
│  └─ center_logo.png
├─ data/
│  └─ cpet.db
└─ requirements.txt
```

## 웹 배포 버전과의 차이

| 항목 | ngc-cpet | cpet-pc |
|---|---|---|
| 화면 | Streamlit 웹 화면 | PySide6 데스크톱 창 |
| 실행 위치 | 웹 배포 | 로컬 PC |
| 데이터 저장 | Supabase | SQLite |
| 외부 저장소 | 사용 | 사용하지 않음 |
| 브라우저 | 사용 | 사용하지 않음 |
| localhost 서버 | 사용 가능 | 사용하지 않음 |
| 네트워크 포트 | 필요 | 필요 없음 |
| 운영 중 인터넷 연결 | 필요 | 불필요 |

## PDF

PDF는 PySide6의 내부 HTML 출력 기능으로 저장합니다. Chrome이나 Edge를 별도로 실행하지 않습니다.

## 자동 검사

GitHub Actions에서 Python 3.12와 3.14 기준으로 다음을 검사합니다.

- PySide6 데스크톱 모듈 import
- SQLite 저장
- Excel Stage 처리
- Rest 시간 처리
- LT 계산
- 그래프 생성
- 결과지 HTML 생성
