import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo

# --- 1. Page Config & CSS ---
st.set_page_config(
    page_title="Surplus Bearings Warehouse",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>

/* collapse 버튼 제거 */
[data-testid="collapsedControl"] {
    display: none;
}

/* 사이드바 완전 고정 */
section[data-testid="stSidebar"] {
    position: fixed;
    top: 0;
    left: 0;
    width: 350px;
    min-width: 350px;
    max-width: 350px;
    height: 100vh;
    background-color: #f8f9fa;
    border-right: 1px solid #dee2e6;
}

/* 사이드바 내부 폭 */
section[data-testid="stSidebar"] > div {
    width: 350px;
    padding-top: 1rem;
}

/* 메인 영역 */
.main .block-container {
    margin-left: 350px;
    padding-left: 2rem;
    padding-right: 2rem;
    padding-top: 1.5rem;
    max-width: none;
}

/* 상단 제목 */
.main-header {
    background-color: #001f3f;
    padding: 20px;
    border-radius: 6px;
    color: white;
    text-align: center;
    margin-bottom: 25px;
}

/* 검색창 */
.stTextInput > div > div > input {
    border-radius: 6px;
}

/* 헤더 바 */
.table-header-row {
    background: #f3f4f6;
    border-top: 1px solid #d1d5db;
    border-bottom: 1px solid #d1d5db;
    padding: 10px 8px;
    margin-bottom: 0;
    font-weight: 700;
    font-size: 0.92rem;
    text-transform: uppercase;
    color: #111827;
}

/* 상품 row: 카드 말고 표 느낌 */
.product-row {
    padding: 12px 8px 10px 8px;
    border-bottom: 1px solid #e5e7eb;
    transition: background-color 0.12s ease;
}
.product-row:hover {
    background-color: #fafcff;
}

/* Part number 강조 */
.part-number {
    font-weight: 700;
    color: #111827;
}

/* 보조 텍스트 */
.subtle-text {
    color: #6b7280;
    font-size: 0.85rem;
}

/* 버튼 */
div[data-testid="stButton"] > button {
    border-radius: 6px;
    font-weight: 600;
}

/* 수량 입력칸 */
div[data-testid="stNumberInput"] input {
    text-align: center;
}

/* 사이드바 헤더 */
.cart-header-box {
    position: sticky;
    top: 0;
    z-index: 999;
    background: #f8f9fa;
    padding-bottom: 10px;
    margin-bottom: 12px;
    border-bottom: 1px solid #dee2e6;
}

/* 장바구니 아이템 */
.cart-item {
    background: white;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
}

/* 총 수량 박스 */
.cart-total-box {
    background: #eef6ff;
    border: 1px solid #cfe2ff;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 10px 0 14px 0;
    font-weight: 600;
}

/* 섹션 제목 */
.sidebar-section-title {
    margin-top: 8px;
    margin-bottom: 8px;
    font-weight: 700;
}

/* 모바일 대응 */
@media (max-width: 900px) {
    section[data-testid="stSidebar"] {
        width: 320px;
        min-width: 320px;
        max-width: 320px;
    }

    section[data-testid="stSidebar"] > div {
        width: 320px;
    }

    .main .block-container {
        margin-left: 320px;
        padding-left: 1rem;
        padding-right: 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0"


# --- 2. Google Sheets Connection ---
@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    secret_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_resource
def get_workbook():
    client = get_gspread_client()
    return client.open_by_url(SHEET_URL)


# --- 3. Data Loading ---
@st.cache_data(ttl=600)
def load_data():
    try:
        workbook = get_workbook()

        sheet1_rows = workbook.get_worksheet(0).get_all_values()[1:]
        sheet2_rows = workbook.get_worksheet(1).get_all_values()[1:]
        all_rows = sheet1_rows + sheet2_rows

        cleaned_data = []
        for row in all_rows:
            # 0=date, 1=part_number, 2=brand, 3=origin, 4=qty, 5=condition, 6=links
            if len(row) < 7:
                row += [""] * (7 - len(row))

            part_number = row[1].strip()
            if part_number:
                cleaned_data.append({
                    "part_number": row[1].strip(),
                    "brand": row[2].strip(),
                    "origin": row[3].strip(),
                    "qty": row[4].strip(),
                    "condition": row[5].strip(),
                    "links": row[6].strip(),
                })

        return cleaned_data

    except Exception as e:
        st.error(f"Data load error: {e}")
        return []


# --- 4. Session State ---
if "customer_cart" not in st.session_state:
    st.session_state.customer_cart = {}

if "inquiry_success" not in st.session_state:
    st.session_state.inquiry_success = False


# --- 5. Helpers ---
def make_item_key(item: dict) -> str:
    return f'{item["brand"]}__{item["part_number"]}__{item["origin"]}'


# --- 6. Main Content ---
st.markdown(
    '<div class="main-header"><h1>⚙️ SURPLUS BEARINGS WAREHOUSE</h1></div>',
    unsafe_allow_html=True
)

items = load_data()

if items:
    search_query = st.text_input(
        "",
        placeholder="Search by Part Number, Brand, or Origin...",
        label_visibility="collapsed"
    )

    filtered_items = [
        item for item in items
        if search_query.lower() in f'{item["part_number"]} {item["brand"]} {item["origin"]}'.lower()
    ]

    st.write(f"**{len(filtered_items)} HITS FOUND**")
    st.divider()

    # Header Row
    st.markdown("<div class='table-header-row'>", unsafe_allow_html=True)
    h1, h2, h3, h4, h5, h6, h7 = st.columns([1.5, 2.5, 1.5, 1, 1, 1, 2])
    h1.markdown("**BRAND**")
    h2.markdown("**PART NUMBER**")
    h3.markdown("**ORIGIN**")
    h4.markdown("**STOCK**")
    h5.markdown("**COND.**")
    h6.markdown("**PHOTO**")
    h7.markdown("**ORDER**")
    st.markdown("</div>", unsafe_allow_html=True)

    # Product Rows
    for i, item in enumerate(filtered_items):
        part_number = item["part_number"]
        brand = item["brand"]
        origin = item["origin"]
        qty = item["qty"]
        condition = item["condition"]
        links_str = item["links"]

        img_links = [link.strip() for link in links_str.split(",") if link.strip()]
        item_key = make_item_key(item)

        st.markdown("<div class='product-row'>", unsafe_allow_html=True)

        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 2.5, 1.5, 1, 1, 1, 2])

        c1.write(brand if brand else "-")
        c2.markdown(f"<div class='part-number'>{part_number}</div>", unsafe_allow_html=True)
        c3.write(origin if origin else "-")
        c4.write(qty if qty else "-")
        c5.write(condition if condition else "-")

        with c6:
            if img_links:
                with st.popover("📸 View"):
                    for img in img_links:
                        st.image(img)
            else:
                st.write("-")

        with c7:
            sub1, sub2 = st.columns([1, 1.2])

            with sub1:
                quantity_input = st.number_input(
                    "qty",
                    min_value=1,
                    value=1,
                    key=f"q_{i}",
                    label_visibility="collapsed"
                )

            with sub2:
                if st.button("Add", key=f"b_{i}", use_container_width=True):
                    if item_key in st.session_state.customer_cart:
                        st.session_state.customer_cart[item_key]["qty"] += quantity_input
                    else:
                        st.session_state.customer_cart[item_key] = {
                            "brand": brand,
                            "part_number": part_number,
                            "origin": origin,
                            "qty": quantity_input
                        }
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.warning("No inventory data found.")


# --- 7. Sidebar ---
with st.sidebar:
    st.markdown("""
        <div class="cart-header-box">
            <h2 style="margin-bottom: 0;">🛒 REQUEST QUOTE</h2>
            <div style="color: #6c757d; font-size: 0.9rem; margin-top: 4px;">
                Items in your cart are shown below.
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.inquiry_success:
        st.success("✅ Your quote request has been submitted.")
        st.session_state.inquiry_success = False

    if st.session_state.customer_cart:
        total_items = 0

        for item_key, cart_item in list(st.session_state.customer_cart.items()):
            st.markdown("<div class='cart-item'>", unsafe_allow_html=True)

            cp, cd = st.columns([4, 1])

            label = f'**{cart_item["part_number"]}** ({cart_item["qty"]} pcs)'
            if cart_item["brand"]:
                label += f'  \n{cart_item["brand"]}'
            if cart_item["origin"]:
                label += f' / {cart_item["origin"]}'

            cp.markdown(label)

            if cd.button("❌", key=f"del_{item_key}"):
                del st.session_state.customer_cart[item_key]
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

            total_items += cart_item["qty"]

        st.markdown(
            f"<div class='cart-total-box'>Total: {total_items} pcs</div>",
            unsafe_allow_html=True
        )

        if st.button("🗑️ Empty Cart", use_container_width=True):
            st.session_state.customer_cart = {}
            st.rerun()

        st.divider()
        st.markdown("<div class='sidebar-section-title'>✉️ Contact Information</div>", unsafe_allow_html=True)

        with st.form("inquiry_form"):
            buyer_name = st.text_input("Company / Name")
            buyer_contact = st.text_input("Email / Phone")
            buyer_msg = st.text_area("Message / Requests")

            submitted = st.form_submit_button(
                "🚀 SUBMIT REQUEST",
                type="primary",
                use_container_width=True
            )

            if submitted:
                if buyer_name and buyer_contact and st.session_state.customer_cart:
                    try:
                        workbook = get_workbook()
                        ws = workbook.get_worksheet(2)

                        now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")

                        rows = []
                        for cart_item in st.session_state.customer_cart.values():
                            rows.append([
                                now,
                                buyer_name,
                                buyer_contact,
                                cart_item["part_number"],
                                cart_item["brand"],
                                cart_item["origin"],
                                cart_item["qty"],
                                buyer_msg
                            ])

                        ws.append_rows(rows)

                        st.session_state.customer_cart = {}
                        st.session_state.inquiry_success = True
                        load_data.clear()
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error! Please try again. ({e})")
                else:
                    st.warning("Please fill in contact info and add items.")
    else:
        st.info("Your cart is empty. Add items from the list.")

# --- 6. Sidebar (기존 코드 하단에 이어서 추가) ---
    st.divider()
    
    # Contact Person Section
    st.markdown("""
        <div style="background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; margin-top: 10px;">
            <p style="margin-bottom: 5px; font-weight: 700; color: #001f3f; font-size: 0.95rem;">Your contact person</p>
            <p style="margin-bottom: 2px; font-weight: 600; font-size: 1.1rem;">Edward Kim</p>
            <p style="margin-bottom: 10px; color: #0056b3; font-size: 0.9rem;">
                <a href="mailto:edward.kim@jointrading.biz" style="text-decoration: none; color: inherit;">
                    edward.kim@jointrading.biz
                </a>
            </p>
            <p style="margin-bottom: 0; font-size: 0.85rem; color: #6c757d; line-height: 1.4;">
                If you have any questions or other suggestions, please feel free to contact me!
            </p>
        </div>
    """, unsafe_allow_html=True)


