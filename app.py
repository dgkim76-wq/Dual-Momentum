import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime

# ----------------------------------------------------
# 1. 환경 설정 및 유니버스 정의
# ----------------------------------------------------
st.set_page_config(page_title="듀얼 모멘텀 실행기", layout="wide")

UNIVERSE = {
    "266370": "KODEX 200IT TR",
    "411060": "ACE KRX금현물",
    "360200": "TIGER 미국S&P500",
    "458730": "ACE 미국배당다우존스",
    "380340": "TIGER 인도니프티50"
}
SAFE_ASSETS = {
    "329750": "TIGER 미국달러단기채권액티브",
    "432320": "ACE 미국30년국채액티브(H)"
}

# ----------------------------------------------------
# 2. 기준일 연동 데이터 수집 엔진 (타임머신 기능 적용)
# ----------------------------------------------------
@st.cache_data(ttl=60)
def get_market_timing(ticker, target_date):
    try:
        # 충분한 과거 데이터를 확보하기 위해 2020년부터 수집
        df = fdr.DataReader(ticker, start='2020-01-01')
        df = df.dropna()
        if df.empty: return 0.0, 0.0, None
        
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # 선택한 기준일(target_date)까지만 데이터 슬라이싱
        target_dt = pd.to_datetime(target_date)
        df_target = df.loc[:target_dt]
        
        if df_target.empty: return 0.0, 0.0, None
        
        latest_close = float(df_target['Close'].iloc[-1])
        latest_ma60 = float(df_target['MA60'].dropna().iloc[-1])
        
        # 차트 출력을 위한 최근 120일(약 6개월) 데이터 추출 및 컬럼명 변경
        df_chart = df_target.tail(120)[['Close', 'MA60']]
        df_chart.columns = ['지수 (Close)', '60일선 (MA60)']
        
        return latest_close, latest_ma60, df_chart
    except:
        return 0.0, 0.0, None

@st.cache_data(ttl=60)
def analyze_asset(ticker, name, target_date, is_safe=False):
    try:
        df = fdr.DataReader(ticker, start='2020-01-01')
        df = df.dropna()
        
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # 선택한 기준일(target_date)까지만 데이터 슬라이싱
        target_dt = pd.to_datetime(target_date)
        df_target = df.loc[:target_dt]
        
        # WMS 계산을 위해 최소 1년(252영업일) 데이터 필요
        if df_target.empty or len(df_target) < 252: return None
            
        current_price = int(df_target['Close'].iloc[-1])
        ma60 = df_target['MA60'].iloc[-1]
        
        def get_return(days):
            if len(df_target) > days:
                past_price = df_target['Close'].iloc[-days-1]
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
# 3. 사이드바 및 대시보드 UI
# ----------------------------------------------------
st.title("📈 듀얼 모멘텀 & 마켓 타이밍 실행기")

st.sidebar.header("포트폴리오 기초 설정")
# 여기서 선택한 날짜가 전체 엔진의 기준일(target_date)로 작동합니다.
target_date = st.sidebar.date_input("리밸런싱 기준일", datetime.today())
total_cash = st.sidebar.number_input("매수 가능 예수금 (원)", min_value=0, value=10000000, step=1000000)
st.sidebar.success(f"설정 금액: **{total_cash:,} 원**")

tab1, tab2 = st.tabs(["🔴 일일 리스크 체크 (시장 전체 추세)", "📅 월간 리밸런싱 (동적 자산배분 실행)"])

with tab1:
    st.subheader(f"글로벌 주요 지수 현황 (기준일: {target_date})")
    with st.spinner('지수 차트 및 실시간 데이터를 불러오는 중입니다...'):
        kospi_price, kospi_ma, kospi_chart = get_market_timing("KS11", target_date)
        kosdaq_price, kosdaq_ma, kosdaq_chart = get_market_timing("KQ11", target_date)
        sp500_price, sp500_ma, sp500_chart = get_market_timing("US500", target_date)

    col1, col2, col3 = st.columns(3)
    def render_metric_and_chart(col, label, price, ma60, chart_data):
        if price == 0 or chart_data is None: return
        is_uptrend = price >= ma60
        
        # 1. 지표(Metric) 출력
        col.metric(
            label=label, 
            value=f"{price:,.2f}", 
            delta=f"60일선({ma60:,.2f}) 대비 {price - ma60:+,.2f}pt",
            delta_color="normal" if is_uptrend else "inverse"
        )
        
        # 2. 라인 차트(최근 6개월) 출력
        # 초록색(상승) 또는 빨간색(하락) 테마를 주기 위해 st.line_chart 색상 설정
        chart_color = ["#FF4B4B", "#2E86C1"] if not is_uptrend else ["#00CC96", "#2E86C1"]
        col.line_chart(chart_data, color=chart_color, height=250)

    render_metric_and_chart(col1, "코스피 (KOSPI)", kospi_price, kospi_ma, kospi_chart)
    render_metric_and_chart(col2, "코스닥 (KOSDAQ)", kosdaq_price, kosdaq_ma, kosdaq_chart)
    render_metric_and_chart(col3, "S&P 500", sp500_price, sp500_ma, sp500_chart)

with tab2:
    st.subheader(f"독립 모멘텀 산출 및 선발 (기준일: {target_date})")
    
    with st.spinner('선택하신 날짜 기준으로 유니버스를 분석 중입니다...'):
        results = []
        for tk, nm in UNIVERSE.items():
            res = analyze_asset(tk, nm, target_date)
            if res: results.append(res)
            
        safe_results = []
        for tk, nm in SAFE_ASSETS.items():
            res = analyze_asset(tk, nm, target_date, is_safe=True)
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
            "기준일 종가": f"{r['Price']:,}원",
            "WMS 스코어": f"{r['WMS']:.2f}%",
            "60일선": f"{r['MA60']:,.0f}원",
            "교차 검증 결과": status
        })
    
    if table_data:
        st.table(pd.DataFrame(table_data))
    else:
        st.error("데이터를 불러오지 못했습니다. 기준일을 변경해보세요. (상장한 지 1년이 안 된 ETF는 조회가 불가합니다.)")
    
    st.divider()
    st.subheader("💰 최종 자산배분 및 매수 주수 계산기")
    
    passed_assets = [r for r in results if r["Passed"]]
    passed_assets.sort(key=lambda x: x["WMS"], reverse=True)
    
    if safe_results:
        best_safe_asset = sorted(safe_results, key=lambda x: x["WMS"], reverse=True)[0]
    else:
        best_safe_asset = None
    
    portfolio = []
    if len(passed_assets) >= 2:
        st.success("🟢 **[리스크 온] 합격 종목 2개 이상**: WMS 1위, 2위 종목에 각각 50%씩 투자합니다.")
        portfolio = [(passed_assets[0], 0.5), (passed_assets[1], 0.5)]
    elif len(passed_assets) == 1 and best_safe_asset:
        st.warning(f"🟡 **[부분 방어] 합격 종목 1개**: WMS 1위 종목(50%)과 안전자산 1위 {best_safe_asset['Name']}(50%)에 분산 투자합니다.")
        portfolio = [(passed_assets[0], 0.5), (best_safe_asset, 0.5)]
    elif best_safe_asset:
        st.error(f"🔴 **[리스크 오프] 전 세계 동반 하락장**: 안전자산 1위 {best_safe_asset['Name']}에 전량(100%) 대피합니다.")
        portfolio = [(best_safe_asset, 1.0)]

    if portfolio:
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
