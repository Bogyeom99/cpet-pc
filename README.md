# NGC CPET PC

차세대스포츠과학지원센터 운동부하검사 피드백지 제작 프로그램의 로컬 PC 버전입니다.

기존 웹 배포 버전의 분석 기능과 결과지 기능을 유지하면서, 선수 정보와 측정 기록을 Supabase가 아닌 **로컬 SQLite 데이터베이스**에 저장합니다.

## 주요 특징

- 인터넷 연결 없이 사용 가능
- 브라우저에서 `http://localhost:8501`로 실행
- 선수 및 측정 정보는 `data/cpet.db`에 저장
- Speed / Power 지원
- 일반 Stage 시간 및 Rest 시간 설정
- Excel Data / Lactate 시트 입력
- HR, VO2, Lactate 그래프 생성
- LT1, LT2 자동 계산
- 결과지 안에서 문구 직접 편집
- PDF 및 Excel 결과 저장

## 처음 설치

Windows PC에서 저장소를 내려받은 뒤 `NGC_CPET_설치.bat`을 한 번 실행합니다.

설치 과정에서:

1. `.venv` 가상환경 생성
2. 필요한 Python 패키지 설치
3. 로컬 데이터 저장 폴더 생성

이 진행됩니다.

## 실행

설치 후 `NGC_CPET_실행.bat`을 더블클릭합니다.

프로그램이 실행되면 기본 브라우저에서 다음 주소가 열립니다.

```text
http://localhost:8501
```

실행 창을 닫거나 `Ctrl + C`를 누르면 로컬 서버가 종료됩니다.

## 데이터 저장 위치

로컬 데이터베이스:

```text
data/cpet.db
```

이 파일 하나에 선수 기본 정보와 측정 기록이 저장됩니다.

PC를 옮기거나 백업하려면 프로그램을 종료한 뒤 `data/cpet.db` 파일을 복사하면 됩니다.

## 개발 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## 웹 버전과의 차이

| 항목 | 웹 버전 | PC 버전 |
|---|---|---|
| 실행 | Streamlit Community Cloud | 로컬 Streamlit |
| 접속 | 인터넷 주소 | localhost |
| 선수 기록 저장 | Supabase | SQLite |
| 인터넷 연결 | 필요 | 설치 이후 불필요 |
| 분석 및 결과지 기능 | 지원 | 동일하게 지원 |

## 기술 구성

- Python
- Streamlit
- SQLite
- pandas
- NumPy
- Matplotlib
- openpyxl
- WeasyPrint
- GitHub Actions
