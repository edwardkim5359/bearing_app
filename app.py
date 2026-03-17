import streamlit as st
from google import genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
import base64
import io
import json
import re

# --- 1. Page Config ---
st.set_page_config(page_title="Surplus Bearing Uploader", layout="centered")

# --- 2. 기본 설정 및 API 연결 ---
GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]

client_ai = genai.Client(api_key=GOOGLE_API_KEY)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"

# --- 3. 구글 시트 연결 함수 ---
@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    secret_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- 4. 사진 처리 보조 함수 ---
def get_image_bytes(file_obj):
    file_obj.seek(0)
    return file_obj.read()

def safe_open_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    return img

def upload_to_imgbb(image_bytes):
    url = "https://api.imgbb.com/1/upload"
    try:
        img = safe_open_image(image_bytes)
        img.thumbnail((1024, 1024))

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.post(
            url,
            data={"key": IMGBB_API_KEY, "image": img_str},
            headers=headers,
            timeout=30,
        )

        if res.status_code == 200:
            body = res.json()
            return body["data"]["url"]

        st.error(f"ImgBB 업로드 실패: {res.status_code} / {res.text}")
        return None

    except Exception as e:
        st.error(f"ImgBB 업로드 오류: {e}")
        return None

def parse_ai_json(text: str):
    if not text:
        return {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}

    # 코드블록 제거
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # JSON 본문만 추출
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}

    try:
        data = json.loads(match.group(0))
        return {
            "p_id": str(data.get("p_id", "Unknown")).strip() or "Unknown",
            "brand": str(data.get("brand", "Unknown")).strip() or "Unknown",
            "origin": str(data.get("origin", "Unknown")).strip() or "Unknown",
        }
    except Exception:
        return {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}

def analyze_bearing_image(image_bytes):
    img = safe_open_image(image_bytes)

    prompt = """
Analyze this bearing image.

Return ONLY valid JSON in exactly this format:
{
  "p_id": "Part Number",
  "brand": "Brand",
  "origin": "Origin"
}

Rules:
- Do not add explanation.
- Do not wrap in markdown unless necessary.
- If unknown, use "Unknown".
- Read visible text from the bearing/package/label if possible.
"""

    response = client_ai.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, img],
    )

    response_text = getattr(response, "text", None)
    if not response_text:
        raise ValueError("AI 응답이 비어 있습니다.")

    return parse_ai_json(response_text)

# --- 5. 세션 상태 초기화 ---
if "cart" not in st.session_state:
    st.session_state.cart = []

if "ai_done" not in st.session_state:
    st.session_state.ai_done = False

if "temp_data" not in st.session_state:
    st.session_state.temp_data = {}

if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""

# --- 6. 앱 UI 구성 ---
st.header("⚙️ Surplus Bearing Uploader")

if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = ""

tab1, tab2 = st.tabs(["🤖 신규 등록 (공급자용)", "📸 사진 매칭 (내 재고용)"])

# ==========================================
# [탭 1] 신규 등록 로직
# ==========================================
with tab1:
    st.subheader("1. 사진 업로드 및 판독")

    uploaded_files = st.file_uploader(
        "다각도 사진 업로드",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=f"up_{st.session_state.reset_key}",
    )
    st.caption("※ 모바일 접속 시 '파일 선택' 후 사진을 찍거나 앨범에서 골라주세요.")

    if not st.session_state.ai_done:
        if st.button("🤖 AI 분석 시작", use_container_width=True, type="primary"):
            if uploaded_files:
                with st.spinner("AI 분석 중..."):
                    try:
                        all_images_bytes = [get_image_bytes(f) for f in uploaded_files]
                        analyzed = analyze_bearing_image(all_images_bytes[0])

                        st.session_state.temp_data = {
                            "p_id": analyzed.get("p_id", "Unknown"),
                            "brand": analyzed.get("brand", "Unknown"),
                            "origin": analyzed.get("origin", "Unknown"),
                            "img_list": all_images_bytes,
                        }
                        st.session_state.ai_done = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"⚠️ 분석 중 오류가 발생했습니다: {e}")
            else:
                st.warning("사진을 먼저 선택해 주세요.")

    if st.session_state.ai_done:
        st.info("💡 AI가 판독한 내용입니다. 필요시 수정하세요.")

        c1, c2, c3 = st.columns(3)
        with c1:
            p_id = st.text_input("품번", value=st.session_state.temp_data.get("p_id", "Unknown"))
        with c2:
            brand = st.text_input("브랜드", value=st.session_state.temp_data.get("brand", "Unknown"))
        with c3:
            origin = st.text_input("원산지", value=st.session_state.temp_data.get("origin", "Unknown"))

        c4, c5 = st.columns([1, 2])
        with c4:
            qty = st.number_input("수량", min_value=1, value=1, step=1)
        with c5:
            cond = st.text_input("상태", value="New")

        if st.button("✅ 장바구니에 담기", use_container_width=True, type="primary"):
            with st.spinner("이미지 서버 전송 중..."):
                links = []
                for img_bytes in st.session_state.temp_data.get("img_list", []):
                    link = upload_to_imgbb(img_bytes)
                    if link:
                        links.append(link)

                if links:
                    st.session_state.cart.append(
                        {
                            "p_id": p_id,
                            "brand": brand,
                            "origin": origin,
                            "qty": int(qty),
                            "cond": cond,
                            "links": ",\n".join(links),
                        }
                    )
                    st.session_state.ai_done = False
                    st.session_state.temp_data = {}
                    st.session_state.reset_key += 1
                    st.session_state.success_msg = "장바구니에 추가되었습니다."
                    st.rerun()
                else:
                    st.error("이미지 업로드에 실패했습니다.")

        if st.button("🔄 취소", use_container_width=True):
            st.session_state.ai_done = False
            st.session_state.temp_data = {}
            st.session_state.reset_key += 1
            st.rerun()

    st.divider()
    st.subheader(f"🛒 등록 대기열 ({len(st.session_state.cart)}개)")

    if st.session_state.cart:
        for idx, item in enumerate(st.session_state.cart):
            st.write(f"{idx + 1}. **{item['p_id']}** ({item['brand']}) - {item['qty']}pcs")

        if st.button("🚀 구글 시트 전송하기", type="primary", use_container_width=True):
            try:
                client = get_gspread_client()
                sheet = client.open_by_url(SHEET_URL).get_worksheet(0)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows = [
                    [
                        now,
                        item["p_id"],
                        item["brand"],
                        item["origin"],
                        item["qty"],
                        item["cond"],
                        item["links"],
                    ]
                    for item in st.session_state.cart
                ]

                sheet.append_rows(rows)
                st.session_state.cart = []
                st.session_state.success_msg = "구글 시트 저장 완료!"
                st.rerun()

            except Exception as e:
                st.error(f"저장 실패: {e}")
    else:
        st.caption("아직 대기열에 등록된 항목이 없습니다.")

# ==========================================
# [탭 2] 기존 재고 사진 매칭
# ==========================================
with tab2:
    st.subheader("기존 품번 사진 업데이트")

    try:
        client = get_gspread_client()
        ws_master = client.open_by_url(SHEET_URL).get_worksheet(1)

        col_values = ws_master.col_values(2)
        p_list = sorted(list(set([p.strip() for p in col_values[1:] if p and p.strip()])))

        sel_p = st.selectbox("품번 선택", options=["-- 선택 --"] + p_list, key="match_selectbox")

        if sel_p != "-- 선택 --":
            m_files = st.file_uploader(
                "사진 업데이트",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="match_uploader",
            )

            if st.button("📸 매칭 실행", type="primary", use_container_width=True):
                if m_files:
                    with st.spinner("업로드 중..."):
                        m_links = []
                        for f in m_files:
                            link = upload_to_imgbb(get_image_bytes(f))
                            if link:
                                m_links.append(link)

                        if m_links:
                            target = ws_master.find(sel_p, in_column=2)
                            ws_master.update_cell(target.row, 7, ",\n".join(m_links))
                            st.success("업데이트 성공!")
                        else:
                            st.error("사진 업로드에 실패했습니다.")
                else:
                    st.warning("사진을 올려주세요.")

    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")