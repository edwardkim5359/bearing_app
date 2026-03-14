import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="Surplus Bearings Warehouse", layout="wide", initial_sidebar_state="expanded")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"

# --- 2. 구글 시트 연결 ---
@st.cache_resource
def get_gspread_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets'] 
    secret_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- 3. 데이터 불러오기 (캐싱) ---
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
    except Exception as e:
        st.error(f"데이터를 불러오는 중 문제가 발생했습니다: {e}")
        return []

# --- 4. 고객용 장바구니 메모리 ---
if 'customer_cart' not in st.session_state or isinstance(st.session_state.customer_cart, list): 
    st.session_state.customer_cart = {} 
if 'inquiry_success' not in st.session_state: 
    st.session_state.inquiry_success = False

# --- 5. 화면 구성 ---
st.title("⚙️ Surplus Bearings Warehouse")
st.markdown("전 세계의 우수한 잉여 베어링 재고를 초고속으로 검색하고 견적을 요청하세요.")

if st.session_state.inquiry_success:
    st.success("🎉 견적 문의가 성공적으로 접수되었습니다! 담당자가 곧 연락드리겠습니다.")
    st.session_state.inquiry_success = False

items = load_data()

if not items:
    st.info("현재 등록된 재고가 없습니다.")
else:
    search_query = st.text_input("🔍 브랜드, 품번 또는 원산지로 검색해보세요", placeholder="예: NSK, 6204, JAPAN...")
    
    filtered_items = []
    for item in items:
        search_target = f"{item[1]} {item[2]} {item[3]}".lower()
        if search_query.lower() in search_target:
            filtered_items.append(item)

    st.write(f"총 **{len(filtered_items)}**개의 상품이 있습니다.")
    st.divider()

    # --- [메인] 리스트 뷰 ---
    h1, h2, h3, h4, h5, h6, h7 = st.columns([1.5, 2, 1.2, 1.8, 1, 1.2, 2])
    with h1: st.markdown("**브랜드 (Brand)**")
    with h2: st.markdown("**품명 (Part No.)**")
    with h3: st.markdown("**원산지**")
    with h4: st.markdown("**제품상태**")
    with h5: st.markdown("**수량**")
    with h6: st.markdown("**사진**")
    with h7: st.markdown("**수량 선택 및 담기**")
    st.divider()

    for i, item in enumerate(filtered_items):
        date, p_id, b_name, origin, qty, condition, links_str = item
        img_links = [link.strip() for link in links_str.split(',') if link.strip()]
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 2, 1.2, 1.8, 1, 1.2, 2])
        
        with col1: st.write(b_name)
        with col2: st.write(f"**{p_id}**")
        with col3: st.write(origin)
        with col4: st.write(condition)
        with col5: st.write(f"{qty}")
            
        with col6:
            if img_links:
                with st.popover("📸"):
                    for img in img_links:
                        # ⭐ ImgBB 썸네일 기술 적용: 원본 주소를 활용해 가벼운 미리보기 표시
                        st.image(img, use_container_width=True)
                        st.markdown(f"[🔍 원본 크게보기]({img})")
            else:
                st.write("-")
                
        with col7:
            max_q = None
            try: max_q = int(qty)
            except: pass
            
            sub_col1, sub_col2 = st.columns([1, 1.2])
            with sub_col1:
                selected_qty = st.number_input("수량", min_value=1, max_value=max_q, value=1, key=f"qty_{i}_{p_id}", label_visibility="collapsed")
            with sub_col2:
                if st.button("🛒 담기", key=f"btn_{i}_{p_id}", use_container_width=True):
                    st.session_state.customer_cart[p_id] = st.session_state.customer_cart.get(p_id, 0) + selected_qty
                    st.toast(f"[{p_id}] {selected_qty}개 추가!")
                
        st.markdown("<hr style='margin: 0px; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

# --- [사이드바] 견적 장바구니 & 발송 폼 ---
with st.sidebar:
    st.header("🛒 내 견적 바구니")
    
    if len(st.session_state.customer_cart) > 0:
        for p, q in st.session_state.customer_cart.items():
            st.write(f"✔️ **{p}** : {q}개")
            
        st.write(f"**총 {len(st.session_state.customer_cart)}개 품목**")
        
        if st.button("🗑️ 바구니 비우기", use_container_width=True):
            st.session_state.customer_cart = {}
            st.rerun()
            
        st.divider()
        
        st.subheader("✉️ 견적 문의하기")
        with st.form("inquiry_form"):
            buyer_name = st.text_input("회사명 / 담당자명")
            buyer_contact = st.text_input("이메일 또는 연락처")
            buyer_msg = st.text_area("추가 문의사항")
            
            submit_btn = st.form_submit_button("🚀 견적 발송", type="primary", use_container_width=True)
            
            if submit_btn:
                if not buyer_name or not buyer_contact:
                    st.error("필수 정보를 입력해 주세요!")
                else:
                    with st.spinner("발송 중..."):
                        try:
                            client = get_gspread_client()
                            worksheet_inquiry = client.open_by_url(SHEET_URL).get_worksheet(2)
                            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            new_rows = []
                            for p_id, q_val in st.session_state.customer_cart.items():
                                new_rows.append([now, buyer_name, buyer_contact, p_id, q_val, buyer_msg])
                            
                            worksheet_inquiry.append_rows(new_rows)
                            
                            st.session_state.customer_cart = {}
                            st.session_state.inquiry_success = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류 발생: {e}")
    else:
        st.info("견적 받을 품목을 담아주세요.")