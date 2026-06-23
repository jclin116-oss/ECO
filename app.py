import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3

# 關閉 SSL 憑證警告資訊
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與佈局
st.set_page_config(page_title="經濟部網頁原始文本檢視器", layout="wide")

st.title("🔍 經濟部首長行程 - 原始 HTML 撈取工具")
st.caption("請點擊下方按鈕，觀察目前的網頁原始文本內容。")

# 經濟部首長行程的網址
url = "https://www.moea.gov.tw/Mns/populace/news/News.aspx?kind=8"

if st.button("開始撈取網頁原始文本"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    with st.spinner("正在讀取網頁中..."):
        try:
            res = requests.get(url, headers=headers, timeout=15, verify=False)
            if res.status_code == 200:
                res.encoding = 'utf-8'
                
                # 取得完整的 HTML 原始文字
                raw_html = res.text
                
                st.success("網頁原始文本撈取成功！")
                
                # 顯示網頁標題確認是否有抓對頁面
                soup = BeautifulSoup(raw_html, "html.parser")
                st.text(f"網頁標題：{soup.title.string if soup.title else '無標題'}")
                
                # 將原始文字呈現在文字框內供複製與檢視
                st.text_area(
                    label="HTML 原始碼 (您可以複製此段落到文字編輯器中查看詳細結構)",
                    value=raw_html,
                    height=600
                )
            else:
                st.error(f"連線失敗，錯誤代碼 (Status Code): {res.status_code}")
        except Exception as e:
            st.error(f"發生異常錯誤: {str(e)}")
