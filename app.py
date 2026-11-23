
from pathlib import Path
import re

import pandas as pd
import streamlit as st


# ==========================================
# 1. 페이지 기본 설정
# ==========================================

st.set_page_config(
    page_title="부산대 맛집 지도",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ 부산대 맛집 지도")
st.caption("담당: 이름(학과)")  # 본인의 이름과 학과로 수정


# ==========================================
# 2. 데이터 파일 불러오기
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "restaurants.csv"


@st.cache_data
def load_data(path_string):

    path = Path(path_string)

    if not path.exists():
        raise FileNotFoundError(
            f"데이터 파일을 찾을 수 없습니다.\n{path}"
        )

    # CSV 인코딩 자동 대응
    data = None

    for encoding in ["utf-8-sig", "cp949", "utf-8"]:
        try:
            data = pd.read_csv(path, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    if data is None:
        raise ValueError("CSV 파일의 인코딩을 확인해 주세요.")

    # 열 이름의 공백 및 BOM 제거
    data.columns = [
        str(column).strip().replace("\ufeff", "")
        for column in data.columns
    ]

    # 한글과 영문 열 이름 모두 지원
    column_aliases = {
        "name": ["name", "가게명", "식당명", "업체명", "상호명"],
        "menu": ["menu", "메뉴", "음식종류", "음식 종류", "업종"],
        "price_label": [
            "price_label", "price", "가격대", "가격", "메뉴 가격"
        ],
        "rating": [
            "rating", "고객 평점", "고객평점", "평점", "별점"
        ],
        "lat": ["lat", "latitude", "위도"],
        "lon": ["lon", "lng", "longitude", "경도"],
        "address": ["address", "주소"]
    }

    rename_columns = {}

    for standard_name, possible_names in column_aliases.items():

        for possible_name in possible_names:

            if possible_name in data.columns:
                rename_columns[possible_name] = standard_name
                break

    data = data.rename(columns=rename_columns)

    # 필수 데이터 확인
    required_columns = [
        "name",
        "menu",
        "price_label",
        "rating"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        raise ValueError(
            f"필요한 열이 없습니다: {missing_columns}\n"
            f"현재 CSV 열 이름: {data.columns.tolist()}\n\n"
            "가게명, 메뉴, 가격대, 고객 평점 열을 확인해 주세요."
        )

    # 주소와 좌표가 없더라도 앱이 중단되지 않도록 처리
    for column in ["lat", "lon"]:
        if column not in data.columns:
            data[column] = pd.NA

    if "address" not in data.columns:
        data["address"] = ""

    # 데이터 형식 정리
    for column in ["name", "menu", "price_label", "address"]:
        data[column] = (
            data[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    for column in ["rating", "lat", "lon"]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    # 빈 식당 행 제거
    data = data[data["name"] != ""].copy()

    return data


# 데이터 불러오기
try:

    df = load_data(str(DATA_PATH))

except Exception as error:

    st.error("맛집 데이터를 불러오지 못했습니다.")
    st.code(str(error))

    st.info(
        "프로젝트 폴더 안에 "
        "data/restaurants.csv 파일이 있는지 확인해 주세요."
    )

    st.stop()


# ==========================================
# 3. 검색 및 필터 기능
# ==========================================

st.divider()
st.subheader("🔎 원하는 맛집 찾기")

col1, col2, col3 = st.columns([1.2, 1, 1.4])


# 메뉴 선택
with col1:

    menu_options = ["전체"] + sorted(
        value
        for value in df["menu"].unique()
        if value.strip()
    )

    selected_menu = st.selectbox(
        "먹고 싶은 메뉴를 선택하세요",
        menu_options
    )


# 평점 선택
with col2:

    min_rating = st.slider(
        "최소 고객 평점",
        min_value=0.0,
        max_value=5.0,
        value=0.0,
        step=0.1
    )


# 식당 검색
with col3:

    keyword = st.text_input(
        "식당 이름 검색",
        placeholder="예: 돈까스, 포포포"
    )


# ==========================================
# 4. 데이터 필터링
# ==========================================

filtered = df.copy()


# 메뉴 필터
if selected_menu != "전체":

    filtered = filtered[
        filtered["menu"].str.contains(
            re.escape(selected_menu),
            case=False,
            na=False
        )
    ]


# 평점 필터
filtered = filtered[
    filtered["rating"].fillna(-1) >= min_rating
]


# 이름 검색
if keyword.strip():

    filtered = filtered[
        filtered["name"].str.contains(
            re.escape(keyword.strip()),
            case=False,
            na=False
        )
    ]


# ==========================================
# 5. 검색 결과 요약
# ==========================================

st.divider()
st.subheader("📊 검색 결과")

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "검색된 맛집",
        f"{len(filtered)}곳"
    )

with col2:

    average_rating = filtered["rating"].mean()

    if pd.notna(average_rating):

        st.metric(
            "평균 고객 평점",
            f"{average_rating:.2f} / 5.00"
        )

    else:

        st.metric(
            "평균 고객 평점",
            "정보 없음"
        )


# ==========================================
# 6. 맛집 지도
# ==========================================

st.divider()
st.subheader("📍 맛집 위치")

map_data = filtered.dropna(
    subset=["lat", "lon"]
).copy()

# 유효한 위도와 경도만 사용
map_data = map_data[
    map_data["lat"].between(-90, 90)
    & map_data["lon"].between(-180, 180)
]

if not map_data.empty:

    st.map(
        map_data[["lat", "lon"]]
    )

    st.caption(
        f"현재 지도에 표시된 맛집: {len(map_data)}곳"
    )

else:

    st.warning(
        "현재 등록된 위도·경도 정보가 없어 "
        "지도에 식당 위치를 표시할 수 없습니다."
    )

    st.write(
        "CSV 파일에 lat(위도), lon(경도) 정보를 추가하면 "
        "실제 위치가 지도에 표시됩니다."
    )


# ==========================================
# 7. 맛집 정보 표
# ==========================================

st.divider()
st.subheader("🍴 맛집 정보")

result_table = filtered[
    ["name", "menu", "price_label", "rating"]
].rename(
    columns={
        "name": "가게명",
        "menu": "메뉴",
        "price_label": "가격대",
        "rating": "고객 평점"
    }
).copy()


# 평점 표시 형식
result_table["고객 평점"] = result_table[
    "고객 평점"
].apply(
    lambda x: f"{x:.2f}" if pd.notna(x) else "정보 없음"
)


if result_table.empty:

    st.info(
        "검색 조건에 맞는 맛집이 없습니다. "
        "필터를 변경해 보세요."
    )

else:

    st.dataframe(
        result_table,
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# 8. 개별 식당 상세 정보
# ==========================================

if not filtered.empty:

    st.divider()
    st.subheader("🔍 식당 상세 정보")

    restaurant_list = (
        filtered["name"]
        .drop_duplicates()
        .tolist()
    )

    selected_restaurant = st.selectbox(
        "자세히 보고 싶은 식당을 선택하세요",
        restaurant_list
    )

    detail = filtered[
        filtered["name"] == selected_restaurant
    ].iloc[0]

    col1, col2 = st.columns(2)

    with col1:

        st.write(f"**가게명:** {detail['name']}")
        st.write(
            f"**메뉴:** {detail['menu'] or '정보 없음'}"
        )
        st.write(
            f"**가격대:** {detail['price_label'] or '정보 없음'}"
        )

    with col2:

        if pd.notna(detail["rating"]):

            st.write(
                f"**고객 평점:** {detail['rating']:.2f} / 5.00"
            )

        else:

            st.write("**고객 평점:** 정보 없음")

        st.write(
            f"**주소:** {detail['address'] or '주소 미등록'}"
        )


# ==========================================
# 9. 데이터 안내
# ==========================================

with st.expander("📌 데이터 및 지도 안내"):

    st.write(
        f"데이터 파일 위치: {DATA_PATH}"
    )

    st.write(
        f"전체 맛집 데이터: {len(df)}곳"
    )

    st.write(
        "지도는 CSV 파일에 저장된 위도(lat)와 "
        "경도(lon)를 사용합니다."
    )

    st.write(
        "좌표가 없는 식당은 목록에는 표시되지만 "
        "지도에는 표시되지 않습니다."
    )
