import streamlit as st
from google import genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
import io
import json
import re

# --- 1. Page Config ---
st.set_page_config(page_title="Surplus Bearing Uploader", layout="centered")

# --- 2. API & Constants ---
GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"].strip()
DRIVE_FOLDER_ID = "0ALpBO5axL8i0Uk9PVA"  # Shared Drive Folder ID
SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"

client_ai = genai.Client(api_key=GOOGLE_API_KEY)

# --- 3. Google Services Connection ---
@st.cache_resource
def get_gcp_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    secret_dict = dict(st.secrets["gcp_service_account"])
    return Credentials.from_service_account_info(secret_dict, scopes=scopes)

def get_gspread_client():
    return gspread.authorize(get_gcp_credentials())

def get_drive_service():
    return build('drive', 'v3', credentials=get_gcp_credentials())

# --- 4. Image Processing (Memory Optimized) & Drive Upload ---
def compress_image_to_bytes(file_obj):
    """Compress image immediately to prevent Streamlit memory crashes."""
    try:
        img = Image.open(file_obj)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Resize to prevent memory overload
        img.thumbnail((1024, 1024))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Image compression error: {e}")
        return None

def upload_to_drive(image_bytes, file_name):
    try:
        service = get_drive_service()
        buffer = io.BytesIO(image_bytes)
        
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        media = MediaIoBaseUpload(buffer, mimetype='image/jpeg', resumable=True)
        
        # supportsAllDrives allows uploading to Enterprise Shared Drives
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()

        return f"https://drive.google.com/uc?id={file.get('id')}"
    except Exception as e:
        st.error(f"Drive upload error: {e}")
        return None

# --- 5. AI Analysis (Direct & Fast) ---
def parse_ai_json(text):
    if not text: return {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match: return {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}
    try:
        data = json.loads(match.group())
        return {
            "p_id": data.get("p_id", "Unknown"),
            "brand": data.get("brand", "Unknown"),
            "origin": data.get("origin", "Unknown"),
        }
    except:
        return {"p_id": "Unknown", "brand": "Unknown", "origin": "Unknown"}

def analyze_bearing(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    
    prompt = """
    Identify the bearing from the image. Look closely at the engravings or labels.
    1. Part Number (p_id): e.g., 6204ZZ, NU205, 32210.
    2. Brand: e.g., SKF, NSK, FAG, KOYO.
    3. Origin: e.g., Japan, Germany, Korea.
    Return ONLY JSON format: {"p_id": "...", "brand": "...", "origin": "..."}
    If entirely not visible, use "Unknown".
    """
    
    # Use the most stable and fast model directly
    response = client_ai.models.generate_content(
        model="gemini-2.5-flash", 
        contents=[prompt, img]
    )
    
    if response and response.text:
        return parse_ai_json(response.text)
    else:
        raise ValueError("AI returned no response.")

# --- 6. Session State Initialization ---
for key in ["cart", "ai_done", "temp_data", "reset_key"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "cart" else {} if key == "temp_data" else False if key == "ai_done" else 0

# --- 7. Main UI ---
st.header("⚙️ Surplus Bearing Uploader")
st.caption("Storage: Google Shared Drive (Enterprise)")

tab1, tab2 = st.tabs(["🤖 New Entry", "📸 Update Photo"])

# ==========================================
# Tab 1: New Entry
# ==========================================
with tab1:
    uploaded_files = st.file_uploader(
        "Upload Photos (JPG/PNG)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True, 
        key=f"up_{st.session_state.reset_key}"
    )

    if not st.session_state.ai_done:
        if st.button("🤖 Start AI Analysis", use_container_width=True, type="primary"):
            if uploaded_files:
                with st.spinner("AI is analyzing engravings and labels..."):
                    try:
                        # Compress immediately upon upload
                        imgs_bytes = [compress_image_to_bytes(f) for f in uploaded_files if f is not None]
                        if not imgs_bytes:
                            raise ValueError("Failed to process images.")
                            
                        result = analyze_bearing(imgs_bytes[0])
                        
                        st.session_state.temp_data = {
                            "p_id": result["p_id"], "brand": result["brand"], 
                            "origin": result["origin"], "imgs": imgs_bytes
                        }
                        st.session_state.ai_done = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Analysis Error: {e}")
            else:
                st.warning("Please upload photos first!")

    if st.session_state.ai_done:
        st.info("💡 Review AI Results (Edit if necessary)")
        c1, c2, c3 = st.columns(3)
        p_id = c1.text_input("Part No.", st.session_state.temp_data["p_id"])
        brand = c2.text_input("Brand", st.session_state.temp_data["brand"])
        origin = c3.text_input("Origin", st.session_state.temp_data["origin"])
        
        c4, c5 = st.columns([1, 2])
        qty = c4.number_input("Quantity", 1, 9999, 1)
        cond = c5.text_input("Condition", value="New")

        if st.button("✅ Add to Cart", use_container_width=True, type="primary"):
            with st.spinner("Uploading photos to Google Drive..."):
                links = []
                for i, img_data in enumerate(st.session_state.temp_data["imgs"]):
                    f_name = f"{p_id}_{datetime.now().strftime('%H%M%S')}_{i}.jpg"
                    link = upload_to_drive(img_data, f_name)
                    if link: links.append(link)

                if links:
                    st.session_state.cart.append({
                        "p_id": p_id, "brand": brand, "origin": origin,
                        "qty": qty, "cond": cond, "links": ",\n".join(links)
                    })
                    st.session_state.ai_done = False
                    st.session_state.temp_data = {}
                    st.session_state.reset_key += 1
                    st.success("Added to cart successfully!")
                    st.rerun()
                else:
                    st.error("Failed to upload to Drive.")

        if st.button("🔄 Cancel & Retry"):
            st.session_state.ai_done = False
            st.rerun()

# ==========================================
# Cart & Google Sheets Submission
# ==========================================
st.divider()
st.subheader(f"🛒 Cart ({len(st.session_state.cart)} items)")

if st.session_state.cart:
    for idx, item in enumerate(st.session_state.cart):
        st.write(f"{idx+1}. **{item['p_id']}** ({item['brand']}) - {item['qty']} pcs")

    if st.button("🚀 Submit to Google Sheets", type="primary", use_container_width=True):
        with st.spinner("Saving to Google Sheets..."):
            try:
                client = get_gspread_client()
                sheet = client.open_by_url(SHEET_URL).get_worksheet(0)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                rows = [
                    [now, i["p_id"], i["brand"], i["origin"], i["qty"], i["cond"], i["links"]] 
                    for i in st.session_state.cart
                ]
                
                sheet.append_rows(rows)
                st.session_state.cart = []
                st.success("🎉 Successfully saved to Google Sheets!")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

# ==========================================
# Tab 2: Update Photo
# ==========================================
with tab2:
    st.subheader("Update Existing Part Photo")
    try:
        client = get_gspread_client()
        ws_master = client.open_by_url(SHEET_URL).get_worksheet(1)
        p_list = sorted(list(set([p for p in ws_master.col_values(2)[1:] if p.strip()])))
        
        sel_p = st.selectbox("Select Part No.", options=["-- Select --"] + p_list)
        if sel_p != "-- Select --":
            m_files = st.file_uploader("Upload New Photos", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
            if st.button("📸 Execute Photo Match", type="primary", use_container_width=True):
                if m_files:
                    with st.spinner("Uploading to Drive..."):
                        links = []
                        for i, f in enumerate(m_files):
                            f_name = f"update_{sel_p}_{datetime.now().strftime('%H%M%S')}_{i}.jpg"
                            compressed_data = compress_image_to_bytes(f)
                            if compressed_data:
                                link = upload_to_drive(compressed_data, f_name)
                                if link: links.append(link)
                            
                        if links:
                            target = ws_master.find(sel_p, in_column=2)
                            ws_master.update_cell(target.row, 7, ",\n".join(links))
                            st.success("Update successful!")
                        else:
                            st.error("Upload failed.")
                else: st.warning("Please upload a photo.")
    except Exception as e:
        st.error(f"Failed to load data: {e}")