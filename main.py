import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="초·중학생 12년 증감 및 추이", layout="wide")
st.title("🗺️ 전국 초·중학생 12년 증감 및 추이")
st.caption("2015년 대비 2026년 시군구별 전체 인구 대비 학생 비율 증감 및 연도별 인구수 변화")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    return pd.read_csv(POP_URL, dtype={"코드": str})

@st.cache_data(show_spinner="지도 경계를 불러오는 중입니다...")
def load_geojson():
    return requests.get(GEO_URL, timeout=30).json()

df = load_population()
geojson = load_geojson()

# 1. '계_'로 시작하는 나이 열 가져오기
total_cols = [c for c in df.columns if c.startswith("계_")]

def age_of(col):
    m = re.match(r"계_(\d+)세", col)
    return int(m.group(1)) if m else None

# 2. 초등학생(만 7~12세) 및 중학생(만 13~15세) 열 분리
elem_cols = [c for c in total_cols if age_of(c) is not None and 7 <= age_of(c) <= 12]
mid_cols = [c for c in total_cols if age_of(c) is not None and 13 <= age_of(c) <= 15]

# 3. 동 단위로 전체 인구 및 학생 수 합산
df["전체인구"] = df[total_cols].sum(axis=1)
df["초등학생인구"] = df[elem_cols].sum(axis=1)
df["중학생인구"] = df[mid_cols].sum(axis=1)

# 4. '코드' 앞 5자리 = 시군구 코드 → 연도별, 시군구별 묶기 및 비율 계산 (100에서 10으로 수정)
df["시군구코드"] = df["코드"].str[:5]
grouped = df.groupby(["연도", "시군구코드"])[["전체인구", "초등학생인구", "중학생인구"]].sum().reset_index()

grouped["초등학생비율"] = (grouped["초등학생인구"] / grouped["전체인구"] * 0.1).round(2)
grouped["중학생비율"] = (grouped["중학생인구"] / grouped["전체인구"] * 0.1).round(2)

# 경계 파일에서 코드 → 시군구·시도 이름 짝 만들기
names = pd.DataFrame([
    {
        "시군구코드": str(f["properties"]["코드"]),
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"]
    }
    for f in geojson["features"]
])
merged_all = grouped.merge(names, on="시군구코드", how="inner")

# 5. 12년간 증감 계산
min_year = merged_all["연도"].min()
max_year = merged_all["연도"].max()

df_min = merged_all[merged_all["연도"] == min_year].set_index("시군구코드")
df_max = merged_all[merged_all["연도"] == max_year].set_index("시군구코드")

diff_df = names.copy().set_index("시군구코드")
diff_df["초등학생_증감"] = (df_max["초등학생비율"] - df_min["초등학생비율"]).round(2)
diff_df["중학생_증감"] = (df_max["중학생비율"] - df_min["중학생비율"]).round(2)
diff_df = diff_df.reset_index().dropna()

st.subheader("1. 시군구별 12년간 비율 증감 지도")
view_option_map = st.radio("지도에서 조회할 대상을 선택하세요", ["중학생", "초등학생"], horizontal=True, key="map_radio")
target_diff = f"{view_option_map}_증감"

# 6. 단계구분도 그리기 (range_color로 -15 ~ 15 고정)
fig_map = px.choropleth(
    diff_df,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color=target_diff,
    color_continuous_scale="RdBu",
    color_continuous_midpoint=0,
    range_color=[-15, 15], 
    hover_name="시군구",
    hover_data={"시도": True, "시군구코드": False, target_diff: True},
    title=f"12년간({min_year}~{max_year}) {view_option_map} 비율 증감"
)

# 윤곽선 추가 (0인 지역 확인 가능하도록 설정)
fig_map.update_traces(marker_line_width=0.5, marker_line_color="darkgray")
fig_map.update_geos(fitbounds="locations", visible=False)
fig_map.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})

st.plotly_chart(fig_map, use_container_width=True)

st.divider()

# 7. 지역별 학생 인구수 추이 그래프 (2단계 선택)
st.subheader(f"📍 지역별 인구수 추이 ({min_year}~{max_year})")

col1, col2, col3 = st.columns(3)

with col1:
    view_option_line = st.radio("추이 그래프 대상 선택", ["중학생", "초등학생"], horizontal=True, key="line_radio")

sido_list = sorted(merged_all["시도"].unique())
default_sido_idx = sido_list.index("충청남도") if "충청남도" in sido_list else 0

with col2:
    selected_sido = st.selectbox("시/도 (광역시/도)를 선택하세요", sido_list, index=default_sido_idx)

sigungu_list = sorted(merged_all[merged_all["시도"] == selected_sido]["시군구"].unique())
default_sigungu_idx = 0
for i, s in enumerate(sigungu_list):
    if "천안시" in s or "아산시" in s:
        default_sigungu_idx = i
        break

with col3:
    selected_sigungu = st.selectbox("시/군/구 (읍/면)를 선택하세요", sigungu_list, index=default_sigungu_idx)

# 선택한 지역의 12년 데이터 필터링 (인구수 기준)
target_pop = f"{view_option_line}인구"
trend_df = merged_all[(merged_all["시도"] == selected_sido) & (merged_all["시군구"] == selected_sigungu)].sort_values("연도")

fig_line = px.line(
    trend_df,
    x="연도",
    y=target_pop,
    markers=True,
    title=f"{selected_sido} {selected_sigungu} {view_option_line} 인구수 추이",
    labels={"연도": "연도", target_pop: f"{view_option_line} 인구 (명)"}
)
fig_line.update_layout(xaxis=dict(tickmode='linear', dtick=1))

st.plotly_chart(fig_line, use_container_width=True)
