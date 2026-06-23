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


def parse_moea_date(date_block):
    """
    從日期區塊 (div class="sch_day_s") 中提取並轉換為標準 "YYYY-MM-DD" 格式
    例如輸入 "6月23日 2026" -> 返回 "2026-06-23"
    """
    if not date_block:
        return None
    try:
        text = date_block.get_text(separator=" ", strip=True)
        # 尋找 數字+月、數字+日、4碼西元年
        month_match = re.search(r'(\d+)\s*月', text)
        day_match = re.search(r'(\d+)\s*日', text)
        year_match = re.search(r'(\d{4})', text)
        
        if month_match and day_match and year_match:
            month = int(month_match.group(1))
            day = int(day_match.group(1))
            year = int(year_match.group(1))
            return f"{year}-{month:02d}-{day:02d}"
    except Exception:
        pass
    return None


def get_moea_schedule(url, target_date_str):
    """
    撈取經濟部首長行程網頁並解析
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
            
            # 依據圖片與原始碼，每個行程時段都是一個 class="divSch" 的區塊
            sch_blocks = soup.find_all(class_="divSch")
            
            current_date_str = None
            
            for block in sch_blocks:
                # 1. 檢查並更新目前區塊的日期 (如果該 block 內含有 sch_day_s)
                day_tag = block.find(class_="sch_day_s")
                if day_tag:
                    parsed_date = parse_moea_date(day_tag)
                    if parsed_date:
                        current_date_str = parsed_date
                
                # 如果沒有抓到目前所屬日期，跳過該行程
                if current_date_str != target_date_str:
                    continue
                
                # 2. 擷取官階 (如：部長、次長、所屬單位記者會)
                kind_tag = block.find(class_="minister-kind")
                if not kind_tag:
                    continue
                title = kind_tag.get_text(strip=True)
                
                # 3. 擷取行程詳細內文與時間 (位於 id 包含 HolderContent_repMinisterSchedule... 的 div)
                # 亦可透過抓取區塊內除 kind 外的文字內容做切分
                content_div = block.find(id=lambda x: x and 'HolderContent_repMinisterSchedule' in x)
                
                if content_div:
                    raw_text = content_div.get_text(separator="\n", strip=True)
                    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                    
                    if lines:
                        first_line = lines[0]
                        # 匹配時間格式如 "2:00 PM" 或 "10:00 AM" 或 "上午09:00"
                        time_match = re.match(r'^(\d+:\d+\s*[APMpm]+|[上下]午\s*\d+:\d+)', first_line)
                        
                        if time_match:
                            time_str = time_match.group(1)
                            # 將所有行合併後移除開頭的時間文字
                            full_content = " ".join(lines)
                            content_str = full_content.replace(time_str, "", 1).strip()
                        else:
                            # 本日無公開行程或其他無時間戳的格式
                            time_str = "-"
                            content_str = " ".join(lines)
                        
                        # 避免把多個官階重複塞入「無公開行程」，這邊作過濾優化
                        scraped_data.append({
                            "時間": time_str,
                            "官階": title,
                            "行程內容": content_str
                        })
                        
    except Exception as e:
        st.error(f"解析資料時發生錯誤: {str(e)}")
        
    return scraped_data


# --- 主畫面排版 ---
st.title("🏛️ 經濟部 - 行程解析工具")

if start_search:
    date_str = target_date.strftime("%Y-%m-%d")
    target_url = "https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225"
    
    with st.spinner(f"正在同步並解析 {date_str} 的經濟部行程資料..."):
        # 經濟部頁面是單一 URL 包含所有首長資料，只需呼叫一次
        results = get_moea_schedule(target_url, date_str)
        
        if results:
            df = pd.DataFrame(results)
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
            # 如果當天完全沒有任何該類別的資料被抓到
            df_empty = pd.DataFrame([{
                "時間": "-",
                "官階": "無資料",
                "行程內容": "當日無公開行程"
            }])
            st.warning(f"於 {date_str} 未偵測到公開行程。")
            st.dataframe(df_empty, use_container_width=True)
else:
    st.info("請於左側設定抓取日期後，點擊「開始同步並篩選資料」按鈕。")
