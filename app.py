import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime

# ----------------------------------------------------
# 1. 환경 설정 및 유니버스 정의 (HTS 화면 기준 완벽 매핑)
# ----------------------------------------------------
st.set_page_config(page_title="듀얼 모멘텀 실행기", layout="wide")

# 공격 자산 유니버스
UNIVERSE = {
    "266370": "KODEX 200IT TR",
    "411060": "ACE KRX금현물",
    "360200": "TIGER 미국S&P500",
    "458730": "ACE 미국배당다우존스",
    "380340": "TIGER 인도니프티50"
}
# 수비/안전자산 유니버스
SAFE_ASSETS = {
    "329750": "TIGER 미국달러단기채권액티브",
    "432320": "ACE 미국30년국채액티브(H)"
}

# ----------------------------------------------------
# 2. 정확도 높은 데이터 수집 엔진 (캐시 최소화 및 EOD 추출)
# ----------------------------------------------------
# ttl=60으로 설정하여 1분마다 새로운 데이터를 받아오도록 수정
@st.cache_data(ttl=60)
def get_market_timing(ticker):
    try:
        df = fdr.DataReader(ticker).tail(150)
        df = df.dropna() # 결측치 제거로 데이터 신뢰도 확보
        if df.empty: return 0.0, 0.0
        df['MA60'] = df['Close'].rolling(window=60).mean()
        # 가장 최근 완벽한 영업일의 종가와 60일선 추출
        return float(df['Close'].iloc[-1]), float(df['MA60'].dropna().iloc[-1])
    except:
        return 0.0, 0.0

@st.cache_data(ttl=60)
def analyze_asset(ticker, name, is_safe=False):
    try:
        df = fdr.DataReader(ticker).tail(260)
        df = df.dropna()
        if df.empty or len(df) < 60: return None
            
        current_price = int(df['Close'].iloc[-1])
        ma60 = df['Close'].rolling(window=60).mean().iloc[-1]
        
        def get_return(days):
            if len(df) > days:
                past_price = df['Close'].iloc[-days-1]
                return ((current_price - past_price) / past_price) * 100
            return 0.0
            
        ret_3m = get_return(63)
        ret_6m = get_return(126)
        ret_9m = get_return(189)
        ret_12m = get_return(252)
        
        wms = (ret_3m * 9 + ret_6m * 6 + ret_9m * 3 + ret_12m * 1) / 19
        
        is_uptrend = current_price >= ma60
        is_positive_wms = wms > 0
        
        passed = True if is_safe else (is_uptrend and is_positive_wms)

        return {
            "Ticker": ticker, "Name": name, "Price": current_price, "MA60": ma60,
            "Ret_3M": ret_3m, "WMS": wms, "Passed": passed,
            "IsUptrend": is_uptrend, "IsPosWMS": is_positive_wms, "IsSafe": is_safe
        }
    except:
        return None

# ----------------------------------------------------
# 3. 레이아웃 및 대시보드 UI
# ----------------------------------------------------
st.title("📈 듀얼 모멘텀 & 마켓 타이밍 실행기")

st.sidebar.header("포트폴리오 기초 설정")
target_date = st.sidebar.date_input("리밸런싱 기준일", datetime.today())
total_cash = st.sidebar.number_input("매수 가능 예수금 (원)", min_value=0, value=10000000, step=1000000)
st.sidebar.success(f"설정 금액: **{total_cash:,} 원**")

tab1, tab2 = st.tabs(["🔴 일일 리스크 체크 (시장 전체 추세)", "📅 월간 리밸런싱 (동적 자산배분 실행)"])

with tab1:
    st.subheader("글로벌 주요 지수 60일선 필터")
    with st.spinner('실시간 지수 데이터를 불러오는 중입니다...'):
        kospi_price, kospi_ma = get_market_timing("KS11")
        sp500_price, sp500_ma = get_market_timing("US500")

    col1, col2 = st.columns(2)
    def render_metric(col, label, price, ma60):
        if price == 0: return
        is_uptrend = price >= ma60
        col.metric(
            label=label, 
            value=f"{price:,.2f}", 
            delta=f"60일선({ma60:,.2f}) 대비 {price - ma60:+,.2f}pt",
            delta_color="normal" if is_uptrend else "inverse"
        )
    render_metric(col1, "코스피 (KOSPI)", kospi_price, kospi_ma)
    render_metric(col2, "S&P 500", sp500_price, sp500_ma)

with tab2:
    st.subheader("최근 영업일 기준 독립 모멘텀 산출 및 선발")
    
    with st.spinner('전체 유니버스의 가격 데이터를 동기화 중입니다...'):
        results = []
        for tk, nm in UNIVERSE.items():
            res = analyze_asset(tk, nm)
            if res: results.append(res)
            
        safe_results = []
        for tk, nm in SAFE_ASSETS.items():
            res = analyze_asset(tk, nm, is_safe=True)
            if res: safe_results.append(res)

    table_data = []
    for r in sorted(results + safe_results, key=lambda x: x['WMS'], reverse=True):
        status = "🛡️ 대피처(상시합격)" if r['IsSafe'] else ("🟢 합격" if r['Passed'] else "🔴 탈락")
        if not r['Passed'] and not r['IsSafe']:
            reasons = []
            if not r['IsUptrend']: reasons.append("60일선 하회")
            if not r['IsPosWMS']: reasons.append("WMS 음수")
            status += f" ({', '.join(reasons)})"
            
        table_data.append({
            "자산 구분": "안전자산" if r['IsSafe'] else "위험자산",
            "종목명": r['Name'],
            "최근 종가": f"{r['Price']:,}원",
            "WMS 스코어": f"{r['WMS']:.2f}%",
            "60일선": f"{r['MA60']:,.0f}원",
            "교차 검증 결과": status
        })
    st.table(pd.DataFrame(table_data))
    
    st.divider()
    st.subheader("💰 최종 자산배분 및 매수 주수 계산기")
    
    passed_assets = [r for r in results if r["Passed"]]
    passed_assets.sort(key=lambda x: x["WMS"], reverse=True)
    
    # 안전자산 중 가장 모멘텀이 좋은 종목 1개 선택 (달러채권 vs 30년국채)
    best_safe_asset = sorted(safe_results, key=lambda x: x["WMS"], reverse=True)[0]
    
    portfolio = []
    if len(passed_assets) >= 2:
        st.success("🟢 **[리스크 온] 합격 종목 2개 이상**: WMS 1위, 2위 종목에 각각 50%씩 투자합니다.")
        portfolio = [(passed_assets[0], 0.5), (passed_assets[1], 0.5)]
    elif len(passed_assets) == 1:
        st.warning(f"🟡 **[부분 방어] 합격 종목 1개**: WMS 1위 종목(50%)과 안전자산 1위 {best_safe_asset['Name']}(50%)에 분산 투자합니다.")
        portfolio = [(passed_assets[0], 0.5), (best_safe_asset, 0.5)]
    else:
        st.error(f"🔴 **[리스크 오프] 전 세계 동반 하락장**: 안전자산 1위 {best_safe_asset['Name']}에 전량(100%) 대피합니다.")
        portfolio = [(best_safe_asset, 1.0)]

    cols = st.columns(len(portfolio))
    inputs = []
    
    for i, (asset, weight) in enumerate(portfolio):
        with cols[i]:
            target_price = st.number_input(f"{asset['Name']} 매수호가 (비중 {int(weight*100)}%)", 
                                           value=int(asset['Price']), step=5, key=f"input_{i}")
            inputs.append((asset, weight, target_price))
            
    if st.button("최종 실행 계획 산출"):
        st.markdown("### 🛒 매수 지시서")
        used_cash = 0
        for asset, weight, target_price in inputs:
            if target_price > 0:
                alloc_amt = total_cash * weight
                shares = int(alloc_amt // target_price)
                cost = shares * target_price
                used_cash += cost
                st.write(f"- **{asset['Name']}**: {shares:,}주 매수 (지정가: {target_price:,}원) ➔ 투입 금액: {cost:,}원")
                
        st.info(f"단수주 발생에 따른 최종 잔여 현금: {int(total_cash - used_cash):,}원")
