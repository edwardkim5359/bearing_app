import streamlit as st
import google.generativeai as genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
import base64
import io
import json
import re

# --- 1. Page Config (가장 먼저 와야 함) ---
st.set_page_config(page_title="Surplus Bearing Uploader", layout="centered")

# --- 2. 기본 설정 및 비밀키 ---
GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = 'gemini-1.5-flash' # 모델명 확인 (2.5는 현재 기준 미출시이므로 1.5로 수정)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"

# --- 3. 구글 시트 연결 ---
@st.cache_resource
def get_gspread_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    secret_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- 4. 사진 처리 함수 (커서 리셋 및 바이트 변환) ---
def get_image_bytes(file_obj):
    file_obj.seek(0)
    return file_obj.read()

def upload_to_imgbb(image_bytes):
    url = "https://api.imgbb.com/1/upload"
    try:
        # 가벼운 압축 후 전송
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((1024, 1024))
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        res = requests.post(url, data={"key": IMGBB_API_KEY, "image": img_str}, timeout=30)
        if res.status_code == 200:
            return res.json()["data"]["url"]
        return None
    except:
        return None

# --- 5. 상태 초기화 ---
for key in ['cart', 'ai_done', 'temp_data', 'reset_key']:
    if key not in st.session_state:
        if key == 'cart': st.session_state.cart = []
        elif key == 'ai_done': st.session_state.ai_done = False
        elif key == 'temp_data': st.session_state.temp_data = {}
        elif key == 'reset_key': st.session_state.reset_key = 0

# --- 6. 앱 UI ---
st.header("⚙️ Surplus Bearing Uploader")

tab1, tab2 = st.tabs(["🤖 신규 등록", "📸 사진 매칭"])

with tab1:
    st.subheader("1. 사진 업로드 및 판독")
    
    # 리셋 키를 이용해 업로더 강제 초기화 지원
    uploaded_files = st.file_uploader("사진을 선택하세요 (여러 장 가능)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key=f"up_{st.session_state.reset_key}")
    
    if not st.session_state.ai_done:
        if st.button("🤖 AI 분석 시작", use_container_width=True, type="primary"):
            if uploaded_files:
                with st.spinner("AI가 분석 중입니다..."):
                    try:
                        # 파일 증발 방지를 위해 모든 파일의 바이트를 세션에 즉시 저장
                        image_data_list = [get_image_bytes(f) for f in uploaded_files]
                        
                        model = genai.GenerativeModel(MODEL_NAME)
                        prompt = """
                        Bearing image analysis. Output ONLY in JSON format:
                        {"p_id": "Part Number", "brand": "Brand", "origin": "Origin"}
                        If not found, use "Unknown".
                        """
                        # 분석은 첫 번째 사진으로 수행
                        img_for_ai = Image.open(io.BytesIO(image_data_list[0]))
                        response = model.generate_content([prompt, img_for_ai])
                        
                        # JSON 추출 로직 (Markdown 태그 제거)
                        raw_text = response.text
                        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                        else:
                            data = {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}
                        
                        # 결과 및 바이트 리스트 저장
                        st.session_state.temp_data = {
                            "p_id": data.get("p_id", "Unknown"),
                            "brand": data.get("brand", "Unknown"),
                            "origin": data.get("origin", "Unknown"),
                            "images": image_data_list # 여기에 저장해야 안 날아감
                        }
                        st.session_state.ai_done = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"분석 실패: {e}")
            else:
                st.warning("사진을 먼저 올려주세요.")

    # 2단계: 결과 확인 및 수정
    if st.session_state.ai_done:
        st.info("💡 AI 판독 결과를 확인하세요.")
        c1, c2, c3 = st.columns(3)
        p_id = c1.text_input("품번", value=st.session_state.temp_data["p_id"])
        brand = c2.text_input("브랜드", value=st.session_state.temp_data["brand"])
        origin = c3.text_input("원산지", value=st.session_state.temp_data["origin"])
        
        c4, c5 = st.columns([1, 2])
        qty = c4.number_input("수량", min_value=1, value=1)
        cond = c5.text_input("상태", value="New")

        if st.button("✅ 장바구니에 담기", use_container_width=True, type="primary"):
            with st.spinner("이미지 서버 전송 중..."):
                links = []
                # 세션에 저장해둔 바이트 데이터 사용
                for img_bytes in st.session_state.temp_data["images"]:
                    link = upload_to_imgbb(img_bytes)
                    if link: links.append(link)
                
                if links:
                    st.session_state.cart.append({
                        "p_id": p_id, "brand": brand, "origin": origin,
                        "qty": qty, "cond": cond, "links": ",\n".join(links)
                    })
                    st.session_state.ai_done = False
                    st.session_state.temp_data = {}
                    st.session_state.reset_key += 1
                    st.rerun()
                else:
                    st.error("이미지 업로드에 실패했습니다.")

        if st.button("🔄 취소", use_container_width=True):
            st.session_state.ai_done = False
            st.rerun()

    # 장바구니 및 전송
    st.divider()
    st.subheader(f"🛒 대기열 ({len(st.session_state.cart)}개)")
    if st.session_state.cart:
        for idx, item in enumerate(st.session_state.cart):
            st.write(f"{idx+1}. **{item['p_id']}** ({item['brand']}) - {item['qty']}pcs")
        
        if st.button("🚀 구글 시트 최종 등록", type="primary", use_container_width=True):
            try:
                client = get_gspread_client()
                sheet = client.open_by_url(SHEET_URL).get_worksheet(0)
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data_to_save = [[now, i['p_id'], i['brand'], i['origin'], i['qty'], i['cond'], i['links']] for i in st.session_state.cart]
                sheet.append_rows(data_to_save)
                st.session_state.cart = []
                st.success("시트 저장 성공!")
                st.rerun()
            except Exception as e:
                st.error(f"시트 저장 실패: {e}")

with tab2:
    st.write("기존 리스트 매칭 기능 준비 중...")