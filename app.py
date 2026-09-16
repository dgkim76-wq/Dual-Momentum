import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime

# --- 실시간 지수 및 60일선 수집 함수 ---
@st.cache_data(ttl=3600)
def get_market_timing(ticker):
    try:
        # 60일선 계산을 위해 넉넉하게 최근 150일 데이터 수집
        df = fdr.DataReader(ticker).tail(150)
        if df.empty:
            return 0.0, 0.0
        
        df['MA60'] = df['Close'].rolling(window=60).mean()
        latest_close = float(df['Close'].iloc[-1])
        latest_ma60 = float(df['MA60'].dropna().iloc[-1])
        return latest_close, latest_ma60
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

# 데이터 수집 
with st.spinner('실시간 지수 데이터를 불러오는 중입니다...'):
    kospi_price, kospi_ma = get_market_timing("KS11")
    kosdaq_price, kosdaq_ma = get_market_timing("KQ11")
    sp500_price, sp500_ma = get_market_timing("US500")

# --- Tab 1: 일일 리스크 체크 ---
with tab1:
    st.subheader("마켓 타이밍 60일선 (중기 수급선) 필터")
    st.info("💡 **교차 검증 재진입 로직**: 현재 지수가 60일선을 상회하고, 매수 대상의 가중 모멘텀(WMS)이 0 초과일 때만 위험자산(주식)에 진입합니다. 조건 미달 시 안전자산(달러단기채 등)으로 대피합니다.")
    
    col1, col2, col3 = st.columns(3)
    
    def render_metric(col, label, price, ma60):
        if price == 0:
            col.metric(label=label, value="데이터 오류", delta="수집 불가")
            return
            
        is_uptrend = price >= ma60
        status = "🟢 진입/유지 가능" if is_uptrend else "🔴 현금화/안전자산 대피"
        diff = price - ma60
        delta_color = "normal" if is_uptrend else "inverse"
        
        col.metric(
            label=label, 
            value=f"{price:,.2f}", 
            delta=f"60일선({ma60:,.2f}) 대비 {diff:+,.2f}pt",
            delta_color=delta_color
        )
        
        # 하락장(60일선 이탈)일 경우 재진입 조건 경고문 출력
        if not is_uptrend:
            col.warning(f"⚠️ 재진입 조건: 지수가 {ma60:,.2f}pt를 재돌파하고\n1위 종목 WMS가 양수(+)일 때")

    render_metric(col1, "코스피 (KOSPI)", kospi_price, kospi_ma)
    render_metric(col2, "코스닥 (KOSDAQ)", kosdaq_price, kosdaq_ma)
    render_metric(col3, "S&P 500", sp500_price, sp500_ma)

# --- Tab 2: 월간 리밸런싱 ---
with tab2:
    st.subheader("모멘텀 산출 및 매수 주수 계산")
    
    with st.expander("💡 가중 모멘텀 스코어(WMS) 및 교차 검증 계산식"):
        st.markdown("""
        * **가중 모멘텀(WMS)**: `(3개월 수익률×9 + 6개월 수익률×6 + 9개월 수익률×3 + 12개월 수익률×1) / 19`
        * **매수 조건 (교차 검증)**: 타겟 지수가 60일선 위에 위치 **AND** 1위 종목의 WMS 스코어가 0 초과일 것.
        * **안전자산 대피**: 위 교차 검증을 충족하지 못할 경우, 하락장 방어를 위해 **TIGER 미국달러단기채권액티브** 등 안전자산으로 100% 리밸런싱합니다.
        """)
        
    st.write("**📊 전체 유니버스 가중 모멘텀 현황 (시뮬레이션)**")
    st.markdown("""
    | 순위 | 자산군 | 종목명 | WMS 스코어 | 3개월 수익률 | 60일선 필터 | 최종 판정 |
    |---|---|---|---|---|---|---|
    | **1위** | 국내주식 | **KODEX 200IT TR** | **8.2%** | 8.5% | 🟢 통과 (코스피) | **매수 대상** |
    | **2위** | 원자재 | **ACE KRX금현물** | **5.4%** | 4.2% | - | **매수 대상** |
    | 3위 | 미국주식 | TIGER 미국S&P500 | 2.5% | 2.1% | 🟢 통과 | - |
    | 4위 | 수비자산 | TIGER 미국달러단기채권액티브 | 0.8% | 0.5% | - | **대피처(조건 미달시)** |
    | 5위 | 신흥국 | TIGER 인도니프티50 | -0.5% | -1.2% | - | - |
    """)
    
    st.divider()
    st.write("**💰 실전 매수 계산기 (안전자산 대체재 포함)**")
    
    # 마켓 타이밍에 따른 시나리오 분기
    market_status = st.radio(
        "현재 교차 검증(마켓 타이밍 60일선 + WMS) 결과는 어떻습니까?",
        ("🟢 매수 조건 충족 (주식/원자재 듀얼 모멘텀 진행)", "🔴 매수 조건 미달 (안전자산 전량 대피)")
    )
    
    if market_status == "🟢 매수 조건 충족 (주식/원자재 듀얼 모멘텀 진행)":
        col4, col5 = st.columns(2)
        with col4:
            price_1 = st.number_input("1위 KODEX 200IT TR 매도 1호가", min_value=0, step=5, value=55885)
        with col5:
            price_2 = st.number_input("2위 ACE KRX금현물 매도 1호가", min_value=0, step=5, value=26490)
            
        if st.button("실행 계획 계산하기", key="btn1"):
            if price_1 > 0 and price_2 > 0:
                alloc_amt = total_cash * 0.5
                shares_1 = int(alloc_amt // price_1)
                shares_2 = int(alloc_amt // price_2)
                
                st.success("✅ [리스크 온] 주식/위험자산 매수 계획 산출 완료")
                st.write(f"- **KODEX 200IT TR (50%)**: {shares_1}주 매수 (지정가: {price_1:,}원)")
                st.write(f"- **ACE KRX금현물 (50%)**: {shares_2}주 매수 (지정가: {price_2:,}원)")
                
                remain_cash = total_cash - ((shares_1 * price_1) + (shares_2 * price_2))
                st.info(f"단수주 발생에 따른 잔여 현금: {int(remain_cash):,}원")
                
    else:
        col_safe, _ = st.columns(2)
        with col_safe:
            price_safe = st.number_input("수비자산 TIGER 미국달러단기채권액티브 매도 1호가", min_value=0, step=5, value=51200)
            
        if st.button("실행 계획 계산하기", key="btn2"):
            if price_safe > 0:
                shares_safe = int(total_cash // price_safe)
                
                st.error("🚨 [리스크 오프] 하락장 방어: 안전자산 전량(100%) 대피")
                st.write(f"- **TIGER 미국달러단기채권액티브 (100%)**: {shares_safe}주 매수 (지정가: {price_safe:,}원)")
                
                remain_cash = total_cash - (shares_safe * price_safe)
                st.info(f"단수주 발생에 따른 잔여 현금: {int(remain_cash):,}원")
