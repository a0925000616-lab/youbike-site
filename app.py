import math
import json
import requests
import urllib3
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

urllib3.disable_warnings()

# ==========================================
# 台中市 YouBike 智慧查詢系統｜高級 UI 版
# ==========================================

st.set_page_config(
    page_title="台中市 YouBike 智慧查詢系統",
    page_icon="🚲",
    layout="wide"
)

# -----------------------------
# 自訂樣式
# -----------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1.5rem;
    max-width: 1400px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1f2430 0%, #181c25 100%);
}

[data-testid="stSidebar"] * {
    color: #f3f4f6;
}

.ui-card {
    background: linear-gradient(180deg, #111827 0%, #0b1220 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}

.metric-card {
    background: linear-gradient(180deg, #111827 0%, #0b1220 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
    min-height: 110px;
}

.metric-label {
    font-size: 0.95rem;
    color: #9ca3af;
    margin-bottom: 8px;
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f9fafb;
}

.section-title {
    font-size: 1.5rem;
    font-weight: 800;
    margin: 0.2rem 0 0.8rem 0;
}

.small-note {
    color: #9ca3af;
    font-size: 0.95rem;
}

.result-card {
    background: linear-gradient(180deg, #111827 0%, #0b1220 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 14px 16px;
    margin-bottom: 12px;
}

.result-title {
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 8px;
}

hr {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.08);
    margin: 1rem 0 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 標題
# -----------------------------
st.markdown("""
<div class="ui-card">
    <div style="font-size:2.2rem; font-weight:800;">🚲 台中市 YouBike 智慧查詢系統</div>
    <div class="small-note">查詢站點、查看地圖，並點地圖找最近站點</div>
</div>
""", unsafe_allow_html=True)

DATA_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=ed5ef436-fb62-40ba-9ad7-a165504cd953"


@st.cache_data(ttl=600)
def fetch_data():
    try:
        res = requests.get(DATA_URL, timeout=20, verify=False)
        res.raise_for_status()
        data = res.json()
        ret_val = data.get("retVal", "[]")
        if isinstance(ret_val, str):
            return json.loads(ret_val)
        return ret_val
    except Exception as e:
        st.error(f"資料抓取失敗：{e}")
        return []


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return r * c


def build_dataframe(raw):
    rows = []
    for item in raw:
        rows.append({
            "站名": str(item.get("sna", "")).replace("YouBike2.0_", ""),
            "行政區": item.get("sarea", ""),
            "可借": int(item.get("sbi", 0) or 0),
            "可還": int(item.get("bemp", 0) or 0),
            "總車位": int(item.get("tot", 0) or 0),
            "緯度": float(item.get("lat", 0) or 0),
            "經度": float(item.get("lng", 0) or 0),
            "地址": item.get("ar", ""),
            "啟用": int(item.get("act", 0) or 0)
        })
    return pd.DataFrame(rows)


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.markdown("## 查詢條件")

if st.sidebar.button("🔄 重新更新資料", use_container_width=True):
    fetch_data.clear()
    st.sidebar.success("資料已更新")

raw_data = fetch_data()

if not raw_data:
    st.warning("目前無法取得台中市 YouBike 資料，請稍後再試。")
    st.stop()

df = build_dataframe(raw_data)
df = df[df["啟用"] == 1].reset_index(drop=True)

areas = ["全部"] + sorted([a for a in df["行政區"].dropna().unique().tolist() if a])
selected_area = st.sidebar.selectbox("行政區", areas)

temp_df = df.copy()
if selected_area != "全部":
    temp_df = temp_df[temp_df["行政區"] == selected_area]

station_list = sorted(temp_df["站名"].dropna().unique().tolist())
selected_station = st.sidebar.selectbox("選擇站名", ["全部"] + station_list)

min_bikes = st.sidebar.slider("最少可借車數", 0, 80, 0)
show_only_available = st.sidebar.checkbox("只顯示可借 > 0", value=False)

# -----------------------------
# Filter
# -----------------------------
filtered = df.copy()

if selected_area != "全部":
    filtered = filtered[filtered["行政區"] == selected_area]

if selected_station != "全部":
    filtered = filtered[filtered["站名"] == selected_station]

filtered = filtered[filtered["可借"] >= min_bikes]

if show_only_available:
    filtered = filtered[filtered["可借"] > 0]

filtered = filtered.reset_index(drop=True)

# -----------------------------
# Metrics cards
# -----------------------------
mc1, mc2, mc3 = st.columns(3)

with mc1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">站點數</div>
        <div class="metric-value">{len(filtered)}</div>
    </div>
    """, unsafe_allow_html=True)

with mc2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">可借總數</div>
        <div class="metric-value">{int(filtered["可借"].sum()) if not filtered.empty else 0}</div>
    </div>
    """, unsafe_allow_html=True)

with mc3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">可還總數</div>
        <div class="metric-value">{int(filtered["可還"].sum()) if not filtered.empty else 0}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# -----------------------------
# Main map
# -----------------------------
map_center = [24.1477, 120.6736]
if not filtered.empty and filtered[["緯度", "經度"]].dropna().shape[0] > 0:
    map_center = [
        filtered["緯度"].dropna().mean(),
        filtered["經度"].dropna().mean()
    ]

m = folium.Map(location=map_center, zoom_start=13)

for _, row in filtered.iterrows():
    lat = row["緯度"]
    lon = row["經度"]

    if pd.isna(lat) or pd.isna(lon) or (lat == 0 and lon == 0):
        continue

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
    總車位：{row['總車位']}<br>
    地址：{row['地址']}
    """

    folium.Marker(
        [lat, lon],
        popup=popup_html,
        tooltip=row["站名"],
        icon=folium.Icon(color=color)
    ).add_to(m)

left, right = st.columns([2.2, 1])

with left:
    st.markdown('<div class="section-title">🗺️ 站點地圖</div>', unsafe_allow_html=True)
    map_data = st_folium(m, width=None, height=500)

with right:
    st.markdown('<div class="section-title">📍 最近站點</div>', unsafe_allow_html=True)

    clicked = map_data.get("last_clicked") if map_data else None

    if clicked:
        click_lat = clicked["lat"]
        click_lon = clicked["lng"]

        st.markdown(f"""
        <div class="result-card">
            <div class="result-title">你點擊的位置</div>
            緯度：{click_lat:.6f}<br>
            經度：{click_lon:.6f}
        </div>
        """, unsafe_allow_html=True)

        nearest_rows = []
        for _, row in filtered.iterrows():
            lat = row["緯度"]
            lon = row["經度"]

            if pd.isna(lat) or pd.isna(lon) or (lat == 0 and lon == 0):
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

            st.dataframe(
                nearest_df[["站名", "距離(公尺)", "可借", "可還"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("找不到最近站點資料。")
    else:
        st.markdown("""
        <div class="result-card">
            <div class="result-title">操作提示</div>
            請先在左側地圖上點一下，系統會自動幫你找出最近 3 個站點。
        </div>
        """, unsafe_allow_html=True)

# -----------------------------
# Detail blocks below
# -----------------------------
clicked = map_data.get("last_clicked") if map_data else None

if clicked:
    click_lat = clicked["lat"]
    click_lon = clicked["lng"]

    nearest_rows = []
    for _, row in filtered.iterrows():
        lat = row["緯度"]
        lon = row["經度"]

        if pd.isna(lat) or pd.isna(lon) or (lat == 0 and lon == 0):
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

        st.markdown('<div class="section-title">🏆 最近 3 個站點</div>', unsafe_allow_html=True)
        st.dataframe(
            nearest_df[["站名", "行政區", "可借", "可還", "距離(公尺)", "地址"]],
            use_container_width=True,
            hide_index=True
        )

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

        st.markdown('<div class="section-title">🧭 最近站點定位圖</div>', unsafe_allow_html=True)
        st_folium(m2, width=None, height=360)

        st.markdown('<div class="section-title">🌐 Google Maps 導航</div>', unsafe_allow_html=True)
        for _, row in nearest_df.iterrows():
            nav_url = f"https://www.google.com/maps/dir/{click_lat},{click_lon}/{row['緯度']},{row['經度']}"
            st.markdown(f"- [{row['站名']}｜距離 {row['距離(公尺)']} 公尺]({nav_url})")

# -----------------------------
# Query table
# -----------------------------
st.markdown('<div class="section-title">📋 查詢結果</div>', unsafe_allow_html=True)

if filtered.empty:
    st.warning("目前沒有符合條件的站點。")
else:
    st.dataframe(
        filtered[["站名", "行政區", "可借", "可還", "總車位", "地址"]],
        use_container_width=True,
        hide_index=True
    )
