st.divider()
    st.subheader("💰 최종 자산배분 및 매수 주수 계산기")
    
    passed_assets = [r for r in results if r["Passed"]]
    passed_assets.sort(key=lambda x: x["WMS"], reverse=True)
    
    # ----------------------------------------------------
    # [수정됨] 안전자산 무조건 고정 로직 
    # WMS 비교를 없애고 TIGER 미국달러단기채권액티브(329750)를 고정 대피처로 지정
    # ----------------------------------------------------
    fixed_safe_asset = next((r for r in safe_results if r["Ticker"] == "329750"), None)
    
    portfolio = []
    if len(passed_assets) >= 2:
        st.success("🟢 **[리스크 온] 합격 종목 2개 이상**: WMS 1위, 2위 종목에 각각 50%씩 투자합니다.")
        portfolio = [(passed_assets[0], 0.5), (passed_assets[1], 0.5)]
    elif len(passed_assets) == 1 and fixed_safe_asset:
        st.warning(f"🟡 **[부분 방어] 합격 종목 1개**: WMS 1위 종목(50%)과 안전자산 {fixed_safe_asset['Name']}(50%)에 분산 투자합니다.")
        portfolio = [(passed_assets[0], 0.5), (fixed_safe_asset, 0.5)]
    elif fixed_safe_asset:
        st.error(f"🔴 **[리스크 오프] 전 세계 동반 하락장**: 안전자산 {fixed_safe_asset['Name']}에 전량(100%) 대피합니다.")
        portfolio = [(fixed_safe_asset, 1.0)]

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
