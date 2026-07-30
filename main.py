import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="초·중학생 분포 지도", layout="wide")
st.title("🗺️ 전국 초·중학생 분포 지도")
st.caption("시군구별 전체 인구 대비 초등학생(만 7~12세), 중학생(만 13~15세) 비율")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    # '코드' 열은 앞자리 0이 사라지지 않게 글자로 읽습니다
    return pd.read_csv(POP_URL, dtype={"코드": str})

@st.cache_data(show_spinner="지도 경계를 불러오는 중입니다...")
def load_geojson():
    return requests.get(GEO_URL, timeout=30).json()

df = load_population()
geojson = load_geojson()

# 1. 가장 최신 연도만 사용
latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()

# 2. '계_'로 시작하는 나이 열 가져오기
total_cols = [c for c in df.columns if c.startswith("계_")]

def age_of(col):
    m = re.match(r"계_(\d+)세", col)
    return int(m.group(1)) if m else None

# 3. 초등학생(만 7~12세) 및 중학생(만 13~15세) 열 분리
elem_cols = [c for c in total_cols if age_of(c) is not None and 7 <= age_of(c) <= 12]
mid_cols = [c for c in total_cols if age_of(c) is not None and 13 <= age_of(c) <= 15]

# 4. 동 단위로 전체 인구 및 학생 수 합산
df["전체인구"] = df[total_cols].sum(axis=1)
df["초등학생인구"] = df[elem_cols].sum(axis=1)
df["중학생인구"] = df[mid_cols].sum(axis=1)

# 5. '코드' 앞 5자리 = 시군구 코드 → 시군구별 묶기 및 비율 계산
df["시군구코드"] = df["코드"].str[:5]
grouped = df.groupby("시군구코드")[["전체인구", "초등학생인구", "중학생인구"]].sum().reset_index()

grouped["초등학생비율"] = (grouped["초등학생인구"] / grouped["전체인구"] * 100).round(2)
grouped["중학생비율"] = (grouped["중학생인구"] / grouped["전체인구"] * 100).round(2)

# 경계 파일에서 코드 → 시군구·시도 이름 짝 만들기
names = pd.DataFrame([
    {
        "시군구코드": str(f["properties"]["코드"]),
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"],
    }
    for f in geojson["features"]
])
merged = grouped.merge(names, on="시군구코드", how="left")

# 6. 사용자 선택 UI (비교 기능)
view_option = st.radio("조회할 지도를 선택하세요", ["중학생 비율 (만 13~15세)", "초등학생 비율 (만 7~12세)"], horizontal=True)

if "중학생" in view_option:
    target_col = "중학생비율"
else:
    target_col = "초등학생비율"

# 7. qcut을 이용한 5단계 색 구간 설정
LABELS = ["매우 낮음", "낮음", "보통", "높음", "매우 높음"]

# 동일한 값이 많을 경우 오류 방지를 위해 duplicates='drop' 적용
merged["단계_숫자"], bins = pd.qcut(merged[target_col], q=5, labels=False, retbins=True, duplicates='drop')
merged["단계"] = merged["단계_숫자"].map(lambda x: LABELS[x] if x < len(LABELS) else LABELS[-1])

# 8. 단계구분도 그리기 (배경 지도 타일 없이 경계만)
fig = px.choropleth(
    merged,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="단계",
    category_orders={"단계": LABELS},
    color_discrete_sequence=px.colors.sequential.Blues,
    hover_name="시군구",
    hover_data={"시도": True, "시군구코드": False, target_col: True, "단계": False},
    title=f"시군구별 {view_option} (%)"
)

fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})

st.plotly_chart(fig, use_container_width=True)

# 9. 비율이 높은 곳과 낮은 곳 표 2개 출력
col1, col2 = st.columns(2)

with col1:
    st.subheader("비율 높은 곳 Top 10")
    st.dataframe(
        merged.nlargest(10, target_col)[["시도", "시군구", target_col]].reset_index(drop=True)
    )

with col2:
    st.subheader("비율 낮은 곳 Top 10")
    st.dataframe(
        merged.nsmallest(10, target_col)[["시도", "시군구", target_col]].reset_index(drop=True)
    )
