import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib3

# 關閉 SSL 憑證警告資訊
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與佈局
st.set_page_config(page_title="經濟部首長行程原始碼檢視器", layout="wide")

st.title("🔍 經濟部首長行程 - 原始 HTML 撈取工具")
st.caption("目標網址：https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225")

if st.button("開始撈取網頁原始文本"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.moea.gov.tw/"
    }
    
    with st.spinner("正在向經濟部伺服器發送請求..."):
        try:
            target_url = "https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225"
            res = requests.get(target_url, headers=headers, timeout=15, verify=False)
            
            if res.status_code == 200:
                res.encoding = 'utf-8'
                raw_html = res.text
                
                soup = BeautifulSoup(raw_html, "html.parser")
                page_title = soup.title.string if soup.title else "未識別出標題"
                
                st.success(f"連線成功！網頁標題確認為：{page_title}")
                
                # 使用文字框呈現完整的 HTML 內容，方便複製與全域搜尋字串
                st.text_area(
                    label="HTML 原始碼 (請檢查內部是否含有 divSch 或 行程中文字)",
                    value=raw_html,
                    height=650
                )
            else:
                st.error(f"伺服器回應失敗，狀態碼 (Status Code): {res.status_code}")
                
        except Exception as e:
            st.error(f"執行請求時發生異常: {str(e)}")
