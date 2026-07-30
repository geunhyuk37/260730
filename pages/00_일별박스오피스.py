import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 조회")

# 비밀 금고에서 인증키 꺼내기 (코드에는 키를 적지 않는다)
KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 한국 시간 기준 어제 날짜 구하기
yesterday = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)

# 사이드바 또는 상단에 달력(날짜 선택 위젯) 배치
selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)

# 선택한 날짜를 KOBIS API 형식(YYYYMMDD)으로 변환
target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")

url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

# KOBIS는 키가 틀려도 상태코드 200을 준다. 대신 faultInfo 상자가 온다.
if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("선택한 날짜에 자료가 없습니다. 다른 날짜를 선택해 보세요.")
    st.stop()

df = pd.DataFrame(box_list)

# 글자로 온 숫자들을 진짜 숫자로 바꾸기
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# 1위 영화 지표 카드 세 장 (왕관 이모지 추가)
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("어제 1위" if selected_date == yesterday else "해당일 1위", f"👑 {top['movieNm']}")
c2.metric("관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객", f"{top['audiAcc']:,}명")

# 표를 한국어 열 이름으로 정리
table = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
table = table.sort_values("순위").reset_index(drop=True)

# 표 안의 1위 영화 이름에도 왕관 이모지 추가
table.loc[table["순위"] == 1, "영화명"] = "👑 " + table.loc[table["순위"] == 1, "영화명"]

st.subheader("📋 박스오피스 TOP 10")
st.dataframe(table)

st.subheader("📈 관객수 상위 5편")
top5 = table.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])
