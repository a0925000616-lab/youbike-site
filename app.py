import math
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# ==========================================
# 台中市 YouBike 智慧查詢系統
# 功能：
# 1. 台中市站點查詢
# 2. 行政區篩選
# 3. 站名下拉選單
# 4. 最少可借車數篩選
# 5. 地圖站點顯示
# 6. 點地圖找最近 3 個站點
# 7. Google Maps 導航
# ==========================================

st.set_page_config(
    page_title="台中市 YouBike 智慧查詢系統",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 台中市 YouBike 智慧查詢系統")
st.caption("查詢站點、查看地圖，並點地圖找最近站點")

# YouBike 即時資料
DATA_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"


@st.cache_data(ttl=60)
def fetch_data():
    """抓取 YouBike 即時資料，快取 60 秒。"""
    res = requests.get(DATA_URL, timeout=15)
    res.raise_for_status()
    return res.json()


def haversine(lat1, lon1, lat2, lon2):
    """計算兩點距離（公尺）。"""
    r = 6371000
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return r * c


def build_dataframe(raw):
    """把原始 JSON 整理成 DataFrame。"""
    rows = []
    for item in raw:
        rows.append({
            "站名": item.get("sna", ""),
            "行政區": item.get("sarea", ""),
            "可借": item.get("available_rent_bikes", 0) or 0,
            "可還": item.get("available_return_bikes", 0) or 0,
            "總車位": item.get("total", 0) or 0,
            "緯度": item.get("latitude"),
            "經度": item.get("longitude"),
            "地址": item.get("ar", "")
        })
    return pd.DataFrame(rows)


# ===============================
# 側邊欄
# ===============================
st.sidebar.header("查詢條件")

if st.sidebar.button("🔄 重新更新資料"):
    fetch_data.clear()
    st.sidebar.success("資料已更新")

raw_data = fetch_data()
df = build_dataframe(raw_data)

# ===============================
# 只保留台中市資料
# ===============================
taichung_areas = [
    "中區", "東區", "南區", "西區", "北區",
    "西屯區", "南屯區", "北屯區",
    "豐原區", "大里區", "太平區", "清水區",
    "沙鹿區", "梧棲區", "大甲區", "東勢區",
    "烏日區", "神岡區", "大肚區", "大雅區",
    "后里區", "霧峰區", "潭子區", "龍井區",
    "外埔區", "和平區", "石岡區", "大安區",
    "新社區"
]

df = df[df["行政區"].isin(taichung_areas)].reset_index(drop=True)

# 行政區下拉選單
areas = ["全部"] + sorted([a for a in df["行政區"].dropna().unique().tolist() if a])
selected_area = st.sidebar.selectbox("行政區", areas)

# 先依行政區做一層篩選，讓站名清單更精準
temp_df = df.copy()
if selected_area != "全部":
    temp_df = temp_df[temp_df["行政區"] == selected_area]

# 站名下拉選單
station_list = sorted(temp_df["站名"].dropna().unique().tolist())
selected_station = st.sidebar.selectbox("選擇站名", ["全部"] + station_list)

# 最少可借車數
min_bikes = st.sidebar.slider("最少可借車數", 0, 40, 0)

# 是否只顯示可借 > 0
show_only_available = st.sidebar.checkbox("只顯示可借 > 0", value=False)

# ===============================
# 篩選資料
# ===============================
filtered = df.copy()

if selected_area != "全部":
    filtered = filtered[filtered["行政區"] == selected_area]

if selected_station != "全部":
    filtered = filtered[filtered["站名"] == selected_station]

filtered = filtered[filtered["可借"] >= min_bikes]

if show_only_available:
    filtered = filtered[filtered["可借"] > 0]

filtered = filtered.reset_index(drop=True)

# ===============================
# 統計資訊
# ===============================
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("站點數", len(filtered))
with c2:
    st.metric("可借總數", int(filtered["可借"].sum()) if not filtered.empty else 0)
with c3:
    st.metric("可還總數", int(filtered["可還"].sum()) if not filtered.empty else 0)

# ===============================
# 地圖中心（台中市中心）
# ===============================
map_center = [24.1477, 120.6736]

if not filtered.empty and filtered[["緯度", "經度"]].dropna().shape[0] > 0:
    map_center = [
        filtered["緯度"].dropna().mean(),
        filtered["經度"].dropna().mean()
    ]

m = folium.Map(location=map_center, zoom_start=13)

# ===============================
# 加入站點標記
# ===============================
for _, row in filtered.iterrows():
    lat = row["緯度"]
    lon = row["經度"]

    if pd.isna(lat) or pd.isna(lon):
        continue

    # 依可借車數決定標記顏色
    if row["可借"] >= 10:
        color = "green"
    elif row["可借"] >= 3:
        color = "orange"
    else:
        color = "red"

    popup_html = f"""
    <b>{row['站名']}</b><br>
    行政區：{row['行政區']}<br>
    可借：{row['可借']}<br>
    可還：{row['可還']}<br>
    地址：{row['地址']}
    """

    folium.Marker(
        [lat, lon],
        popup=popup_html,
        tooltip=row["站名"],
        icon=folium.Icon(color=color)
    ).add_to(m)

# ===============================
# 顯示主地圖
# ===============================
st.subheader("🗺️ 站點地圖")
map_data = st_folium(m, width=1000, height=600)

# ===============================
# 點地圖找最近站點
# ===============================
st.subheader("📍 點地圖找最近站點")
clicked = map_data.get("last_clicked") if map_data else None

if clicked:
    click_lat = clicked["lat"]
    click_lon = clicked["lng"]

    st.write(f"你點擊的位置：緯度 {click_lat:.6f} / 經度 {click_lon:.6f}")

    nearest_rows = []
    for _, row in filtered.iterrows():
        lat = row["緯度"]
        lon = row["經度"]

        if pd.isna(lat) or pd.isna(lon):
            continue

        dist = haversine(click_lat, click_lon, lat, lon)

        nearest_rows.append({
            "站名": row["站名"],
            "行政區": row["行政區"],
            "可借": row["可借"],
            "可還": row["可還"],
            "距離(公尺)": int(dist),
            "緯度": lat,
            "經度": lon,
            "地址": row["地址"]
        })

    nearest_df = pd.DataFrame(nearest_rows)

    if not nearest_df.empty and "距離(公尺)" in nearest_df.columns:
        nearest_df = nearest_df.sort_values(by="距離(公尺)").head(3).reset_index(drop=True)

        st.subheader("🏆 最近 3 個站點")
        st.dataframe(
            nearest_df[["站名", "行政區", "可借", "可還", "距離(公尺)", "地址"]],
            use_container_width=True
        )

        # 最近站點定位圖
        m2 = folium.Map(location=[click_lat, click_lon], zoom_start=16)

        folium.Marker(
            [click_lat, click_lon],
            popup="你的位置",
            tooltip="你的位置",
            icon=folium.Icon(color="blue", icon="star")
        ).add_to(m2)

        colors = ["red", "orange", "green"]

        for idx, row in nearest_df.iterrows():
            lat = row["緯度"]
            lon = row["經度"]
            name = row["站名"]
            dist = row["距離(公尺)"]

            popup_html = f"""
            <b>{name}</b><br>
            距離：{dist} 公尺<br>
            可借：{row['可借']}<br>
            可還：{row['可還']}
            """

            folium.Marker(
                [lat, lon],
                popup=popup_html,
                tooltip=f"第 {idx + 1} 近",
                icon=folium.Icon(color=colors[idx])
            ).add_to(m2)

            folium.PolyLine(
                [[click_lat, click_lon], [lat, lon]],
                color=colors[idx],
                weight=4
            ).add_to(m2)

        st.subheader("🧭 最近站點定位圖")
        st_folium(m2, width=1000, height=500)

        st.subheader("🌐 Google Maps 導航")
        for _, row in nearest_df.iterrows():
            nav_url = f"https://www.google.com/maps/dir/{click_lat},{click_lon}/{row['緯度']},{row['經度']}"
            st.markdown(f"- [{row['站名']}｜距離 {row['距離(公尺)']} 公尺]({nav_url})")
    else:
        st.warning("目前無法計算最近站點。")
else:
    st.info("請先在地圖上點一下。")

# ===============================
# 查詢結果表格
# ===============================
st.subheader("📋 查詢結果")
if filtered.empty:
    st.warning("目前沒有符合條件的站點。")
else:
    st.dataframe(
        filtered[["站名", "行政區", "可借", "可還", "總車位", "地址"]],
        use_container_width=True
    )
