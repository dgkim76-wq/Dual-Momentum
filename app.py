import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime

# --- 실시간 지수 및 20일선 수집 함수 ---
@st.cache_data(ttl=3600)
def get_market_timing(ticker):
    try:
        df = fdr.DataReader(ticker).tail(100)
        if df.empty:
            return 0.0, 0.0
        
        df['MA20'] = df['Close'].rolling(window=20).mean()
        latest_close = float(df['Close'].iloc[-1])
        latest_ma20 = float(df['MA20'].dropna().iloc[-1])
        return latest_close, latest_ma20
    except:
        return 0.0, 0.0

st.set_page_config(page_title="듀얼 모멘텀 리밸런싱", layout="wide")
st.title("📈 듀얼 모멘텀 & 마켓 타이밍 실행기")

tab1, tab2 = st.tabs(["🔴 일일 리스크 체크", "📅 월간 리밸런싱"])

# --- 사이드바 ---
st.sidebar.header("포트폴리오 기초 설정")
target_date = st.sidebar.date_input("리밸런싱 기준일", datetime.today())

st.sidebar.markdown("**유안타증권(TRADER) 매수 가능 예수금**")
st.sidebar.caption("숫자만 입력 후 Enter를 누르세요. (예: 10000000)")
total_cash = st.sidebar.number_input("단위: 원", min_value=0, value=10000000, step=1000000, label_visibility="collapsed")
st.sidebar.success(f"현재 설정 금액: **{total_cash:,} 원**")

# --- Tab 1: 일일 리스크 체크 ---
with tab1:
    st.subheader("마켓 타이밍 20일선 필터")
    st.info("현재 지수와 20일 이동평균선을 비교하여 🟢유지 또는 🔴매도(현금화) 여부를 결정합니다.")
    
    with st.spinner('실시간 지수 데이터를 불러오는 중입니다...'):
        kospi_price, kospi_ma = get_market_timing("KS11")
        kosdaq_price, kosdaq_ma = get_market_timing("KQ11")
        sp500_price, sp500_ma = get_market_timing("US500")
    
    col1, col2, col3 = st.columns(3)
    
    def render_metric(col, label, price, ma20):
        if price == 0:
            col.metric(label=label, value="데이터 오류", delta="수집 불가")
            return
            
        status = "🟢 유지" if price >= ma20 else "🔴 이탈 (매도)"
        diff = price - ma20
        delta_color = "normal" if price >= ma20 else "inverse"
        
        col.metric(
            label=label, 
            value=f"{price:,.2f} ({status})", 
            delta=f"20일선({ma20:,.2f}) 대비 {diff:+,.2f}pt",
            delta_color=delta_color
        )

    render_metric(col1, "코스피 (KOSPI)", kospi_price, kospi_ma)
    render_metric(col2, "코스닥 (KOSDAQ)", kosdaq_price, kosdaq_ma)
    render_metric(col3, "S&P 500", sp500_price, sp500_ma)

# --- Tab 2: 월간 리밸런싱 ---
with tab2:
    st.subheader("모멘텀 산출 및 매수 주수 계산")
    
    # 가중 모멘텀(WMS) 산출식 설명으로 변경
    with st.expander("💡 가중 모멘텀 스코어(WMS) 계산식"):
        st.markdown("""
        * **계산 방식**: 최근 시장 트렌드에 민감하게 반응하기 위해 각 기간별 수익률에 서로 다른 가중치를 곱하여 산출합니다.
        * **공식**: `(3개월 수익률 × 9 + 6개월 수익률 × 6 + 9개월 수익률 × 3 + 12개월 수익률 × 1) / 19`
        * **우선 순위**: 산출된 가중 평균 수익률(WMS 스코어) 수치가 가장 높은 순서대로 투자 대상을 선정합니다.
        """)
        
    st.write("**📊 전체 유니버스 가중 모멘텀 현황 (시뮬레이션)**")
    st.markdown("""
    | 순위 | 자산군 | 종목명 | WMS 스코어 | 3개월 수익률 | 비고 |
    |---|---|---|---|---|---|
    | **1위** | 국내주식 | **KODEX 200IT TR** | **8.2%** | 8.5% | **매수 대상** |
    | **2위** | 원자재 | **ACE KRX금현물** | **5.4%** | 4.2% | **매수 대상** |
    | 3위 | 미국주식 | TIGER 미국S&P500 | 2.5% | 2.1% | - |
    | 4위 | 미국주식 | ACE 미국배당다우존스 | 1.8% | 1.5% | - |
    | 5위 | 수비자산 | TIGER 미국달러단기채권액티브 | 0.8% | 0.5% | 기준점 |
    | 6위 | 신흥국 | TIGER 인도니프티50 | -0.5% | -1.2% | - |
    | 7위 | 안전자산 | ACE 미국30년국채액티브(H) | -2.1% | -3.5% | - |
    """)
    
    st.divider()
    st.write("**💰 실시간 호가 입력 및 매수 주수 산출**")
    
    col4, col5 = st.columns(2)
    with col4:
        price_1 = st.number_input("1위 KODEX 200IT TR 매도 1호가", min_value=0, step=5, value=55885)
    with col5:
        price_2 = st.number_input("2위 ACE KRX금현물 매도 1호가", min_value=0, step=5, value=26490)
    
    if st.button("실행 계획 계산하기"):
        if price_1 > 0 and price_2 > 0:
            alloc_amt = total_cash * 0.5
            shares_1 = int(alloc_amt // price_1)
            shares_2 = int(alloc_amt // price_2)
            
            st.success("✅ 매수 계획 산출 완료")
            st.write(f"- **KODEX 200IT TR**: {shares_1}주 매수 (지정가: {price_1:,}원)")
            st.write(f"- **ACE KRX금현물**: {shares_2}주 매수 (지정가: {price_2:,}원)")
            
            remain_cash = total_cash - ((shares_1 * price_1) + (shares_2 * price_2))
            st.info(f"단수주 발생에 따른 잔여 현금: {int(remain_cash):,}원")