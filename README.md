# NGC CPET PC

차세대스포츠과학지원센터 운동부하검사 피드백지 제작 프로그램의 **완전 로컬 PC 버전**입니다.

이 버전은 Streamlit과 Supabase를 사용하지 않습니다. 화면은 Flask 기반의 로컬 웹 앱으로 제공하고, 선수 정보와 측정 기록은 SQLite 파일에 저장합니다.

## 보안 구조

프로그램 실행 중 선수 정보, Excel 원자료, 분석 결과, PDF와 Excel 결과는 외부 저장소로 전송하지 않습니다.

```text
브라우저
  ↓
http://127.0.0.1:8501
  ↓
Flask 로컬 서버
  ↓
Python 분석 모듈
  ↓
SQLite
data/cpet.db
```

서버는 `127.0.0.1`에만 연결되므로 같은 네트워크의 다른 PC에서도 직접 접속할 수 없습니다.

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
- 로컬 SQLite 백업

## 설치

Windows PC에서 저장소를 내려받은 뒤 처음 한 번만:

```text
NGC_CPET_설치.bat
```

을 실행합니다.

Python이 설치되어 있어야 하며 설치 과정에서 필요한 Python 패키지를 내려받습니다.

## 실행

설치 이후에는:

```text
NGC_CPET_실행.bat
```

을 더블클릭합니다.

브라우저가 자동으로 열리고 다음 주소에서 프로그램이 실행됩니다.

```text
http://127.0.0.1:8501
```

프로그램을 종료하려면 실행 창에서 `Ctrl + C`를 누르거나 창을 닫습니다.

## 데이터 저장

선수 및 측정 기록은 다음 파일에 저장됩니다.

```text
data/cpet.db
```

Git에는 실제 데이터베이스 파일이 올라가지 않도록 제외되어 있습니다.

## 백업

프로그램을 종료한 상태에서:

```text
NGC_CPET_백업.bat
```

을 실행하면 다음 형태로 복사됩니다.

```text
backup/cpet_YYYYMMDD_HHMMSS.db
```

## 개발 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## 폴더 구조

```text
cpet-pc/
├─ app.py
├─ services/
│  ├─ athlete_store.py
│  ├─ excel_parser.py
│  ├─ input_template.py
│  ├─ lt_analysis.py
│  ├─ graph_service.py
│  ├─ workflow.py
│  ├─ report_service.py
│  └─ excel_export.py
├─ templates/
│  └─ index.html
├─ static/
│  ├─ app.css
│  └─ app.js
├─ assets/
│  └─ center_logo.png
├─ data/
│  └─ cpet.db
├─ NGC_CPET_설치.bat
├─ NGC_CPET_실행.bat
├─ NGC_CPET_백업.bat
└─ requirements.txt
```

## 웹 배포 버전과의 차이

| 항목 | ngc-cpet | cpet-pc |
|---|---|---|
| UI | Streamlit | Flask + HTML/CSS/JavaScript |
| 실행 위치 | 웹 배포 | 로컬 PC |
| 데이터 저장 | Supabase | SQLite |
| 외부 저장소 | 사용 | 사용하지 않음 |
| 접속 주소 | 웹 주소 | 127.0.0.1 |
| 인터넷 연결 | 운영 시 필요 | 설치 후 운영 시 불필요 |

## PDF

PDF는 먼저 WeasyPrint로 생성합니다. Windows 환경에서 WeasyPrint 실행이 어려운 경우 PC에 설치된 Chrome 또는 Edge의 로컬 PDF 출력 기능을 자동으로 사용합니다.

## 자동 검사

GitHub Actions에서 Python 3.12와 3.14 기준으로 다음을 검사합니다.

- Flask 앱 시작
- SQLite 저장
- Excel Stage 처리
- Rest 시간 처리
- LT 계산
- 그래프 생성
- 결과지 생성
