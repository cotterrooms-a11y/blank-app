# streamlit_app.py — Pension Modeler
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Pension Modeler", layout="wide")
st.title("Pension Modeler")

# --- Sidebar: Inputs ---------------------------------------------------------
st.sidebar.header("Inputs")

today = dt.date.today()
current_year = today.year

current_age = st.sidebar.number_input("Current age", 20, 75, 55, 1)
current_salary = st.sidebar.number_input("Current salary (€)", 0, 5_000_000, 100_000, 1_000)
salary_growth_pct = st.sidebar.number_input("Expected salary growth % (p.a.)", 0.0, 10.0, 2.0, 0.1)

current_service = st.sidebar.number_input("Current reckonable service (years)", 0.0, 45.0, 20.0, 0.5)

target_mode = st.sidebar.radio("Retirement target by…", ["Age", "Year"], horizontal=True)
if target_mode == "Age":
    retirement_age = st.sidebar.number_input("Desired retirement age", 55, 75, 65, 1)
    years_to_retirement = max(0, retirement_age - current_age)
    retirement_year = current_year + years_to_retirement
else:
    retirement_year = st.sidebar.number_input("Desired retirement year", current_year, current_year + 40, 2033, 1)
    years_to_retirement = max(0, retirement_year - current_year)
    retirement_age = current_age + years_to_retirement

annual_service_accrual = st.sidebar.number_input("Service accrual per year", 0.0, 2.0, 1.0, 0.1)
max_service_cap = st.sidebar.number_input("Max reckonable service cap", 20.0, 50.0, 40.0, 0.5)
valuation_factor = st.sidebar.number_input("Capitalisation factor (default 20)", 10.0, 50.0, 20.0, 0.5)

sft_now = st.sidebar.number_input("Current SFT (€)", 500_000, 10_000_000, 2_000_000, 50_000)
sft_growth_pct = st.sidebar.number_input("Assumed SFT growth % (p.a.)", 0.0, 10.0, 0.0, 0.1)

# --- Functions ---------------------------------------------------------------
def project_final_salary(salary_now: float, growth_pct: float, years: int) -> float:
    return salary_now * ((1 + growth_pct/100.0) ** years)

def project_service(service_now: float, accrual_per_year: float, years: int, cap: float) -> float:
    return min(service_now + accrual_per_year * years, cap)

def sft_at_year(sft_now: float, growth_pct: float, years: int) -> float:
    return sft_now * ((1 + growth_pct/100.0) ** years)

def classic_db_pension(final_salary: float, service_years: float):
    annual_pension = final_salary * (service_years / 80.0)
    lump_sum = final_salary * (service_years / 30.0)   # ~3/80ths
    return annual_pension, lump_sum

# --- Calculations ------------------------------------------------------------
final_salary = project_final_salary(current_salary, salary_growth_pct, years_to_retirement)
service_at_retirement = project_service(current_service, annual_service_accrual, years_to_retirement, max_service_cap)
annual_pension, lump_sum = classic_db_pension(final_salary, service_at_retirement)

sft_value = annual_pension * valuation_factor + lump_sum
sft_threshold_future = sft_at_year(sft_now, sft_growth_pct, years_to_retirement)

# --- Checks ------------------------------------------------------------------
issues = []
if years_to_retirement == 0:
    issues.append("Retirement is this year (years to retirement = 0).")
if abs(service_at_retirement - max_service_cap) < 1e-9:
    issues.append("Service hit the cap. Consider raising the cap or revising accrual.")
if retirement_age < current_age:
    issues.append("Retirement age is less than current age.")

# --- Summary -----------------------------------------------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("Summary")
    st.metric("Retirement Year", f"{retirement_year}")
    st.metric("Retirement Age", f"{int(round(retirement_age))} years")
    st.metric("Years to Retirement", f"{years_to_retirement} years")
    st.metric("Total Service at Retirement", f"{service_at_retirement:.2f} years")

with right:
    st.subheader("Benefit Projection")
    st.metric("Final Salary", f"€{final_salary:,.0f}")
    st.metric("Annual Pension (1/80th)", f"€{annual_pension:,.0f}")
    st.metric("Lump Sum (~3/80ths)", f"€{lump_sum:,.0f}")
    st.metric("SFT Valuation", f"€{sft_value:,.0f}")

st.info(f"Projected SFT threshold in {retirement_year}: **€{sft_threshold_future:,.0f}**")
if sft_value > sft_threshold_future:
    st.error("⚠️ Over the SFT threshold based on current assumptions.")
else:
    st.success("✅ Within SFT threshold under current assumptions.")

if issues:
    with st.expander("Checks & Warnings", expanded=True):
        for msg in issues:
            st.warning(msg)

# --- Scenarios ---------------------------------------------------------------
st.markdown("---")
tab1, tab2 = st.tabs(["Scenarios", "Assumptions Snapshot"])

with tab1:
    st.subheader("Scenario testing by retirement age")
    default_ages = [60, 62, 65, 66]
    ages = st.multiselect("Retirement ages to test", options=list(range(55, 76)), default=default_ages)

    rows = []
    for age in ages:
        yrs = max(0, age - current_age)
        ry = current_year + yrs
        fs = project_final_salary(current_salary, salary_growth_pct, yrs)
        svc = project_service(current_service, annual_service_accrual, yrs, max_service_cap)
        pen, ls = classic_db_pension(fs, svc)
        sft_val = pen * valuation_factor + ls
        sft_thr = sft_at_year(sft_now, sft_growth_pct, yrs)
        over = sft_val > sft_thr
        rows.append({
            "Ret Age": age,
            "Ret Year": ry,
            "Years to Ret": yrs,
            "Service (yrs)": round(svc, 2),
            "Final Salary (€)": round(fs, 0),
            "Annual Pension (€)": round(pen, 0),
            "Lump Sum (€)": round(ls, 0),
            "SFT Value (€)": round(sft_val, 0),
            "SFT Threshold (€)": round(sft_thr, 0),
            "Over SFT?": "Yes" if over else "No",
        })

    df = pd.DataFrame(rows).sort_values(["Ret Age"])
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download scenarios as CSV", data=csv, file_name="pension_scenarios.csv", mime="text/csv")

with tab2:
    st.write({
        "Current Year": current_year,
        "Current Age": current_age,
        "Current Salary": current_salary,
        "Salary Growth %": salary_growth_pct,
        "Current Service": current_service,
        "Service Accrual/Yr": annual_service_accrual,
        "Service Cap": max_service_cap,
        "Valuation Factor": valuation_factor,
        "SFT Now (€)": sft_now,
        "SFT Growth %": sft_growth_pct,
    })

