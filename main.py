import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import zoneinfo
import altair as alt

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

# 2. 한국 표준시(KST) 기준 '어제' 날짜 계산
# Streamlit Cloud 서버는 UTC 기준이므로 명시적으로 Asia/Seoul 타임존을 적용합니다.
kst = zoneinfo.ZoneInfo("Asia/Seoul")
now_kst = datetime.now(kst)
yesterday_kst = now_kst - timedelta(days=1)
target_dt = yesterday_kst.strftime("%Y%m%d")
display_dt = yesterday_kst.strftime("%Y년 %m월 %d일")

st.title("🎬 어제 박스오피스 순위")
st.caption(f"기준 일자: {display_dt} (KST)")

# 3. Streamlit Secrets에서 API 인증키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 API 인증키를 찾을 수 없습니다.")
    st.info("Streamlit Cloud 설정(Settings -> Secrets)에 `KOBIS_KEY = '발급받은_키'` 형태로 등록했는지 확인해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 4. KOBIS 일별 박스오피스 API 호출
api_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt
}

try:
    response = requests.get(api_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error("🚨 KOBIS API 서버에 연결하지 못했습니다.")
    st.info("인터넷 연결 상태나 KOBIS 서버 점검 여부를 확인해 주세요.")
    st.stop()
except ValueError:
    st.error("🚨 응답 데이터를 JSON 형식으로 변환할 수 없습니다.")
    st.stop()

# 5. KOBIS 응답 예외 처리
# 인증키 오류 시 HTTP 200과 함께 'faultInfo' 객체가 반환됩니다.
if "faultInfo" in data:
    fault_message = data["faultInfo"].get("message", "인증키 또는 파라미터가 유효하지 않습니다.")
    st.error(f"🚨 KOBIS API 오류: {fault_message}")
    st.info("Secrets에 입력한 KOBIS_KEY가 정확한지, 일일 트래픽 한도를 초과하지 않았는지 확인해 주세요.")
    st.stop()

# 영화 데이터 목록 추출
box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning(f"⚠️ {display_dt}의 박스오피스 데이터가 비어 있습니다.")
    st.info("아직 해당 날짜의 관객 집계가 완료되지 않았거나 공휴일 등으로 지연될 수 있습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

# 6. 데이터프레임 변환 및 전처리 (문자열 -> 숫자형 변환)
df = pd.DataFrame(movie_list)

numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 7. 1위 영화 하이라이트 (메트릭 카드 3장)
top_movie = df.iloc[0]

st.subheader(f"🥇 어제의 1위: {top_movie['movieNm']}")
col1, col2, col3 = st.columns(3)

col1.metric(
    label="일일 관객수",
    value=f"{top_movie['audiCnt']:,} 명"
)
col2.metric(
    label="누적 관객수",
    value=f"{top_movie['audiAcc']:,} 명"
)
col3.metric(
    label="확보 스크린수",
    value=f"{top_movie['scrnCnt']:,} 개"
)

st.divider()

# 8. 관객수 상위 5편 막대그래프 (문법 오류 수정 완료)
st.subheader("📊 관객수 TOP 5")
top_5_df = df.head(5).copy()

chart = (
    alt.Chart(top_5_df)
    .mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5)
    .encode(
        x=alt.X("audiCnt:Q", title="일일 관객수(명)", axis=alt.Axis(format=",")),
        y=alt.Y("movieNm:N", title="영화명", sort="-x"),
        tooltip=[
            alt.Tooltip("movieNm:N", title="영화명"),
            alt.Tooltip("audiCnt:Q", title="일일 관객수", format=","),
            alt.Tooltip("audiAcc:Q", title="누적 관객수", format=",")
        ]
    )
    .properties(height=260)
)
st.altair_chart(chart, use_container_width=True)

st.divider()

# 9. 전체 박스오피스 순위표 표시
st.subheader("📋 전체 박스오피스 순위표")

display_columns = {
    "rank": "순위",
    "movieNm": "영화명",
    "openDt": "개봉일",
    "audiCnt": "당일 관객수",
    "audiAcc": "누적 관객수",
    "scrnCnt": "스크린수"
}
table_df = df[list(display_columns.keys())].rename(columns=display_columns)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(format="%d위"),
        "당일 관객수": st.column_config.NumberColumn(format="%d명"),
        "누적 관객수": st.column_config.NumberColumn(format="%d명"),
        "스크린수": st.column_config.NumberColumn(format="%d개"),
    }
)
