import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="Surplus Bearing Showroom", layout="wide", initial_sidebar_state="expanded")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"

# --- 2. 구글 시트 연결 (읽기 & 쓰기 권한) ---
@st.cache_resource
def get_gspread_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets'] 
    secret_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- 3. 데이터 초고속 불러오기 (10분 캐싱 & 에러 추적) ---
@st.cache_data(ttl=600)
def load_data():
    try:
        client = get_gspread_client()
        data1 = client.open_by_url(SHEET_URL).get_worksheet(0).get_all_values()[1:]
        data2 = client.open_by_url(SHEET_URL).get_worksheet(1).get_all_values()[1:]
        all_data = data1 + data2
        
        cleaned_data = []
        for row in all_data:
            if len(row) < 7: 
                row += [""] * (7 - len(row))
            if row[1].strip(): 
                cleaned_data.append(row)
        return cleaned_data
    # ⭐ 에러의 진짜 원인을 화면에 출력해 주는 마법의 코드
    except Exception as e:
        st.error(f"데이터를 불러오는 중 문제가 발생했습니다: {e}")
        return []

# --- 4. 고객용 장바구니 메모리 ---
if 'customer_cart' not in st.session_state: st.session_state.customer_cart = []
if 'inquiry_success' not in st.session_state: st.session_state.inquiry_success = False

# --- 5. 화면 구성 ---
st.title("⚙️ Surplus Bearing Showroom")
st.markdown("전 세계의 우수한 잉여 베어링 재고를 한눈에 확인하세요.")

if st.session_state.inquiry_success:
    st.success("🎉 견적 문의가 성공적으로 접수되었습니다! 담당자가 곧 연락드리겠습니다.")
    st.session_state.inquiry_success = False

items = load_data()

if not items:
    st.info("현재 등록된 재고가 없습니다.")
else:
    # --- [상단] 검색 필터 ---
    search_query = st.text_input("🔍 품번 또는 브랜드로 검색해보세요", placeholder="예: 6204, NSK, JAPAN...")
    
    filtered_items = []
    for item in items:
        search_target = f"{item[1]} {item[2]} {item[3]}".lower()
        if search_query.lower() in search_target:
            filtered_items.append(item)

    st.write(f"총 **{len(filtered_items)}**개의 상품이 있습니다.")
    st.divider()

    # --- [메인] 쇼핑몰 바둑판(Grid) 갤러리 ---
    cols = st.columns(4)
    for i, item in enumerate(filtered_items):
        date, p_id, b_name, origin, qty, condition, links_str = item
        
        img_links = [link.strip() for link in links_str.split(',') if link.strip()]
        thumbnail = img_links[0] if img_links else "https://via.placeholder.com/300x200?text=No+Image"

        with cols[i % 4]:
            st.image(thumbnail, use_container_width=True)
            st.subheader(f"{p_id}")
            st.caption(f"🏢 {b_name} | 🌍 {origin}")
            st.text(f"상태: {condition}")
            st.text(f"수량: {qty}개")
            
            if len(img_links) > 1:
                st.info(f"📸 다각도 사진 {len(img_links)}장 (상세