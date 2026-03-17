import streamlit as st
import google.generativeai as genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
import base64
import io  # ⭐ 모바일 사진 압축을 위해 새로 추가된 필수 부품!

# --- 1. 기본 설정 ---
GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = 'models/gemini-2.5-flash'

SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"

# --- 2. 구글 시트 연결 ---
@st.cache_resource
def get_gspread_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    secret_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- 3. ImgBB 초고속 사진 업로드 (자동 압축 기능 추가) ---
def compress_image(file_obj):
    """휴대폰의 거대한 사진을 웹용으로 가볍게 줄여주는 함수"""
    img = Image.open(file_obj)
    
    # PNG 등 투명 배경이거나 특수 형식일 경우 기본 RGB(JPG)로 변환
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    # 사진 크기 줄이기 (가로/세로 최대 1024px로 맞춤 - AI 판독과 웹 표시에 충분함)
    img.thumbnail((1024, 1024))
    
    # 가벼워진 사진을 메모리에 임시 저장
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    output.seek(0)
    return output

def upload_to_imgbb(file_obj):
    url = "https://api.imgbb.com/1/upload"
    
    # ⭐ 업로드 직전에 사진을 가볍게 압축!
    compressed_file = compress_image(file_obj)
    
    payload = {
        "key": IMGBB_API_KEY,
        "image": base64.b64encode(compressed_file.getvalue()).decode("utf-8")
    }
    try:
        res = requests.post(url, data=payload)
        if res.status_code == 200:
            return res.json()["data"]["url"]
        else:
            # 실패 원인을 화면에 띄워주는 마법의 코드
            st.error(f"사진 업로드 실패 (코드 {res.status_code}): {res.text}")
            return None
    except Exception as e:
        st.error(f"인터넷 연결/업로드 에러 발생: {e}")
        return None

# --- 4. 상태 관리 ---
if 'cart' not in st.session_state: st.session_state.cart = []
if 'reset_key' not in st.session_state: st.session_state.reset_key = 0
if 'success_msg' not in st.session_state: st.session_state.success_msg = ""
if 'ai_done' not in st.session_state: st.session_state.ai_done = False
if 'temp_data' not in st.session_state: st.session_state.temp_data = {}

# --- 5. 앱 화면 구성 ---
st.set_page_config(page_title="Surplus Bearing Uploader", layout="centered")
st.header("Surplus Bearing Uploader")

if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = ""

tab1, tab2 = st.tabs(["🤖 신규 베어링 등록 (공급자용)", "📸 기존 재고 사진 매칭 (내 재고용)"])

# ==========================================
# [탭 1] 신규 베어링 등록 -> 구글 시트 "첫 번째 탭" 저장
# ==========================================
with tab1:
    st.subheader("1. 사진 업로드 및 판독")
    
    current_key = str(st.session_state.reset_key)
    uploaded_files = st.file_uploader("다각도 사진 업로드 (여러 장 가능)", type=['jpg', 'jpeg', 'png', 'heic'], accept_multiple_files=True, key=f"files_{current_key}")
    
    if not st.session_state.ai_done:
        if st.button("🤖 AI 분석 시작", use_container_width=True):
            if uploaded_files:
                with st.spinner("AI가 품번/브랜드/원산지를 판독 중입니다... 🧐"):
                    try:
                        img = Image.open(uploaded_files[0])
                        model = genai.GenerativeModel(MODEL_NAME)
                        prompt = "이 사진 속 베어링의 품번(Part Number), 브랜드(Brand), 원산지(Origin/Made in)를 찾아서 '품번: [값], 브랜드: [값], 원산지: [값]' 형식으로 답해줘. 안 보이면 '미확인'으로 해줘."
                        response = model.generate_content([prompt, img])
                        
                        text = response.text.replace('\n', ',')
                        parts = [p.strip() for p in text.split(',') if ':' in p]
                        
                        p_id, b_name, origin = "미확인", "미확인", "미확인"
                        for p in parts:
                            if "품번" in p: p_id = p.split(':')[-1].strip()
                            elif "브랜드" in p: b_name = p.split(':')[-1].strip()
                            elif "원산지" in p: origin = p.split(':')[-1].strip()
                        
                        st.session_state.temp_data = {"품번": p_id, "브랜드": b_name, "원산지": origin}
                        st.session_state.ai_done = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"분석 오류: {e}")
            else:
                st.warning("사진을 먼저 올려주세요!")
                
    if st.session_state.ai_done:
        st.info("💡 AI 판독 결과입니다. 틀린 글자가 있다면 직접 수정해 주세요!")
        col1, col2, col3 = st.columns(3)
        with col1: confirm_p_id = st.text_input("품번 (Part No.)", value=st.session_state.temp_data.get("품번", ""))
        with col2: confirm_b_name = st.text_input("브랜드 (Brand)", value=st.session_state.temp_data.get("브랜드", ""))
        with col3: confirm_origin = st.text_input("원산지 (Origin)", value=st.session_state.temp_data.get("원산지", ""))
            
        col4, col5 = st.columns([1, 2])
        with col4: quantity = st.number_input("입고 수량", min_value=1, value=1)
        with col5: condition = st.text_input("제품상태 (예: A급 신품, 박스없음)", placeholder="A급 신품")

        if st.button("✅ 정보 확정 및 장바구니 담기", type="primary", use_container_width=True):
            with st.spinner("사진을 클라우드에 저장하는 중..."):
                links = []
                for f in uploaded_files:
                    link = upload_to_imgbb(f)
                    if link: links.append(link)
                links_str = ",\n".join(links)

                st.session_state.cart.append({
                    "품번": confirm_p_id, "브랜드": confirm_b_name, "원산지": confirm_origin,
                    "수량": quantity, "제품상태": condition, "사진링크": links_str
                })
                
                st.session_state.success_msg = f"✅ [{confirm_p_id}] 장바구니 담기 완료! 다음 제품을 올려주세요."
                st.session_state.ai_done = False
                st.session_state.temp_data = {}
                st.session_state.reset_key += 1
                st.rerun()
                
        if st.button("취소하고 다시 올리기", use_container_width=True):
            st.session_state.ai_done = False
            st.session_state.temp_data = {}
            st.rerun()

    st.divider()
    
    st.subheader(f"🛒 장바구니 대기열 ({len(st.session_state.cart)}개)")
    if len(st.session_state.cart) > 0:
        for i, item in enumerate(st.session_state.cart):
            st.write(f"**{i+1}. {item['품번']}** | {item['브랜드']} | {item['원산지']} | {item['수량']}개 | {item['제품상태']} | 사진 {len(item['사진링크'].split(','))}장")

        if st.button("🚀 전체 구글 시트에 등록", type="primary", use_container_width=True):
            with st.spinner("구글 시트에 기록 중..."):
                try:
                    client = get_gspread_client()
                    # ⭐ 0번(첫 번째) 시트 탭에 저장합니다!
                    worksheet = client.open_by_url(SHEET_URL).get_worksheet(0)
                    rows_to_insert = []
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    for item in st.session_state.cart:
                        rows_to_insert.append([now, item["품번"], item["브랜드"], item["원산지"], item["수량"], item["제품상태"], item["사진링크"]])
                    
                    worksheet.append_rows(rows_to_insert)
                    st.session_state.cart = []
                    st.success("🎉 시트 등록 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

# ==========================================
# [탭 2] 기존 재고 매칭 -> 구글 시트 "두 번째 탭" 연동
# ==========================================
with tab2:
    st.subheader("내 재고 장부에 사진 매칭하기")
    st.info("두 번째 시트 탭에 입력된 마스터 리스트에서 품번을 검색합니다.")
    
    try:
        client = get_gspread_client()
        # ⭐ 1번(두 번째) 시트 탭에서 데이터를 읽어옵니다!
        worksheet_master = client.open_by_url(SHEET_URL).get_worksheet(1)
        all_part_numbers = worksheet_master.col_values(2)[1:] 
        valid_part_numbers = sorted(list(set([p for p in all_part_numbers if p.strip()])))
    except Exception as e:
        st.error("마스터 시트를 불러오는 데 실패했습니다. 두 번째 시트 탭이 만들어져 있는지 확인해 주세요!")
        valid_part_numbers = []

    if valid_part_numbers:
        search_part = st.selectbox("품번 검색 및 선택", options=["-- 품번을 선택하세요 --"] + valid_part_numbers)
        
        if search_part != "-- 품번을 선택하세요 --":
            match_files = st.file_uploader(f"[{search_part}] 제품 사진 업로드", type=['jpg', 'jpeg', 'png', 'heic'], accept_multiple_files=True, key="match_files")
            
            if st.button("📸 사진 매칭 및 시트 덮어쓰기", type="primary", use_container_width=True):
                if match_files:
                    with st.spinner("사진 업로드 및 시트 업데이트 중... 🚀"):
                        try:
                            links = []
                            for f in match_files:
                                link = upload_to_imgbb(f)
                                if link: links.append(link)
                            links_str = ",\n".join(links)
                            
                            # ⭐ 1번(두 번째) 시트 탭에서 품번을 찾고 덮어씁니다!
                            cell = worksheet_master.find(search_part, in_column=2)
                            if cell:
                                worksheet_master.update_cell(cell.row, 7, links_str)
                                st.success(f"✅ [{search_part}] 사진 매칭 완료! 내 재고 시트에 즉시 반영되었습니다.")
                            else:
                                st.error("해당 품번을 시트에서 찾을 수 없습니다.")
                        except Exception as e:
                            st.error(f"업데이트 오류: {e}")
                else:
                    st.warning("사진을 올려주세요!")
    else:
        st.write("두 번째 시트 탭에 등록된 기존 품번이 없습니다. 데이터를 먼저 넣어주세요!")