import streamlit as st
import pandas as pd

# 預設檔案路徑
DATA_FILE = "data/policies.xlsx"

st.set_page_config(page_title="保險商品查詢系統", page_icon="📦", layout="wide")

st.title("📦 保險商品查詢系統")
st.write("依性別、年齡、保額、繳費年期等條件查詢適合的保險商品。")

# 讀取 Excel
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        st.error(f"讀取檔案失敗：{e}")
        return pd.DataFrame()

df = load_data(DATA_FILE)

if df.empty:
    st.warning("尚未上傳或載入保險商品資料。請確認 `data/policies.xlsx` 是否存在。")
else:
    st.success("✅ 保險商品資料載入完成！")

    # 依欄位動態建立篩選器
    filters = {}
    for col in df.columns:
        unique_vals = df[col].dropna().unique()
        if df[col].dtype == 'object':  # 文字欄位
            filters[col] = st.multiselect(f"{col}（可多選）", options=unique_vals)
        else:  # 數字欄位
            min_val, max_val = int(df[col].min()), int(df[col].max())
            filters[col] = st.slider(f"{col} 範圍", min_val, max_val, (min_val, max_val))

    # 篩選邏輯
    filtered_df = df.copy()
    for col, val in filters.items():
        if isinstance(val, list) and val:  # 多選
            filtered_df = filtered_df[filtered_df[col].isin(val)]
        elif isinstance(val, tuple):  # 範圍
            filtered_df = filtered_df[(filtered_df[col] >= val[0]) & (filtered_df[col] <= val[1])]

    st.subheader("查詢結果")
    st.dataframe(filtered_df, use_container_width=True)

    # 匯出結果
    if not filtered_df.empty:
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="下載查詢結果 CSV",
            data=csv,
            file_name="保險商品查詢結果.csv",
            mime="text/csv"
        )
