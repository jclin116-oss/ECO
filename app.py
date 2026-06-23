import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3
import re
import pandas as pd

# 關閉 SSL 憑證警告資訊
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與佈局
st.set_page_config(page_title="經濟部行程解析工具", layout="wide")

# --- 側邊欄配置：日期篩選器 ---
st.sidebar.header("設定抓取日期")
target_date = st.sidebar.date_input("選擇日期", datetime.today())
start_search = st.sidebar.button("開始同步並篩選資料")


def parse_moea_date(date_text):
    """
    將經濟部網頁上的日期字串轉換為標準的西元日期字串 "YYYY-MM-DD"
    支援格式如 "115-06-23" 或 "2026-06-23" 或 "115年06月23日"
    """
    if not date_text:
        return None
    try:
        # 移除空白
        date_text = date_text.strip()
        
        # 處理標準符合的 民國格式 (如 115-06-23 或 115.06.23)
        match = re.search(r'(\d+)[-./年](\d+)[-./月](\d+)', date_text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            
            # 判斷是否為民國年 (長度為3或小於1900)
            if year < 1900:
                year += 1911
                
            return f"{year}-{month:02d}-{day:02d}"
    except Exception:
        pass
    return None


def get_moea_data(url, title, target_date_str):
    """
    撈取經濟部政要行程，並解析出時間、官階、行程內容
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    scraped_data = []

    try:
        res = requests.get(url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")
            
            # 經濟部主要行程公告通常位於表格頁面 (由 tr 構成)
            # 根據經濟部標準版型，表格通常帶有 class="table" 或在特定 div 下
            rows = soup.find_all("tr")
            
            for row in rows:
                # 尋找表格內的欄位資料 (td)
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue
                
                # 經濟部版型常見格式：欄位1為日期/時間，欄位2為行程內容
                # 或是 欄位1為日期、欄位2為時間、欄位3為行程
                date_time_text = cols[0].get_text(strip=True)
                parsed_date_str = parse_moea_date(date_time_text)
                
                # 如果第一欄沒匹配到日期，嘗試檢視整行文字中是否含有目標日期
                if not parsed_date_str:
                    row_text = row.get_text(strip=True)
                    parsed_date_str = parse_moea_date(row_text)
                
                if parsed_date_str != target_date_str:
                    continue
                
                # 提取時間與內容
                # 預設行為：若有 3 個以上的欄位，欄位2通常為時間，欄位3為內容
                if len(cols) >= 3:
                    time_str = cols[1].get_text(strip=True)
                    content_str = cols[2].get_text(strip=True)
                else:
                    # 若只有 2 個欄位
                    time_str = "-"
                    content_str = cols[1].get_text(strip=True)
                
                # 清洗內容文字中可能殘留的換行或多餘空白
                content_str = re.sub(r'\s+', ' ', content_str).strip()
                time_str = re.sub(r'\s+', ' ', time_str).strip()
                
                if content_str:
                    scraped_data.append({
                        "時間": time_str if time_str else "-",
                        "官階": title,
                        "行程內容": content_str
                    })
    except Exception:
        pass
        
    # 如果當天完全沒有行程，塞入一筆「無公開行程」
    if not scraped_data:
        scraped_data.append({
            "時間": "-",
            "官階": title,
            "行程內容": "無公開行程"
        })
        
    return scraped_data


# --- 主畫面排版 ---
st.title("🏛️ 經濟部 - 行程解析工具")

if start_search:
    date_str = target_date.strftime("%Y-%m-%d")
    
    # 調整為經濟部對應官職的行程公開網址
    urls = {
        "部長": "https://www.moea.gov.tw/Mns/populace/news/News.aspx?kind=8",
        "政務次長": "https://www.moea.gov.tw/Mns/populace/news/News.aspx?kind=9",
        "常務次長": "https://www.moea.gov.tw/Mns/populace/news/News.aspx?kind=10"
    }
    
    all_rows = []
    
    with st.spinner(f"正在同步並解析 {date_str} 的經濟部行程資料..."):
        for title, base_url in urls.items():
            politician_rows = get_moea_data(base_url, title, date_str)
            all_rows.extend(politician_rows)
            
        df = pd.DataFrame(all_rows)
        
        st.success(f"查詢成功！已完成 {date_str} 的行程解析。")
        
        st.dataframe(df, use_container_width=True, hide_index=False)
        
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="匯出此表格為 CSV",
            data=csv_data,
            file_name=f"經濟部政要行程_{date_str}.csv",
            mime="text/csv"
        )
else:
    st.info("請於左側設定抓取日期後，點擊「開始同步並篩選資料」按鈕。")
