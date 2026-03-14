import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. 기본 설정 (넓은 화면 유지) ---
st.set_page_config(page_title="Surplus Bearing Showroom", layout="wide", initial_sidebar_state="expanded")

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
if 'customer_cart' not in st.session_state: st.session_state.customer_cart = []
if 'inquiry_success' not in st.session_state: st.session_state.inquiry_success = False

# --- 5. 화면 구성 ---
st.title("⚙️ Surplus Bearing Showroom")
st.markdown("전 세계의 우수한 잉여 베어링 재고를 초고속으로 검색하세요.")

if st.session_state.inquiry_success:
    st.success("🎉 견적 문의가 성공적으로 접수되었습니다! 담당자가 곧 연락드리겠습니다.")
    st.session_state.inquiry_success = False

items = load_data()

if not items:
    st.info("현재 등록된 재고가 없습니다.")
else:
    # --- [상단] 통합 검색 필터 ---
    search_query = st.text_input("🔍 품번 또는 브랜드로 검색해보세요", placeholder="예: 6204, NSK, JAPAN...")
    
    filtered_items = []
    for item in items:
        search_target = f"{item[1]} {item[2]} {item[3]}".lower()
        if search_query.lower() in search_target:
            filtered_items.append(item)

    st.write(f"총 **{len(filtered_items)}**개의 상품이 있습니다.")
    st.divider()

    # --- [메인] 초고속 리스트 뷰 (List View) ⭐ ---
    # 표의 제목줄(헤더) 만들기
    header_col1, header_col2, header_col3, header_col4, header_col5 = st.columns([2, 2, 2, 1.5, 1.5])
    with header_col1: st.markdown("**품번 (Part No.)**")
    with header_col2: st.markdown("**브랜드 / 원산지**")
    with header_col3: st.markdown("**상태 / 수량**")
    with header_col4: st.markdown("**제품 사진**")
    with header_col5: st.markdown("**견적 담기**")
    st.divider()

    # 리스트 데이터 뿌리기
    for i, item in enumerate(filtered_items):
        date, p_id, b_name, origin, qty, condition, links_str = item
        
        img_links = [link.strip() for link in links_str.split(',') if link.strip()]
        
        # 5칸으로 나누어서 정보 배치
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1.5, 1.5])
        
        with col1:
            st.write(f"**{p_id}**")
        with col2:
            st.write(f"{b_name} / {origin}")
        with col3:
            st.write(f"{condition} ({qty}개)")
            
        with col4:
            # 사진이 있으면 '팝업(Popover)' 버튼을 생성!
            if img_links:
                with st.popover("📸 사진 보기"):
                    # 팝업 창 안에서 사진들을 보여줍니다.
                    for img in img_links:
                        st.image(img, use_container_width=True)
            else:
                st.write("사진 없음")
                
        with col5:
            # 장바구니 버튼
            if st.button("🛒 담기", key=f"btn_{i}_{p_id}"):
                st.session_state.customer_cart.append(p_id)
                st.toast(f"[{p_id}] 장바구니에 담겼습니다! 💖")
                
        # 줄 구분선 (옅은 회색 선)
        st.markdown("<hr style='margin: 0px; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)

# --- [사이드바] 견적 장바구니 & 발송 폼 ---
with st.sidebar:
    st.header("🛒 내 견적 바구니")
    
    if len(st.session_state.customer_cart) > 0:
        unique_cart = list(set(st.session_state.customer_cart))
        
        for p in unique_cart:
            st.write(f"✔️ {p}")
        st.write(f"**총 {len(unique_cart)}개 품목**")
        
        if st.button("🗑️ 바구니 비우기"):
            st.session_state.customer_cart = []
            st.rerun()
            
        st.divider()
        
        st.subheader("✉️ 견적 문의하기")
        with st.form("inquiry_form"):
            buyer_name = st.text_input("회사명 / 담당자명 (필수)")
            buyer_contact = st.text_input("이메일 또는 연락처 (필수)")
            buyer_msg = st.text_area("남기실 말씀 (선택)", placeholder="수량이나 배송 관련 등 추가 문의사항을 적어주세요.")
            
            submit_btn = st.form_submit_button("🚀 이 목록으로 견적 발송", type="primary", use_container_width=True)
            
            if submit_btn:
                if not buyer_name or not buyer_contact:
                    st.error("회사명과 연락처를 꼭 입력해 주세요!")
                else:
                    with st.spinner("견적 문의를 전송하는 중입니다..."):
                        try:
                            client = get_gspread_client()
                            worksheet_inquiry = client.open_by_url(SHEET_URL).get_worksheet(2)
                            
                            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            items_str = ", ".join(unique_cart) 
                            
                            worksheet_inquiry.append_row([now, buyer_name, buyer_contact, items_str, buyer_msg])
                            
                            st.session_state.customer_cart = []
                            st.session_state.inquiry_success = True
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"전송 실패: 구글 시트 3번째 탭(견적문의함)이 만들어져 있는지 확인해주세요! ({e})")
    else:
        st.info("원하시는 베어링을 장바구니에 담아주세요.")