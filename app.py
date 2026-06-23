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

    # 初始化當天所有必須列出的預設類別字典，預設皆為無行程
    categories_status = {
        "部長": {"時間": "-", "行程內容": "本日無公開行程", "地點": "-"},
        "次長": {"時間": "-", "行程內容": "本日無公開行程", "地點": "-"},
        "所屬單位記者會": {"時間": "-", "行程內容": "本日無公開行程", "地點": "-"}
    }
    
    # 用於紀錄網頁上實際有抓到具體行程的類別，避免被預設的「無公開行程」覆蓋
    has_real_schedule = set()
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
                
                # 找出屬於該日期的所有行程區塊 <div class="divSch">
                sch_blocks = day_container.find_all(class_="divSch")
                if not sch_blocks:
                    sibling = day_container.find_next_sibling()
                    while sibling and "divSch" in sibling.get("class", []):
                        sch_blocks.append(sibling)
                        sibling = sibling.find_next_sibling()
                
                # 逐一解析行程
                for block in sch_blocks:
                    # 1. 提取類別/官階 (minister-kind)
                    kind_tag = block.find(class_="minister-kind")
                    title = kind_tag.get_text(strip=True) if kind_tag else None
                    
                    if not title or title not in categories_status:
                        continue
                    
                    # 2. 提取時間與行程標題 (sch-title)
                    title_tag = block.find(class_="sch-title")
                    if not title_tag:
                        continue
                    
                    title_text = title_tag.get_text(strip=True)
                    
                    # 檢查是否為無行程文字
                    if "本日無公開行程" in title_text:
                        # 如果該類別之前已經記錄過具體行程，不轉為「無行程」
                        if title not in has_real_schedule:
                            categories_status[title] = {"時間": "-", "行程內容": "本日無公開行程", "地點": "-"}
                        continue
                    
                    # 正常行程時間切分
                    time_match = re.match(r'^(\d+:\d+\s*[APMpm]+|[上下]午\s*\d+:\d+)', title_text)
                    if time_match:
                        time_str = time_match.group(1)
                        content_str = title_text.replace(time_str, "", 1).strip()
                    else:
                        time_str = "-"
                        content_str = title_text
                    
                    # 3. 提取地點 (sch-place)
                    place_tag = block.find(class_="sch-place")
                    if place_tag:
                        place_str = place_tag.get_text(strip=True).replace("地點：", "").strip()
                    else:
                        place_str = "-"
                    
                    # 填入實際行程資料（若同一類別有多筆行程，由新行程取代或可視需求改為 list，此處採單一覆蓋或初始化處理）
                    # 若同類別有多筆，直接更新或擴充機制：
                    if title not in has_real_schedule:
                        categories_status[title] = {"時間": time_str, "行程內容": content_str, "地點": place_str}
                        has_real_schedule.add(title)
                    else:
                        # 處理同類別當天有多筆行程的情況，將多筆行程資料整理合併成多列資料
                        if not isinstance(categories_status[title], list):
                            categories_status[title] = [categories_status[title]]
                        categories_status[title].append({"時間": time_str, "行程內容": content_str, "地點": place_str})
                        
    except Exception as e:
        st.error(f"解析網頁結構時發生錯誤: {str(e)}")
        
    # 將整理好的字典轉換為 DataFrame 格式所需的串列
    final_rows = []
    for cat in ["部長", "次長", "所屬單位記者會"]:
        data = categories_status[cat]
        if isinstance(data, list):
            for item in data:
                final_rows.append({
                    "時間": item["時間"],
                    "類別": cat,
                    "行程內容": item["行程內容"],
                    "地點": item["地點"]
                })
        else:
            final_rows.append({
                "時間": data["時間"],
                "類別": cat,
                "行程內容": data["行程內容"],
                "地點": data["地點"]
            })
            
    return final_rows


# --- 主畫面排版 ---
st.title("🏛️ 經濟部 - 行程解析工具")

if start_search:
    date_str = target_date.strftime("%Y-%m-%d")
    target_url = "https://www.moea.gov.tw/Mns/populace/news/MinisterSchedule.aspx?menu_id=42225"
    
    with st.spinner(f"正在同步並解析 {date_str} 的經濟部行程資料..."):
        results = get_moea_schedule(target_url, date_str)
        
        df = pd.DataFrame(results)
        st.success(f"查詢成功！已完成 {date_str} 的行程解析。")
        st.dataframe(df, use_container_width=True, hide_index=False)
        
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="匯出此表格為 CSV",
            data=csv_data,
            file_name=f"經濟部行程_{date_str}.csv",
            mime="text/csv"
        )
else:
    st.info("請於左側設定抓取日期後，點擊「開始同步並篩選資料」按鈕。")
