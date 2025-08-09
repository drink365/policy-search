import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="policy-search", page_icon="🔎", layout="wide")

@st.cache_data
def load_products():
    df = pd.read_csv("products.csv")
    # 基本清洗
    df["pay_terms_list"] = df["pay_terms"].apply(lambda s: [int(x) for x in str(s).split("|") if x.strip()])
    return df

def suggest_face_amount(budget_usd: float, base_prem_per_10k: float, age: int, pay_term: int) -> int:
    """
    以年度預算反推建議基本保額（估算用）：
    - 以 base_prem_per_10k 為基準
    - 粗略年齡係數與年期係數做調整
    """
    age_factor = 1.0 + max(0, age - 30) * 0.01      # 30歲以上每歲+1%保費係數（估算）
    term_factor = {6: 1.0, 8: 0.92, 12: 0.85, 20: 0.78}.get(pay_term, 1.0)
    unit_prem_est = base_prem_per_10k * age_factor / term_factor
    units = np.floor(budget_usd / max(unit_prem_est, 1e-6))
    face = int(units * 10000)
    return max(0, face)

def project_cash_value(annual_prem: float, pay_years: int, years: int, declared: float, guaranteed: float, load_rate: float, crediting_mode: str):
    """
    超簡化現金價值曲線（估算版）
    - 期末入帳、CV 以 (max(宣告-費用, 保證)) 成長
    - 不做退保費用與保障成本細化，純示意
    """
    eff = max(declared - load_rate, guaranteed)
    cv = []
    val = 0.0
    for y in range(1, years + 1):
        val = val * (1 + eff)
        if y <= pay_years:
            val += annual_prem
        cv.append(val)
    # 身故保額簡化：基本保額 + 「增額繳清」示意（CV 的 1% 略增 DB）
    if crediting_mode == "增額繳清":
        db_bump_ratio = 0.01
    else:
        db_bump_ratio = 0.0
    return np.array(cv), db_bump_ratio

def irr(cashflows, guess=0.05, tol=1e-7, max_iter=200):
    r = guess
    for _ in range(max_iter):
        t = np.arange(len(cashflows))
        disc = (1 + r) ** t
        npv = np.sum(np.array(cashflows) / disc)
        d = -np.sum(t * np.array(cashflows) / disc / (1 + r))
        if abs(d) < 1e-12:
            break
        r_new = r - npv / d
        if abs(r_new - r) < tol:
            return r_new
        r = r_new
    return r

def main():
    st.title("🔎 policy-search")
    st.caption("極簡版｜輸入需求 → 建議保額 & 估算曲線")

    df = load_products()
    col1, col2 = st.columns([1,2])

    with col1:
        st.subheader("條件")
        prod_name = st.selectbox("商品", df["product_name"].tolist(), index=0)
        row = df[df["product_name"] == prod_name].iloc[0]

        age = st.number_input("投保年齡（足歲）", min_value=int(row["min_issue_age"]), max_value=int(row["max_issue_age"]), value=30, step=1)
        sex = st.selectbox("性別", ["F", "M"], index=0)
        smoker = st.selectbox("是否抽菸", ["N", "Y"], index=0)
        pay_term = st.selectbox("繳費年期", row["pay_terms_list"], index=0)
        annual_budget = st.number_input("年度保費預算（USD）", min_value=2000, value=10000, step=500)
        declared_rate = st.slider("宣告利率（假設）", 0.0, 6.0, float(row["declared_rate_default"]*100), 0.05) / 100.0
        guaranteed_rate = st.slider("預定/保證利率", 0.0, 4.0, float(row["guaranteed_rate"]*100), 0.05) / 100.0
        load_rate = st.slider("內含費用率（估）", 0.0, 2.5, 1.0, 0.05) / 100.0
        crediting = st.selectbox("增值回饋運用", ["增額繳清","儲存生息","抵繳保費"], index=0)
        horizon = st.slider("觀察年期", 20, 60, 40, 1)

    with col2:
        st.subheader("建議與試算")
        face = suggest_face_amount(
            budget_usd=annual_budget,
            base_prem_per_10k=float(row["base_prem_per_10k_usd"]),
            age=age,
            pay_term=int(pay_term)
        )

        if face < int(row["min_face_usd"]):
            st.error(f"預算不足以達到最低保額（最低 {int(row['min_face_usd']):,} USD）。請提高預算或更改年期。")
            st.stop()

        st.success(f"建議基本保額：約 **{face:,} USD**")
        st.write("重點特色：", "、".join(str(row["features"]).split(";")))

        # 投保曲線
        cv, db_bump_ratio = project_cash_value(
            annual_prem=annual_budget,
            pay_years=int(pay_term),
            years=horizon,
            declared=declared_rate,
            guaranteed=guaranteed_rate,
            load_rate=load_rate,
            crediting_mode=crediting
        )
        years = np.arange(1, horizon+1)
        db = face * np.ones_like(cv) + cv * db_bump_ratio

        # IRR（示意）：期末身故給付
        cashflows = []
        for y in years:
            if y <= int(pay_term):
                cashflows.append(-annual_budget)
            else:
                cashflows.append(0.0)
        cashflows[-1] += db[-1]
        irr_val = irr(cashflows)

        st.metric("長期 IRR（示意）", f"{irr_val*100:.2f}%")
        st.line_chart(pd.DataFrame({"Cash Value (估)": cv, "Death Benefit (估)": db}, index=years))

        st.markdown("**風險與注意**")
        st.markdown(
            "- 宣告利率非保證，實際利益依公司公告而變動\n"
            "- 前期解約不利，短期解約可能損失本金\n"
            "- 幣別為 USD，折算台幣存在匯率風險\n"
            "- 本頁皆為估算示意，正式投保需以公司試算表與條款為準"
        )

if __name__ == "__main__":
    main()
