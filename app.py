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


def get_moea_schedule(url, target_date_str):
    """
    撈取經濟部首長行程網頁並依 HTML 結構精確解析
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.moea.gov.tw/"
    }

    scraped_data = []
    target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")

    try:
        res = requests.get(url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")
            
            # 依據 ID 規則尋找所有的日期標籤 (lblDate_S_0, lblDate_S_1, 等)
            date_tags = soup.find_all(id=re.compile(r'lblDate_S_'))
            
            for d_tag in date_tags:
                # 取得日期中文字 (例如: 6月23日)
                date_text = d_tag.get_text(strip=True)
                
                # 尋找同一天大區塊的容器，用來定位年份與行程
                day_container = d_tag.find_parent(class_=re.compile(r'sch_day|divchs|divchs_items'))
                if not day_container:
                    day_container = d_tag.parent.parent
                
                # 取得年份
                year_tag = day_container.find(class_="sch_year")
                year_text = year_tag.get_text(strip=True) if year_tag else str(target_date_obj.year)
                
                # 轉換為標準西元日期字串
                month_match = re.search(r'(\d+)\s*月', date_text)
                day_match = re.search(r'(\d+)\s*日', date_text)
                
                if month_match and day_match:
                    m = int(month_match.group(1))
                    d = int(day_match.group(1))
                    y = int(year_text)
                    current_date_str = f"{y}-{m:02d}-{d:02d}"
                else:
                    continue
                
                # 如果不是使用者要查詢的日期，跳過此日期區塊
                if current_date_str != target_date_str:
                    continue
                
                # 找出屬於該日期的所有行程區塊 <div class="divSch">（包含部長、次長、所屬單位記者會）
                sch_blocks = day_container.find_all(class_="divSch")
                if not sch_blocks:
                    # 若因巢狀結構不在內部，則往後抓取同級節點
                    sibling = day_container.find_next_sibling()
                    while sibling and "divSch" in sibling.get("class", []):
                        sch_blocks.append(sibling)
                        sibling = sibling.find_next_sibling()
                
                # 逐一解析行程
                for block in sch_blocks:
                    # 1. 提取類別/官階 (minister-kind) -> 會抓到 "部長"、"次長" 或 "所屬單位記者會"
                    kind_tag = block.find(class_="minister-kind")
                    title = kind_tag.get_text(strip=True) if kind_tag else "未知類別"
                    
                    # 2. 提取時間與行程標題 (sch-title)
                    title_tag = block.find(class_="sch-title")
                    if not title_tag:
                        continue
                    
                    title_text = title_tag.get_text(strip=True)
                    
                    # 處理「本日無公開行程」或是正常的行程時間切分
                    if "本日無公開行程" in title_text:
                        time_str = "-"
                        content_str = "本日無公開行程"
                    else:
                        # 匹配時間格式，如 "4:00 PM" 或 "上午 09:00"
                        time_match = re.match(r'^(\d+:\d+\s*[APMpm]+|[上下]午\s*\d+:\d+)', title_text)
                        if time_match:
                            time_str = time_match.group(1)
                            content_str = title_text.replace(time_str, "", 1).strip()
                        else:
                            time_str = "-"
                            content_str = title_text
                    
                    # 3. 提取地點 (sch-place) -> 獨立成欄位
                    place_tag = block.find(class_="sch-place")
                    if place_tag:
                        place_str = place_tag.get_text(strip=True).replace("地點：", "").strip()
                    else:
                        place_str = "-"
                        
                    # 4. 提取說明備註 (sch-memo) -> 獨立成欄位
                    memo_tag = block.find(class_="sch-memo")
                    if memo_tag:
                        memo_str = memo_tag.get_text(separator=" ", strip=True).replace("※說明：", "").strip()
                    else:
                        memo_str = "-"
                    
                    scraped_data.append({
                        "時間": time_str,
                        "類別": title,
                        "行程內容": content_str,
                        "地點": place_str,
                        "備註說明": memo_str
                    })
                    
    except Exception as e:
        st.error(f"解析網頁結構時發生錯誤: {str(e)}")
        
    return scraped_data


# --- 主畫面排版 ---
st.title("🏛️ 經濟部 - 行程解析工具")

if start_search:
    date_str = target_date.strftime("%Y-%m-%d")
    target_url = "https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225"
    
    with st.
