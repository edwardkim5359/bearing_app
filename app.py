import streamlit as st
import google.generativeai as genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. API 키 및 모델 설정
# 클라우드 비밀 금고(secrets)에서 GEMINI_API_KEY라는 이름의 열쇠를 가져옵니다.
GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
MODEL_NAME = 'models/gemini-2.5-flash'
genai.configure(api_key=GOOGLE_API_KEY)

# 2. 클라우드용 구글 시트 연결 함수 ⭐
def save_to_google_sheet(p_name, brand, qty, note):
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        # [변경됨] 파일 대신 스트림릿 클라우드의 '비밀 금고(secrets)'에서 열쇠를 가져옵니다.
        secret_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 사원님의 시트 주소
        sheet_url = "https://docs.google.com/spreadsheets/d/1cPeCqb2_Bq5ddG_UmS8L0wcR-8oNI3m7-nNC-dTDXBI/edit#gid=0" 
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        worksheet.append_row([now, p_name, brand, qty, note])
        return True
    except Exception as e:
        st.error(f"시트 저장 실패: {e}")
        return False

# 3. 앱 화면 구성
st.set_page_config(page_title="베어링 재고 자동 장부", layout="centered")
st.title("📱 베어링 자동 재고 장부 (Web)")
st.success("클라우드 엔진 가동 준비 완료!")

uploaded_file = st.file_uploader("베어링 사진 업로드", type=['jpg', 'jpeg', 'png'])
quantity = st.number_input("입고 수량", min_value=1, value=1)
note = st.text_input("특이사항")

if st.button("AI 분석 및 장부 기록", use_container_width=True):
    if uploaded_file is not None:
        try:
            with st.spinner('AI 분석 및 장부 기록 중...'):
                img = Image.open(uploaded_file)
                model = genai.GenerativeModel(MODEL_NAME)
                
                prompt = "이 사진 속 베어링의 품번(Part Number)과 브랜드(Brand)를 찾아서 '품번: [값], 브랜드: [값]' 형식으로 답해줘."
                response = model.generate_content([prompt, img])
                result_text = response.text
                
                lines = result_text.replace('\n', ',').split(',')
                p_id = lines[0].split(':')[-1].strip() if len(lines) > 0 else "미확인"
                b_name = lines[1].split(':')[-1].strip() if len(lines) > 1 else "미확인"

                if save_to_google_sheet(p_id, b_name, quantity, note):
                    st.balloons()
                    st.success(f"✅ 장부 기록 완료! (품번: {p_id} / {quantity}개)")
                    st.code(f"분석 결과: {result_text}")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")
    else:
        st.warning("사진을 올려주세요.")