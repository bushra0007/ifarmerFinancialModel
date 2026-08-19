import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from pnl_calculator import (
    prepare_data,
    validate_data,
    calculate_row_level_pnl,
    generate_buyer_summary,
    generate_pnl_summary,
    predict_next_period,
    format_currency as fmt_txn,
)
from financial_parser import (
    parse_financial_csv,
    pnl_to_dataframe,
    predict_pnl,
    predict_by_buyer,
    allocate_costs_by_month_buyer,
    get_cost_ratios,
    normalize_month,
    extract_parent_buyer,
    build_finance_pct_lookup,
    format_currency as fmt_fin,
)

def fmt_crore(value):
    """Format value in crore BDT, showing just enough decimals."""
    if value == 0:
        return "0.00 Cr"
    val_crore = value / 10_000_000
    abs_val = abs(val_crore)
    sign = "-" if val_crore < 0 else ""
    if abs_val >= 100:
        return f"{sign}{abs_val:,.0f} Cr"
    elif abs_val >= 1:
        return f"{sign}{abs_val:,.2f} Cr"
    elif abs_val >= 0.1:
        return f"{sign}{abs_val:.2f} Cr"
    elif abs_val >= 0.01:
        return f"{sign}{abs_val:.3f} Cr"
    elif abs_val >= 0.001:
        return f"{sign}{abs_val:.4f} Cr"
    else:
        return f"{sign}{abs_val:.5f} Cr"

def generate_html_report():
    """Generate a standalone HTML report from current session data."""
    import plotly.io as pio

    sections = []
    sections.append("""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>iFarmer P&L Report</title>
<style>
body{font-family:'Segoe UI',sans-serif;margin:2rem;background:#f5f5f5;color:#1a1a1a;}
h1{color:#1a1a1a;border-bottom:3px solid #4CAF50;padding-bottom:0.5rem;}
h2{color:#333;margin-top:2rem;}
table{border-collapse:collapse;width:100%;margin:1rem 0;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);}
th{background:#4CAF50;color:#fff;padding:10px 12px;text-align:left;font-weight:600;}
td{padding:8px 12px;border-bottom:1px solid #eee;}
tr:hover{background:#f0f0f0;}
.chart{margin:1.5rem 0;}
.section{background:#fff;padding:1.5rem;border-radius:12px;margin:1.5rem 0;box-shadow:0 2px 12px rgba(0,0,0,0.08);}
.footer{margin-top:3rem;text-align:center;color:#999;font-size:0.85rem;}
</style></head><body>
<h1>  iFarmer P&L Dashboard Report</h1>
<p>Generated from iFarmer P&L Prediction Dashboard</p>
""")

    # Financial Overview
    if st.session_state.fin_data is not None:
        fin_df = pnl_to_dataframe(st.session_state.fin_data)
        sections.append('<div class="section"><h2>  Financial Overview</h2>')
        sections.append(fin_df.to_html(index=False, classes="", border=0))
        # KPIs
        total_rev = fin_df["revenue"].sum()
        total_cogs = fin_df["cogs"].sum()
        gp = total_rev - total_cogs
        total_sd = fin_df["total_sd"].sum()
        profit_after_sd = gp - total_sd
        total_admin = fin_df["admin_general"].sum()
        nop = profit_after_sd - total_admin
        total_fin = fin_df["financing"].sum()
        net_profit = nop - total_fin
        sections.append(f"""
        <table><tr><th>Metric</th><th>Amount (Crore BDT)</th><th>% of Sales</th></tr>
        <tr><td>Revenue</td><td>{fmt_crore(total_rev)}</td><td>100.0%</td></tr>
        <tr><td>COGS</td><td>{fmt_crore(total_cogs)}</td><td>{total_cogs/total_rev*100:.1f}%</td></tr>
        <tr><td>Gross Profit</td><td>{fmt_crore(gp)}</td><td>{gp/total_rev*100:.1f}%</td></tr>
        <tr><td>Total S&D</td><td>{fmt_crore(total_sd)}</td><td>{total_sd/total_rev*100:.1f}%</td></tr>
        <tr><td>Profit after S&D</td><td>{fmt_crore(profit_after_sd)}</td><td>{profit_after_sd/total_rev*100:.1f}%</td></tr>
        <tr><td>Admin & General</td><td>{fmt_crore(total_admin)}</td><td>{total_admin/total_rev*100:.1f}%</td></tr>
        <tr><td>Net Operating Profit</td><td>{fmt_crore(nop)}</td><td>{nop/total_rev*100:.1f}%</td></tr>
        <tr><td>Finance Cost</td><td>{fmt_crore(total_fin)}</td><td>{total_fin/total_rev*100:.1f}%</td></tr>
        <tr><td><b>Net Profit</b></td><td><b>{fmt_crore(net_profit)}</b></td><td><b>{net_profit/total_rev*100:.1f}%</b></td></tr>
        </table>""")
        sections.append('</div>')

    # Transaction P&L
    if st.session_state.pnl_data is not None:
        pnl_df = st.session_state.pnl_data
        sections.append('<div class="section"><h2>  Transaction P&L</h2>')
        summary = generate_pnl_summary(pnl_df)
        total_sales = summary["Total Sales"]
        summary_rows = [
            ("Sales", summary["Total Sales"]),
            ("COGS", summary["Total COGS"]),
            ("Gross Profit", summary["Gross Profit"]),
            ("S&D (Selling Opex)", summary["Total Selling Opex"]),
            ("Profit After S&D", summary["Profit After S&D"]),
            ("Admin & General Expense", summary["Total Admin Expense"]),
            ("Net Operating Profit", summary["Net Operating Profit"]),
            ("Finance Cost", summary["Total Finance Cost"]),
            ("Net Profit", summary["Net Profit"]),
        ]
        sections.append('<table><tr><th>Line Item</th><th>Amount</th><th>Contribution Margin</th></tr>')
        for name, val in summary_rows:
            cm = f"{val / total_sales * 100:.1f}%" if total_sales else "0.0%"
            sections.append(f'<tr><td>{name}</td><td>{fmt_crore(val)}</td><td>{cm}</td></tr>')
        sections.append('</table>')

        # Buyer summary
        buyer_summary = generate_buyer_summary(pnl_df)
        sections.append('<h3>Buyer-Level Summary</h3>')
        sections.append(buyer_summary.to_html(index=False, classes="", border=0))
        sections.append('</div>')

    # 6-Month Prediction
    if st.session_state.prediction_data is not None:
        combined = st.session_state.prediction_data
        fore = combined[combined["type"] == "Forecast"]
        if not fore.empty:
            sections.append('<div class="section"><h2>  6-Month P&L Forecast</h2>')
            forecast_cols = ["month", "revenue", "cogs", "gross_profit", "total_sd", "profit_after_sd", "admin_general", "financing", "net_profit"]
            display = fore[[c for c in forecast_cols if c in fore.columns]].copy()
            for col in display.columns:
                if col not in ["month"]:
                    display[col] = display[col].apply(lambda x: fmt_crore(x) if isinstance(x, (int, float)) else x)
            display.columns = [c.replace("_", " ").title() for c in display.columns]
            sections.append(display.to_html(index=False, classes="", border=0))
            sections.append('</div>')

    sections.append('<div class="footer"><p>iFarmer P&L Dashboard | Confidential</p></div>')
    sections.append('</body></html>')
    return "\n".join(sections)

st.set_page_config(
    page_title="iFarmer | P&L Dashboard",
    page_icon=" ",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── PASSWORD GATE ───────────────────────────────────────────────────────────
VIEWER_PASSWORD = "ifarmer2026"
ADMIN_PASSWORD = "ifarmer@admin"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.is_admin = False

if not st.session_state.authenticated:
    st.markdown("""
    <div style="display:flex;justify-content:center;align-items:center;height:80vh;">
        <div style="background:#f8f9fa;padding:3rem;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.1);max-width:400px;width:100%;text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.5rem;"> </div>
            <h2 style="margin:0 0 0.5rem 0;color:#1a1a1a;">iFarmer P&L Dashboard</h2>
            <p style="color:#666;margin-bottom:1.5rem;">Enter password to access</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    pwd = st.text_input("Password", type="password", key="login_pwd")
    if st.button("Login", type="primary"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.is_admin = True
            st.rerun()
        elif pwd == VIEWER_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.is_admin = False
            st.rerun()
        else:
            st.error("Invalid password")
    st.stop()

# ─── iFarmer DESIGN ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ── GLOBAL ── */
    .stApp { font-family: 'Inter', sans-serif; background: #ffffff; }
    .main .block-container { padding: 1rem 2rem 2rem 2rem; max-width: 1400px; }

    /* ── TEXT: dark on white bg ── */
    .stApp, .stApp p, .stApp span, .stApp li, .stApp label,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp div, .stApp code, .stApp pre {
        color: #1a1a1a;
    }
    /* Override: white text on dark backgrounds */
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] { color: #ffffff !important; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span { color: #e0e0e0 !important; }
    [data-baseweb="select"] [role="combobox"],
    [data-testid="stSelectbox"] [role="combobox"],
    [data-testid="stNumberInput"] input,
    [data-baseweb="input"] input {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    /* ── SIDEBAR - DARK BLACK BG, WHITE TEXT ── */
    [data-testid="stSidebar"] {
        background: #111111 !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] h2 {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: #e0e0e0 !important;
    }

    /* ── TABS - ALWAYS VISIBLE ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #ffffff;
        padding: 4px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.85rem;
        color: #1a1a1a !important;
        background: transparent;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: #f0f0f0;
    }
    .stTabs [aria-selected="true"] {
        background: #2e7d32 !important;
        color: #ffffff !important;
        font-weight: 600;
    }

    /* ── METRICS ── */
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 1.2rem 1rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        flex: 1 !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        display: flex !important;
        flex-direction: column !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div {
        flex: 1 !important;
    }
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
        color: #1a1a1a !important;
        font-size: 1.4rem !important;
        line-height: 1.2 !important;
        letter-spacing: -0.5px !important;
    }
    [data-testid="stMetricLabel"] {
        font-weight: 600 !important;
        color: #666666 !important;
        font-size: 0.65rem !important;
        text-transform: uppercase;
        letter-spacing: 0.8px !important;
        margin-bottom: 0.3rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
        margin-top: auto !important;
    }

    /* ── TABLES ── */
    .stDataFrame { border-radius: 8px; border: 1px solid #e0e0e0; }
    .stDataFrame th { background: #f5f5f5 !important; color: #1a1a1a !important; font-size: 0.7rem !important; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600 !important; }
    .stDataFrame td { color: #1a1a1a !important; }

    /* ── BUTTONS ── */
    .stButton > button {
        background: #2e7d32;
        color: white;
        border-radius: 6px;
        font-weight: 600;
        border: none;
    }

    .stButton > button:hover { background: #1b5e20; }
    .stDownloadButton > button { background: #2e7d32 !important; color: white !important; }

    /* ── FORM SUBMIT BUTTONS ── */
    [data-testid="stForm"] button,
    [data-testid="stForm"] [data-testid="stBaseButton"],
    [data-testid="stForm"] [data-testid="stBaseButton-secondary"] {
        background: #2e7d32 !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
    }
    [data-testid="stForm"] button:hover,
    [data-testid="stForm"] [data-testid="stBaseButton"]:hover {
        background: #1b5e20 !important;
    }

    /* ── SELECTS ── */
    .stSelectbox > div > div,
    .stMultiSelect > div > div { border-radius: 6px !important; border: 1px solid #cccccc !important; }

    /* ── ALERTS ── */
    [data-testid="stInfo"] { background: #e8f5e9 !important; border-left: 4px solid #2e7d32 !important; color: #1a1a1a !important; }
    [data-testid="stSuccess"] { background: #e8f5e9 !important; border-left: 4px solid #2e7d32 !important; color: #1a1a1a !important; }
    [data-testid="stWarning"] { background: #fff8e1 !important; border-left: 4px solid #f9a825 !important; color: #1a1a1a !important; }
    [data-testid="stError"] { background: #fce4ec !important; border-left: 4px solid #c62828 !important; color: #1a1a1a !important; }

    /* ── SECTION HEADER ── */
    .section-header {
        display: flex; align-items: center; gap: 0.5rem;
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #e0e0e0;
    }
    .section-header h2, .section-header h3 { margin: 0; font-size: 1.15rem; color: #1a1a1a !important; }

    /* ── CHARTS ── */
    .stPlotlyChart { border-radius: 8px; border: 1px solid #e0e0e0; background: #fff; }

    /* ── EXPANDER ── */
    .streamlit-expanderHeader { font-weight: 600 !important; color: #1a1a1a !important; background: #f5f5f5; border-radius: 6px; }

    /* ── HIDE ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* ── TOOLBAR - WHITE TEXT ── */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    header[data-testid="stHeader"] * {
        color: #ffffff !important;
    }
    [data-testid="stToolbar"] {
        background: #111111 !important;
    }
    [data-testid="stToolbar"] * {
        color: #ffffff !important;
    }
    [data-testid="stDecoration"] {
        background: #111111 !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── TITLE SECTION ────────────────────────────────────────────────────────────
st.markdown("""
<div style="background-color: #000000 !important; padding: 2.5rem 3rem 1.5rem 3rem; margin: 0 -2rem 1.5rem -2rem;">
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.8rem;">
        <svg width="60" height="60" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22L6.66 19.7C7.14 19.87 7.64 20 8 20C19 20 22 3 22 3C21 5 14 5.25 9 6.25C4 7.25 2 11.5 2 13.5C2 15.5 3.75 17.25 3.75 17.25C7 8 17 8 17 8Z" fill="#4CAF50"/>
        </svg>
        <h1 style="margin: 0; font-size: 2.8rem; font-weight: 800; color: white !important; text-shadow: none; letter-spacing: -1px;">iFarmer</h1>
    </div>
    <p style="margin: 0; font-size: 1.6rem; font-weight: 400; color: #cccccc !important;">Supply Chain P&L Analytics</p>
</div>
""", unsafe_allow_html=True)

if "txn_data" not in st.session_state:
    st.session_state.txn_data = None
if "fin_data" not in st.session_state:
    st.session_state.fin_data = None
if "pnl_data" not in st.session_state:
    st.session_state.pnl_data = None
if "prediction_data" not in st.session_state:
    st.session_state.prediction_data = None
if "buyer_prediction_data" not in st.session_state:
    st.session_state.buyer_prediction_data = None
if "wc_data" not in st.session_state:
    st.session_state.wc_data = None
if "wc_budget_data" not in st.session_state:
    st.session_state.wc_budget_data = None
if "budget_data" not in st.session_state:
    st.session_state.budget_data = None
if "fin_alloc_data" not in st.session_state:
    st.session_state.fin_alloc_data = None
if "fin_alloc_on" not in st.session_state:
    st.session_state.fin_alloc_on = None
if "fin_alloc_off" not in st.session_state:
    st.session_state.fin_alloc_off = None
if "salary_data" not in st.session_state:
    st.session_state.salary_data = None
if "buyer_budget_data" not in st.session_state:
    st.session_state.buyer_budget_data = None
if "buyer_actuals_data" not in st.session_state:
    st.session_state.buyer_actuals_data = None
if "supplier_budget_data" not in st.session_state:
    st.session_state.supplier_budget_data = None
if "supplier_actuals_data" not in st.session_state:
    st.session_state.supplier_actuals_data = None
if "inventory_data" not in st.session_state:
    st.session_state.inventory_data = None
if "prev_year_data" not in st.session_state:
    st.session_state.prev_year_data = None
if "tax_data" not in st.session_state:
    st.session_state.tax_data = None

# ─── AUTO-LOAD SAVED DATA ─────────────────────────────────────────────────────
import os
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def save_uploaded_file(filename, df_or_data, file_type="csv"):
    """Save uploaded data to the data directory."""
    path = os.path.join(DATA_DIR, filename)
    if isinstance(df_or_data, pd.DataFrame):
        df_or_data.to_csv(path, index=False)
    elif isinstance(df_or_data, dict):
        import json
        with open(path, "w") as f:
            json.dump(df_or_data, f)

def load_saved_data():
    """Load previously saved data from the data directory on startup."""
    # Transaction data
    txn_path = os.path.join(DATA_DIR, "txn_data.csv")
    if os.path.exists(txn_path) and st.session_state.txn_data is None:
        try:
            df = pd.read_csv(txn_path)
            is_valid, _ = validate_data(df)
            if is_valid:
                st.session_state.txn_data = prepare_data(df)
        except Exception:
            pass

    # Financial data
    fin_path = os.path.join(DATA_DIR, "fin_data.json")
    if os.path.exists(fin_path) and st.session_state.fin_data is None:
        try:
            import json
            with open(fin_path, "r") as f:
                st.session_state.fin_data = json.load(f)
        except Exception:
            pass

    # Working capital
    wc_path = os.path.join(DATA_DIR, "wc_data.csv")
    if os.path.exists(wc_path) and st.session_state.wc_data is None:
        try:
            st.session_state.wc_data = pd.read_csv(wc_path)
        except Exception:
            pass

    # Budget working capital
    wc_budget_path = os.path.join(DATA_DIR, "wc_budget_data.csv")
    if os.path.exists(wc_budget_path) and st.session_state.wc_budget_data is None:
        try:
            st.session_state.wc_budget_data = pd.read_csv(wc_budget_path)
        except Exception:
            pass

    # Budget
    budget_path = os.path.join(DATA_DIR, "budget_data.csv")
    if os.path.exists(budget_path) and st.session_state.budget_data is None:
        try:
            st.session_state.budget_data = pd.read_csv(budget_path)
        except Exception:
            pass

    # Finance cost on-season
    fin_on_path = os.path.join(DATA_DIR, "fin_alloc_on.csv")
    if os.path.exists(fin_on_path) and st.session_state.fin_alloc_on is None:
        try:
            st.session_state.fin_alloc_on = pd.read_csv(fin_on_path)
        except Exception:
            pass

    # Finance cost off-season
    fin_off_path = os.path.join(DATA_DIR, "fin_alloc_off.csv")
    if os.path.exists(fin_off_path) and st.session_state.fin_alloc_off is None:
        try:
            st.session_state.fin_alloc_off = pd.read_csv(fin_off_path)
        except Exception:
            pass

    # Salary data
    salary_path = os.path.join(DATA_DIR, "salary_data.csv")
    if os.path.exists(salary_path) and st.session_state.salary_data is None:
        try:
            st.session_state.salary_data = pd.read_csv(salary_path)
        except Exception:
            pass

    # Buyer budget
    buyer_budget_path = os.path.join(DATA_DIR, "buyer_budget_data.csv")
    if os.path.exists(buyer_budget_path) and st.session_state.buyer_budget_data is None:
        try:
            st.session_state.buyer_budget_data = pd.read_csv(buyer_budget_path)
        except Exception:
            pass

    # Buyer actuals
    buyer_actuals_path = os.path.join(DATA_DIR, "buyer_actuals_data.csv")
    if os.path.exists(buyer_actuals_path) and st.session_state.buyer_actuals_data is None:
        try:
            st.session_state.buyer_actuals_data = pd.read_csv(buyer_actuals_path)
        except Exception:
            pass

    # Supplier budget
    supplier_budget_path = os.path.join(DATA_DIR, "supplier_budget_data.csv")
    if os.path.exists(supplier_budget_path) and st.session_state.supplier_budget_data is None:
        try:
            st.session_state.supplier_budget_data = pd.read_csv(supplier_budget_path)
        except Exception:
            pass

    # Supplier actuals
    supplier_actuals_path = os.path.join(DATA_DIR, "supplier_actuals_data.csv")
    if os.path.exists(supplier_actuals_path) and st.session_state.supplier_actuals_data is None:
        try:
            st.session_state.supplier_actuals_data = pd.read_csv(supplier_actuals_path)
        except Exception:
            pass

    # Inventory data
    inventory_path = os.path.join(DATA_DIR, "inventory_data.csv")
    if os.path.exists(inventory_path) and st.session_state.inventory_data is None:
        try:
            st.session_state.inventory_data = pd.read_csv(inventory_path)
        except Exception:
            pass

    # Previous year data
    prev_year_path = os.path.join(DATA_DIR, "prev_year_data.json")
    if os.path.exists(prev_year_path) and st.session_state.prev_year_data is None:
        try:
            import json
            with open(prev_year_path, "r") as f:
                st.session_state.prev_year_data = json.load(f)
        except Exception:
            pass

    # Tax data
    tax_path = os.path.join(DATA_DIR, "tax_data.csv")
    if os.path.exists(tax_path) and st.session_state.tax_data is None:
        try:
            st.session_state.tax_data = pd.read_csv(tax_path)
        except Exception:
            pass

load_saved_data()


def pnl_summary_table(df: pd.DataFrame, include_type: str = None) -> pd.DataFrame:
    """Build full P&L summary with BDT and Contribution Margin (% of Sales)."""
    if include_type:
        data = df[df["type"] == include_type]
    else:
        data = df

    def safe_sum(col):
        if col in data.columns:
            return data[col].sum()
        return 0.0

    total_sales = safe_sum("revenue")
    if total_sales == 0:
        total_sales = 1

    def cm(val):
        return f"{val / total_sales * 100:.2f}%"

    rows = [
        ("Sales / Revenue", safe_sum("revenue"), cm(safe_sum("revenue"))),
        ("Cost of Goods Sold (COGS)", safe_sum("cogs"), cm(safe_sum("cogs"))),
        ("Gross Profit", safe_sum("gross_profit"), cm(safe_sum("gross_profit"))),
        ("", "", ""),
        ("Selling & Distribution (S&D)", "", ""),
        ("  Selling Opex", safe_sum("total_selling_opex"), cm(safe_sum("total_selling_opex"))),
        ("  Marketing Expense", safe_sum("total_marketing"), cm(safe_sum("total_marketing"))),
        ("  Other S&D Cost", safe_sum("total_other_sd"), cm(safe_sum("total_other_sd"))),
        ("Total S&D", safe_sum("total_sd"), cm(safe_sum("total_sd"))),
        ("", "", ""),
        ("Profit after S&D (OP)", safe_sum("profit_after_sd"), cm(safe_sum("profit_after_sd"))),
        ("", "", ""),
        ("Admin & General Expenses", "", ""),
        ("  Salary", safe_sum("total_salary"), cm(safe_sum("total_salary"))),
        ("  Field Visit Cost", safe_sum("total_field_visit"), cm(safe_sum("total_field_visit"))),
        ("  Legal, Subscription & Advisory", safe_sum("total_legal_sub"), cm(safe_sum("total_legal_sub"))),
        ("  Employee Engagement", safe_sum("total_engagement"), cm(safe_sum("total_engagement"))),
        ("  Administrative Cost", safe_sum("total_admin_exp"), cm(safe_sum("total_admin_exp"))),
        ("  General Expenses", safe_sum("total_general"), cm(safe_sum("total_general"))),
        ("  Miscellaneous Expenses", safe_sum("total_misc"), cm(safe_sum("total_misc"))),
        ("Total Admin & General", safe_sum("admin_general"), cm(safe_sum("admin_general"))),
        ("", "", ""),
        ("Other Income", safe_sum("other_income"), cm(safe_sum("other_income"))),
        ("Net Operating Profit", safe_sum("net_operating_profit"), cm(safe_sum("net_operating_profit"))),
        ("", "", ""),
        ("Interest Income", safe_sum("interest_income"), cm(safe_sum("interest_income"))),
        ("Profit before Financing & Tax", safe_sum("profit_before_financing"), cm(safe_sum("profit_before_financing"))),
        ("", "", ""),
        ("Finance Cost", "", ""),
        ("  Crowdfunding Interest", safe_sum("crowdfunding_int"), cm(safe_sum("crowdfunding_int"))),
        ("  Bank/NBFI Interest", safe_sum("bank_int"), cm(safe_sum("bank_int"))),
        ("  Factoring Cost", safe_sum("factoring_cost"), cm(safe_sum("factoring_cost"))),
        ("Total Finance Cost", safe_sum("financing"), cm(safe_sum("financing"))),
        ("", "", ""),
        ("Profit before Tax", safe_sum("profit_before_tax"), cm(safe_sum("profit_before_tax"))),
        ("Tax on Profit", safe_sum("tax"), cm(safe_sum("tax"))),
        ("Net Profit / (Loss)", safe_sum("net_profit"), cm(safe_sum("net_profit"))),
    ]

    result_df = pd.DataFrame(rows, columns=["Line Item", "BDT Amount", "Contribution Margin (% of Sales)"])
    result_df["BDT Amount"] = result_df["BDT Amount"].apply(lambda x: fmt_fin(x) if isinstance(x, (int, float)) and x != "" else x)
    return result_df


# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style="padding: 1rem 0 1.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22L6.66 19.7C7.14 19.87 7.64 20 8 20C19 20 22 3 22 3C21 5 14 5.25 9 6.25C4 7.25 2 11.5 2 13.5C2 15.5 3.75 17.25 3.75 17.25C7 8 17 8 17 8Z" fill="#4CAF50"/>
            </svg>
            <div>
                <h2 style="margin: 0; font-size: 1.3rem; font-weight: 800; color: #ffffff;">iFarmer</h2>
                <p style="margin: 0; font-size: 0.65rem; color: #999999;">Supply Chain P&L Analytics</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- NAVIGATION ---
    st.markdown("**Navigation**", unsafe_allow_html=True)

    page_options = ["Financial Overview", "Transaction P&L", "6-Month Prediction"]
    if st.session_state.wc_data is not None:
        page_options.append("ROIC Analysis")

    current_page = st.radio("Go to", page_options, label_visibility="collapsed", key="nav_page")

    # --- PAGE-SPECIFIC FILTERS ---
    st.markdown("---")
    st.markdown(f"**Filters — {current_page}**", unsafe_allow_html=True)

    # Financial Overview filters
    if current_page == "Financial Overview":
        if st.session_state.fin_data is not None:
            fin_df_filter = pnl_to_dataframe(st.session_state.fin_data)
            fin_months = fin_df_filter["month"].tolist()
            sel_month = st.selectbox("Month", ["All Months"] + fin_months, key="sb_fin_month")
            all_buyers_list = ["All Buyers"]
            if st.session_state.txn_data is not None and "Buyer Name" in st.session_state.txn_data.columns:
                all_buyers_list.extend(sorted(st.session_state.txn_data["Buyer Name"].dropna().unique().tolist()))
            sel_buyer = st.selectbox("Buyer", all_buyers_list, key="sb_fin_buyer")
        else:
            st.info("Upload financial data first.")

    # Transaction P&L filters
    elif current_page == "Transaction P&L":
        if st.session_state.fin_data is not None:
            use_financial = st.checkbox("Auto-allocate from financial data", value=True, key="sb_auto_alloc")
        else:
            use_financial = False

        # Transaction P&L filters
        if st.session_state.txn_data is not None:
            txn = st.session_state.txn_data
            if "Reporting Month" in txn.columns:
                txn_months = sorted(txn["Reporting Month"].dropna().unique().tolist())
            else:
                txn_months = []
            sel_txn_months = st.multiselect("Months", txn_months, default=txn_months, key="sb_txn_months")

            if "Buyer Name" in txn.columns:
                txn_buyers = sorted(txn["Buyer Name"].dropna().unique().tolist())
            else:
                txn_buyers = []
            sel_txn_buyers = st.multiselect("Buyers", txn_buyers, default=txn_buyers, key="sb_txn_buyers")

            # Buyer Group filter
            if "Buyer Name" in txn.columns:
                txn["Buyer_Group_Temp"] = txn["Buyer Name"].apply(extract_parent_buyer)
                txn_groups = sorted(txn["Buyer_Group_Temp"].dropna().unique().tolist())
                txn.drop(columns=["Buyer_Group_Temp"], errors="ignore", inplace=True)
            else:
                txn_groups = []
            sel_txn_groups = st.multiselect("Buyer Groups", txn_groups, default=txn_groups, key="sb_txn_groups")

            # Supplier Name filter
            if "Supplier_Name" in txn.columns:
                txn_suppliers = sorted(txn["Supplier_Name"].dropna().unique().tolist())
            else:
                txn_suppliers = []
            sel_txn_suppliers = st.multiselect("Suppliers", txn_suppliers, default=txn_suppliers, key="sb_txn_suppliers")

        if st.button("Calculate P&L", type="primary", key="sb_calc_pnl"):
            st.session_state["_do_calc_pnl"] = True

    # 6-Month Prediction filters
    elif current_page == "6-Month Prediction":
        if st.session_state.fin_data is not None:
            months_ahead_sb = st.slider("Months to predict", 1, 12, 6, key="sb_months_ahead")

            # Month filter - historical + forecast months
            fin_df_pred = pnl_to_dataframe(st.session_state.fin_data)
            pred_months = fin_df_pred["month"].tolist()

            # Add forecast months if prediction exists
            if st.session_state.prediction_data is not None:
                forecast_months = st.session_state.prediction_data[
                    st.session_state.prediction_data["type"] == "Forecast"
                ]["month"].tolist()
                pred_months = pred_months + forecast_months

            sel_pred_months = st.multiselect("Months", pred_months, default=pred_months, key="sb_pred_months")

            # Buyer filter
            pred_buyers = ["All Buyers"]
            if st.session_state.txn_data is not None and "Buyer Name" in st.session_state.txn_data.columns:
                pred_buyers.extend(sorted(st.session_state.txn_data["Buyer Name"].dropna().unique().tolist()))
            sel_pred_buyer = st.selectbox("Buyer", pred_buyers, key="sb_pred_buyer")

            # P&L Head filter
            all_pnl_heads = ["Revenue", "COGS", "Gross Profit", "Total S&D", "Profit after S&D", "Admin & General", "Finance Cost", "Net Profit"]
            sel_pnl_heads = st.multiselect("P&L Heads", all_pnl_heads, default=all_pnl_heads, key="sb_pred_heads")

            if st.button("Generate Forecast", type="primary", key="sb_gen_forecast"):
                st.session_state["_do_gen_forecast"] = True
        else:
            st.info("Upload financial data first.")

    # ROIC Analysis filters
    elif current_page == "ROIC Analysis":
        roic_months = ["All Months", "Jul'26", "Aug'26", "Sep'26", "Oct'26", "Nov'26", "Dec'26",
                       "Jan'27", "Feb'27", "Mar'27", "Apr'27", "May'27", "Jun'27"]
        roic_month = st.selectbox("Month", roic_months, key="sb_roic_month")


    # --- DATA IMPORT (Admin Only) ---
    if st.session_state.is_admin:
        st.markdown("---")
        st.markdown("**Data Import**", unsafe_allow_html=True)

        # Google Drive Upload Option
        with st.expander("  Import from Google Drive (Paste share link)", expanded=False):
            st.caption("Paste a Google Drive share link and select the file type")
            gdrive_url = st.text_input("Google Drive URL", key="gdrive_url", placeholder="https://drive.google.com/file/d/...")
            gdrive_type = st.selectbox("File Type", ["Transaction CSV", "Financial CSV", "Budget Excel/CSV", "WC Data", "Finance Cost %", "Other"], key="gdrive_type")
            gdrive_name = st.text_input("Save as filename (e.g., budget.csv)", key="gdrive_name", placeholder="budget.csv")

            if st.button("  Download from Google Drive", key="gdrive_download"):
                if gdrive_url and gdrive_name:
                    try:
                        import requests
                        # Extract file ID from Google Drive URL
                        file_id = None
                        if "/file/d/" in gdrive_url:
                            file_id = gdrive_url.split("/file/d/")[1].split("/")[0].split("?")[0]
                        elif "id=" in gdrive_url:
                            file_id = gdrive_url.split("id=")[1].split("&")[0]
                        
                        if file_id:
                            # Create direct download link
                            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                            
                            # Download with session to handle confirmation page
                            session = requests.Session()
                            response = session.get(download_url, stream=True)
                            
                            # Check for virus scan warning (large files)
                            if "confirm=" in response.url or b"virus scan warning" in response.content.lower():
                                for key, value in session.cookies.items():
                                    if key.startswith("download_warning"):
                                        download_url = f"{download_url}&confirm={value}"
                                        response = session.get(download_url, stream=True)
                                        break
                            
                            # Save file
                            save_path = os.path.join(DATA_DIR, gdrive_name)
                            with open(save_path, "wb") as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                            
                            st.success(f"Downloaded: {gdrive_name}")
                            st.info("File saved. Use the appropriate Step below to load it.")
                        else:
                            st.error("Could not extract file ID from URL. Make sure it's a valid Google Drive share link.")
                    except ImportError:
                        st.error("requests library not installed. Run: pip install requests")
                    except Exception as e:
                        st.error(f"Error downloading: {e}")
                else:
                    st.warning("Please enter a URL and filename.")
            
            st.markdown("---")
            st.caption("**Manual alternative:** Download the file from Google Drive first, then upload using the steps below.")

        st.markdown("**Step 1** — Transaction Data")
        txn_file = st.file_uploader("Upload transaction CSV", type=["csv"], key="txn")
        if txn_file:
            try:
                df = pd.read_csv(txn_file)
                is_valid, missing_cols = validate_data(df)
                if is_valid:
                    st.session_state.txn_data = prepare_data(df)
                    save_uploaded_file("txn_data.csv", df)
                    st.success(f"Loaded {len(df)} transactions")
                else:
                    st.error(f"Missing: {', '.join(missing_cols)}")
                    st.write("**Your columns:**")
                    st.code(list(df.columns))
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 2** — Financial Data")
        fin_file = st.file_uploader("Upload financial CSV", type=["csv"], key="fin")
        if fin_file:
            try:
                fin_file.seek(0)
                monthly_pnl = parse_financial_csv(fin_file)
                if monthly_pnl and monthly_pnl.get("months"):
                    st.session_state.fin_data = monthly_pnl
                    import json
                    with open(os.path.join(DATA_DIR, "fin_data.json"), "w") as f:
                        json.dump(monthly_pnl, f)
                    st.success(f"Loaded {len(monthly_pnl['months'])} months: {', '.join(monthly_pnl['months'])}")
                else:
                    st.error("Could not parse financial data. Check CSV format.")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 3** — Working Capital (Optional)")
        col_wc1, col_wc2 = st.columns(2)
        with col_wc1:
            st.caption("Historical WC data (actuals)")
            wc_hist_file = st.file_uploader("Historical Working Capital (CSV/Excel)", type=["csv", "xlsx"], key="wc_hist")
            if wc_hist_file:
                try:
                    if wc_hist_file.name.endswith('.csv'):
                        wc_hist_df = pd.read_csv(wc_hist_file)
                    else:
                        wc_hist_df = pd.read_excel(wc_hist_file)
                    st.session_state.wc_data = wc_hist_df
                    wc_hist_df.to_csv(os.path.join(DATA_DIR, "wc_data.csv"), index=False)
                    st.success(f"Historical WC: {len(wc_hist_df)} rows")
                except Exception as e:
                    st.error(f"Error: {e}")
        with col_wc2:
            st.caption("Budget/planned WC data")
            wc_budget_file = st.file_uploader("Budget Working Capital (CSV/Excel)", type=["csv", "xlsx"], key="wc_budget")
            if wc_budget_file:
                try:
                    if wc_budget_file.name.endswith('.csv'):
                        wc_budget_df = pd.read_csv(wc_budget_file)
                    else:
                        wc_budget_df = pd.read_excel(wc_budget_file)
                    st.session_state.wc_budget_data = wc_budget_df
                    wc_budget_df.to_csv(os.path.join(DATA_DIR, "wc_budget_data.csv"), index=False)
                    st.success(f"Budget WC: {len(wc_budget_df)} rows")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("**Step 4** — Finance Cost % (Optional)")
        st.caption("Upload finance cost % per buyer for accurate allocation")
        col_fin1, col_fin2 = st.columns(2)
        with col_fin1:
            fin_on_file = st.file_uploader("On-Season Finance Cost % (CSV/Excel)", type=["csv", "xlsx"], key="fin_on")
            if fin_on_file:
                try:
                    if fin_on_file.name.endswith('.csv'):
                        fin_on_file.seek(0)
                        lines = fin_on_file.readlines()
                        header_idx = 0
                        for i, line in enumerate(lines):
                            decoded = line.decode('utf-8', errors='ignore')
                            if decoded.strip().startswith('Buyer'):
                                header_idx = i
                                break
                        fin_on_file.seek(0)
                        st.session_state.fin_alloc_on = pd.read_csv(fin_on_file, skiprows=header_idx)
                    else:
                        st.session_state.fin_alloc_on = pd.read_excel(fin_on_file, header=1)
                    st.session_state.fin_alloc_on.to_csv(os.path.join(DATA_DIR, "fin_alloc_on.csv"), index=False)
                    df_on = st.session_state.fin_alloc_on
                    for col in df_on.columns:
                        if '30-day' in str(col).lower() or 'monthly finance' in str(col).lower():
                            st.session_state.fin_on_pct_col = col
                            break
                    st.success(f"On-season: {len(df_on)} buyers")
                except Exception as e:
                    st.error(f"Error: {e}")
        with col_fin2:
            fin_off_file = st.file_uploader("Off-Season Finance Cost % (CSV/Excel)", type=["csv", "xlsx"], key="fin_off")
            if fin_off_file:
                try:
                    if fin_off_file.name.endswith('.csv'):
                        fin_off_file.seek(0)
                        lines = fin_off_file.readlines()
                        header_idx = 0
                        for i, line in enumerate(lines):
                            decoded = line.decode('utf-8', errors='ignore')
                            if decoded.strip().startswith('Buyer'):
                                header_idx = i
                                break
                        fin_off_file.seek(0)
                        st.session_state.fin_alloc_off = pd.read_csv(fin_off_file, skiprows=header_idx)
                    else:
                        st.session_state.fin_alloc_off = pd.read_excel(fin_off_file, header=1)
                    st.session_state.fin_alloc_off.to_csv(os.path.join(DATA_DIR, "fin_alloc_off.csv"), index=False)
                    df_off = st.session_state.fin_alloc_off
                    for col in df_off.columns:
                        if '30-day' in str(col).lower() or 'monthly finance' in str(col).lower():
                            st.session_state.fin_off_pct_col = col
                            break
                    st.success(f"Off-season: {len(df_off)} buyers")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("**Step 5** — Budget File (Optional)")
        st.caption("Upload budget file with monthly revenue targets for FY 2026-27")
        budget_file = st.file_uploader("Upload Budget Excel/CSV", type=["xlsx", "csv"], key="budget_file")
        if budget_file is not None:
            try:
                if budget_file.name.endswith('.csv'):
                    budget_df = pd.read_csv(budget_file)
                else:
                    budget_df = pd.read_excel(budget_file)
                st.session_state.budget_data = budget_df
                budget_df.to_csv(os.path.join(DATA_DIR, "budget_data.csv"), index=False)
                st.success("Budget file uploaded!")
            except Exception as e:
                st.error(f"Error reading budget file: {e}")

        st.markdown("**Step 6** — Buyer-Wise Budget (Optional)")
        st.caption("Monthly revenue/cost targets split by buyer")
        buyer_budget_file = st.file_uploader("Upload Buyer-Wise Budget (CSV/Excel)", type=["csv", "xlsx"], key="buyer_budget_file")
        if buyer_budget_file is not None:
            try:
                if buyer_budget_file.name.endswith('.csv'):
                    buyer_budget_df = pd.read_csv(buyer_budget_file)
                else:
                    buyer_budget_df = pd.read_excel(buyer_budget_file)
                st.session_state.buyer_budget_data = buyer_budget_df
                buyer_budget_df.to_csv(os.path.join(DATA_DIR, "buyer_budget_data.csv"), index=False)
                st.success(f"Buyer budget: {len(buyer_budget_df)} rows, {len(buyer_budget_df.columns)} columns")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 7** — Buyer-Wise Actuals (Optional)")
        st.caption("Actual revenue/cost data split by buyer for comparison")
        buyer_actuals_file = st.file_uploader("Upload Buyer-Wise Actuals (CSV/Excel)", type=["csv", "xlsx"], key="buyer_actuals_file")
        if buyer_actuals_file is not None:
            try:
                if buyer_actuals_file.name.endswith('.csv'):
                    buyer_actuals_df = pd.read_csv(buyer_actuals_file)
                else:
                    buyer_actuals_df = pd.read_excel(buyer_actuals_file)
                st.session_state.buyer_actuals_data = buyer_actuals_df
                buyer_actuals_df.to_csv(os.path.join(DATA_DIR, "buyer_actuals_data.csv"), index=False)
                st.success(f"Buyer actuals: {len(buyer_actuals_df)} rows")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 8** — Supplier-Wise Budget (Optional)")
        st.caption("Monthly procurement targets split by supplier")
        supplier_budget_file = st.file_uploader("Upload Supplier-Wise Budget (CSV/Excel)", type=["csv", "xlsx"], key="supplier_budget_file")
        if supplier_budget_file is not None:
            try:
                if supplier_budget_file.name.endswith('.csv'):
                    supplier_budget_df = pd.read_csv(supplier_budget_file)
                else:
                    supplier_budget_df = pd.read_excel(supplier_budget_file)
                st.session_state.supplier_budget_data = supplier_budget_df
                supplier_budget_df.to_csv(os.path.join(DATA_DIR, "supplier_budget_data.csv"), index=False)
                st.success(f"Supplier budget: {len(supplier_budget_df)} rows")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 9** — Supplier-Wise Actuals (Optional)")
        st.caption("Actual procurement data split by supplier for comparison")
        supplier_actuals_file = st.file_uploader("Upload Supplier-Wise Actuals (CSV/Excel)", type=["csv", "xlsx"], key="supplier_actuals_file")
        if supplier_actuals_file is not None:
            try:
                if supplier_actuals_file.name.endswith('.csv'):
                    supplier_actuals_df = pd.read_csv(supplier_actuals_file)
                else:
                    supplier_actuals_df = pd.read_excel(supplier_actuals_file)
                st.session_state.supplier_actuals_data = supplier_actuals_df
                supplier_actuals_df.to_csv(os.path.join(DATA_DIR, "supplier_actuals_data.csv"), index=False)
                st.success(f"Supplier actuals: {len(supplier_actuals_df)} rows")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 10** — Salary/Payroll Data (Optional)")
        st.caption("Detailed salary breakdown by department/employee")
        salary_file = st.file_uploader("Upload Salary Data (CSV/Excel)", type=["csv", "xlsx"], key="salary_file")
        if salary_file is not None:
            try:
                if salary_file.name.endswith('.csv'):
                    salary_df = pd.read_csv(salary_file)
                else:
                    salary_df = pd.read_excel(salary_file)
                st.session_state.salary_data = salary_df
                salary_df.to_csv(os.path.join(DATA_DIR, "salary_data.csv"), index=False)
                st.success(f"Salary data: {len(salary_df)} rows, {len(salary_df.columns)} columns")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 11** — Inventory Data (Optional)")
        st.caption("Stock levels, turnover, and warehouse data")
        inventory_file = st.file_uploader("Upload Inventory Data (CSV/Excel)", type=["csv", "xlsx"], key="inventory_file")
        if inventory_file is not None:
            try:
                if inventory_file.name.endswith('.csv'):
                    inventory_df = pd.read_csv(inventory_file)
                else:
                    inventory_df = pd.read_excel(inventory_file)
                st.session_state.inventory_data = inventory_df
                inventory_df.to_csv(os.path.join(DATA_DIR, "inventory_data.csv"), index=False)
                st.success(f"Inventory data: {len(inventory_df)} rows")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 12** — Previous Year Data (Optional)")
        st.caption("Last year P&L for year-over-year comparison")
        prev_year_file = st.file_uploader("Upload Previous Year P&L (CSV)", type=["csv"], key="prev_year_file")
        if prev_year_file is not None:
            try:
                prev_year_file.seek(0)
                monthly_pnl_prev = parse_financial_csv(prev_year_file)
                if monthly_pnl_prev and monthly_pnl_prev.get("months"):
                    st.session_state.prev_year_data = monthly_pnl_prev
                    import json
                    with open(os.path.join(DATA_DIR, "prev_year_data.json"), "w") as f:
                        json.dump(monthly_pnl_prev, f)
                    st.success(f"Previous year: {len(monthly_pnl_prev['months'])} months loaded")
                else:
                    st.error("Could not parse previous year data.")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("**Step 13** — Tax Data (Optional)")
        st.caption("Tax rates and deductions for accurate net profit calculation")
        tax_file = st.file_uploader("Upload Tax Data (CSV/Excel)", type=["csv", "xlsx"], key="tax_file")
        if tax_file is not None:
            try:
                if tax_file.name.endswith('.csv'):
                    tax_df = pd.read_csv(tax_file)
                else:
                    tax_df = pd.read_excel(tax_file)
                st.session_state.tax_data = tax_df
                tax_df.to_csv(os.path.join(DATA_DIR, "tax_data.csv"), index=False)
                st.success(f"Tax data: {len(tax_df)} rows")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.markdown("---")
        st.info("  View-only mode. Contact admin to upload data.")

    # Logout button
    st.markdown("---")
    if st.button("  Logout", key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.is_admin = False
        st.rerun()

    # Admin: Delete saved data
    if st.session_state.is_admin:
        with st.expander("  Admin: Manage Saved Data"):
            saved_files = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
            if saved_files:
                for f in saved_files:
                    col_name, col_btn = st.columns([3, 1])
                    with col_name:
                        st.caption(f)
                    with col_btn:
                        if st.button(" ️", key=f"del_{f}"):
                            os.remove(os.path.join(DATA_DIR, f))
                            st.rerun()
                if st.button("  Delete All Saved Data", type="primary"):
                    for f in saved_files:
                        os.remove(os.path.join(DATA_DIR, f))
                    st.rerun()
            else:
                st.caption("No saved data found.")

    # Download Report
    if st.session_state.txn_data is not None or st.session_state.fin_data is not None:
        html_report = generate_html_report()
        st.download_button(
            label="📥 Download HTML Report",
            data=html_report,
            file_name="ifarmer_pnl_report.html",
            mime="text/html",
            key="download_report",
        )


# --- MAIN CONTENT ---
if st.session_state.txn_data is not None or st.session_state.fin_data is not None:

    # --- PAGE: FINANCIAL OVERVIEW ---
    if current_page == "Financial Overview":
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;"> </span>
            <h2 style="margin: 0;">Financial Overview</h2>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.fin_data is not None:
            try:
                fin_df = pnl_to_dataframe(st.session_state.fin_data)
                months = fin_df["month"].tolist()

                selected_month = sel_month

                # Buyer filter (from sidebar)
                selected_buyer = sel_buyer

                # Use company-wide financial data
                if selected_month != "All Months":
                    vis_df = fin_df[fin_df["month"] == selected_month].copy()
                else:
                    vis_df = fin_df.copy()

                # If buyer is selected, allocate costs based on buyer's sales share
                if selected_buyer != "All Buyers" and st.session_state.txn_data is not None:
                    txn_df = st.session_state.txn_data
                    if "Reporting Month" in txn_df.columns and "Buyer Name" in txn_df.columns:
                        # Calculate buyer's sales share per month
                        for idx, row in vis_df.iterrows():
                            month = row["month"]
                            # Get buyer's sales for this month
                            month_norm = normalize_month(str(month))
                            month_txn = txn_df[txn_df["Reporting Month"].apply(lambda x: normalize_month(str(x))) == month_norm]
                            buyer_month_sales = month_txn[month_txn["Buyer Name"] == selected_buyer]["Sales/Revenue"].sum()
                            total_month_sales = month_txn["Sales/Revenue"].sum()

                            if total_month_sales > 0:
                                share = buyer_month_sales / total_month_sales
                            else:
                                share = 0

                            # Allocate all P&L lines by buyer's sales share
                            for col in vis_df.columns:
                                if col != "month":
                                    vis_df.at[idx, col] = row[col] * share

                # Ensure numeric types
                for col in ["revenue", "cogs", "gross_profit", "total_sd", "admin_general", "financing", "net_profit"]:
                    if col in vis_df.columns:
                        vis_df[col] = pd.to_numeric(vis_df[col], errors="coerce").fillna(0)

                def safe_float(val):
                    try:
                        return float(val) if val else 0.0
                    except (ValueError, TypeError):
                        return 0.0

                def pct_str(val, rev):
                    v = safe_float(val)
                    r = safe_float(rev)
                    return f"{v/r*100:.1f}%" if r else "0%"

                # ── KPIs AT THE TOP ──
                # First define current month values
                if selected_month != "All Months":
                    sel_row = vis_df.iloc[0] if not vis_df.empty else fin_df[fin_df["month"] == selected_month].iloc[0]
                    rev = safe_float(sel_row.get("revenue", 0))
                    cogs = safe_float(sel_row.get("cogs", 0))
                    gp = safe_float(sel_row.get("gross_profit", 0))
                    total_sd = safe_float(sel_row.get("total_sd", 0))
                    admin = safe_float(sel_row.get("admin_general", 0))
                    financing = safe_float(sel_row.get("financing", 0))
                    np_val = safe_float(sel_row.get("net_profit", 0))
                    cm3 = gp - total_sd
                    cm6 = cm3 - admin
                else:
                    rev = vis_df["revenue"].sum()
                    cogs = vis_df["cogs"].sum()
                    gp = vis_df["gross_profit"].sum()
                    total_sd = vis_df["total_sd"].sum()
                    admin = vis_df["admin_general"].sum()
                    financing = vis_df["financing"].sum()
                    np_val = vis_df["net_profit"].sum()
                    cm3 = gp - total_sd
                    cm6 = cm3 - admin

                # Calculate MoM growth using current values
                mom_growth = {}
                if selected_month != "All Months" and selected_month in months:
                    month_idx = months.index(selected_month)
                    if month_idx > 0:
                        prev_month = months[month_idx - 1]
                        prev_row = fin_df[fin_df["month"] == prev_month]
                        if not prev_row.empty:
                            prev_row = prev_row.iloc[0]
                            prev_rev = safe_float(prev_row.get("revenue", 0))
                            prev_cogs = safe_float(prev_row.get("cogs", 0))
                            prev_gp = safe_float(prev_row.get("gross_profit", 0))
                            prev_sd = safe_float(prev_row.get("total_sd", 0))
                            prev_admin = safe_float(prev_row.get("admin_general", 0))
                            prev_fin = safe_float(prev_row.get("financing", 0))
                            prev_np = safe_float(prev_row.get("net_profit", 0))
                            prev_cm3 = prev_gp - prev_sd
                            prev_cm6 = prev_cm3 - prev_admin

                            def calc_mom(curr, prev):
                                if prev == 0:
                                    return None
                                return ((curr - prev) / abs(prev)) * 100

                            mom_growth = {
                                "revenue": calc_mom(rev, prev_rev),
                                "cogs": calc_mom(cogs, prev_cogs),
                                "gp": calc_mom(gp, prev_gp),
                                "sd": calc_mom(total_sd, prev_sd),
                                "cm3": calc_mom(cm3, prev_cm3),
                                "admin": calc_mom(admin, prev_admin),
                                "cm6": calc_mom(cm6, prev_cm6),
                                "fin": calc_mom(financing, prev_fin),
                                "np": calc_mom(np_val, prev_np),
                            }

                def mom_label(val, is_cost=False):
                    if val is None:
                        return "&nbsp;", "#999"
                    arrow = "↑" if val >= 0 else "↓"
                    # For costs: increase is bad (red), decrease is good (green)
                    # For revenue/profit: increase is good (green), decrease is bad (red)
                    if is_cost:
                        color = "#c62828" if val >= 0 else "#2e7d32"
                    else:
                        color = "#2e7d32" if val >= 0 else "#c62828"
                    return f"{arrow} {abs(val):.1f}%", color

                header = f"**{selected_month}**" if selected_month != "All Months" else "**All Months (FY 2025-26)**"
                if selected_buyer != "All Buyers":
                    header += f" — {selected_buyer}"
                st.markdown(header)

                def pct_label(val, rev):
                    return f"{val/rev*100:.1f}%" if rev else "0%"

                kpi_row1_c1, kpi_row1_c2, kpi_row1_c3, kpi_row1_c4 = st.columns(4)
                with kpi_row1_c1:
                    rev_mom, rev_mom_color = mom_label(mom_growth.get("revenue"), is_cost=False)
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">REVENUE</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(rev)}</div>
                        <div style="font-size:0.75rem;color:{rev_mom_color};font-weight:600;">{rev_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)
                with kpi_row1_c2:
                    cogs_mom, cogs_mom_color = mom_label(mom_growth.get("cogs"), is_cost=True)
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">COGS</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(cogs)}</div>
                        <div style="font-size:0.75rem;color:{cogs_mom_color};font-weight:600;">{pct_label(cogs, rev)} | {cogs_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)
                with kpi_row1_c3:
                    gp_mom, gp_mom_color = mom_label(mom_growth.get("gp"), is_cost=False)
                    gp_color = "#2e7d32" if gp >= 0 else "#c62828"
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">GROSS PROFIT</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(gp)}</div>
                        <div style="font-size:0.75rem;color:{gp_mom_color};font-weight:600;">{pct_label(gp, rev)} | {gp_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)
                with kpi_row1_c4:
                    sd_mom, sd_mom_color = mom_label(mom_growth.get("sd"), is_cost=True)
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">TOTAL S&amp;D</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(total_sd)}</div>
                        <div style="font-size:0.75rem;color:{sd_mom_color};font-weight:600;">{pct_label(total_sd, rev)} | {sd_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)

                kpi_row2_c1, kpi_row2_c2, kpi_row2_c3, kpi_row2_c4 = st.columns(4)
                with kpi_row2_c1:
                    cm3_mom, cm3_mom_color = mom_label(mom_growth.get("cm3"), is_cost=False)
                    cm3_color = "#2e7d32" if cm3 >= 0 else "#c62828"
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">PROFIT AFTER S&amp;D</div>
                        <div style="font-size:1.5rem;font-weight:800;color:{cm3_color};letter-spacing:-0.5px;">{fmt_crore(cm3)}</div>
                        <div style="font-size:0.75rem;color:{cm3_mom_color};font-weight:600;">{pct_label(cm3, rev)} | {cm3_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)
                with kpi_row2_c2:
                    admin_mom, admin_mom_color = mom_label(mom_growth.get("admin"), is_cost=True)
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">ADMIN &amp; GENERAL</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(admin)}</div>
                        <div style="font-size:0.75rem;color:{admin_mom_color};font-weight:600;">{pct_label(admin, rev)} | {admin_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)
                with kpi_row2_c3:
                    cm6_mom, cm6_mom_color = mom_label(mom_growth.get("cm6"), is_cost=False)
                    cm6_color = "#2e7d32" if cm6 >= 0 else "#c62828"
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">NET OPERATING PROFIT</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(cm6)}</div>
                        <div style="font-size:0.75rem;color:{cm6_mom_color};font-weight:600;">{pct_label(cm6, rev)} | {cm6_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)
                with kpi_row2_c4:
                    fin_mom, fin_mom_color = mom_label(mom_growth.get("fin"), is_cost=True)
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">FINANCE COST</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;">{fmt_crore(financing)}</div>
                        <div style="font-size:0.75rem;color:{fin_mom_color};font-weight:600;">{pct_label(financing, rev)} | {fin_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)

                kpi_row3_c1, kpi_row3_c2 = st.columns(2)
                with kpi_row3_c1:
                    np_mom, np_mom_color = mom_label(mom_growth.get("np"), is_cost=False)
                    np_color = "#2e7d32" if np_val >= 0 else "#c62828"
                    st.markdown(f"""<div style="background:#ffffff;border:none;border-radius:12px;padding:1.2rem 1.4rem;min-height:130px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-size:0.65rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;">NET PROFIT</div>
                        <div style="font-size:1.5rem;font-weight:800;color:{np_color};letter-spacing:-0.5px;">{fmt_crore(np_val)}</div>
                        <div style="font-size:0.75rem;color:{np_mom_color};font-weight:600;">{pct_label(np_val, rev)} | {np_mom} MoM</div>
                    </div>""", unsafe_allow_html=True)

                st.markdown("---")

                # ── P&L SUMMARY TABLE ──
                if selected_month != "All Months":
                    summary_data = [
                        ("Sales / Revenue", fmt_crore(rev), pct_str(rev, rev)),
                        ("Cost of Goods Sold (COGS)", fmt_crore(safe_float(sel_row.get("cogs", 0))), pct_str(sel_row.get("cogs", 0), rev)),
                        ("Gross Profit", fmt_crore(gp), pct_str(gp, rev)),
                        ("", "", ""),
                        ("Total S&D", fmt_crore(total_sd), pct_str(total_sd, rev)),
                        ("Profit after S&D (CM3)", fmt_crore(cm3), pct_str(cm3, rev)),
                        ("", "", ""),
                        ("Total Admin & General", fmt_crore(admin), pct_str(admin, rev)),
                        ("Net Operating Profit (CM6)", fmt_crore(cm6), pct_str(cm6, rev)),
                        ("", "", ""),
                        ("Finance Cost", fmt_crore(financing), pct_str(financing, rev)),
                        ("Net Profit / (Loss)", fmt_crore(np_val), pct_str(np_val, rev)),
                    ]
                    summary_df = pd.DataFrame(summary_data, columns=["Line Item", "Amount (Cr)", "% of Sales"])
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                else:
                    summary_tbl = pnl_summary_table(vis_df)
                    st.dataframe(summary_tbl, use_container_width=True, hide_index=True)

                # ── CHARTS ROW ──
                vis_df["GP%"] = np.where(vis_df["revenue"] != 0, vis_df["gross_profit"] / vis_df["revenue"] * 100, 0)
                vis_df["cogs%"] = np.where(vis_df["revenue"] != 0, vis_df["cogs"] / vis_df["revenue"] * 100, 0)
                vis_df["sd%"] = np.where(vis_df["revenue"] != 0, vis_df["total_sd"] / vis_df["revenue"] * 100, 0)
                vis_df["S&D%"] = np.where(vis_df["revenue"] != 0, -vis_df["total_sd"] / vis_df["revenue"] * 100, 0)
                vis_df["CM3%"] = np.where(vis_df["revenue"] != 0, (vis_df["gross_profit"] - vis_df["total_sd"]) / vis_df["revenue"] * 100, 0)
                vis_df["cm3"] = vis_df["gross_profit"] - vis_df["total_sd"]
                vis_df["admin%"] = np.where(vis_df["revenue"] != 0, vis_df["admin_general"] / vis_df["revenue"] * 100, 0)
                vis_df["Admin%"] = np.where(vis_df["revenue"] != 0, -vis_df["admin_general"] / vis_df["revenue"] * 100, 0)
                vis_df["fin%"] = np.where(vis_df["revenue"] != 0, vis_df["financing"] / vis_df["revenue"] * 100, 0)
                vis_df["Finance%"] = np.where(vis_df["revenue"] != 0, -vis_df["financing"] / vis_df["revenue"] * 100, 0)
                vis_df["np%"] = np.where(vis_df["revenue"] != 0, vis_df["net_profit"] / vis_df["revenue"] * 100, 0)
                vis_df["NP%"] = vis_df["np%"]

                st.markdown("### P&L Waterfall")

                all_heads = ["COGS", "S&D", "Profit after S&D", "Admin", "Finance", "Net Profit"]
                selected_heads = st.multiselect("Filter P&L Heads", all_heads, default=all_heads, key="pnl_head_filter")

                def _pct_amt(pct, amt):
                    return f"{pct:.1f}% | {fmt_crore(amt)}"

                fig_wf = go.Figure()
                head_config = [
                    ("COGS", "cogs%", "cogs", "#f44336"),
                    ("S&D", "sd%", "total_sd", "#FF9800"),
                    ("Profit after S&D", "CM3%", "cm3", "#2196F3"),
                    ("Admin", "admin%", "admin_general", "#9C27B0"),
                    ("Finance", "fin%", "financing", "#607D8B"),
                    ("Net Profit", "np%", "net_profit", "#00BCD4"),
                ]
                for head_name, pct_col, amt_col, color in head_config:
                    if head_name in selected_heads:
                        fig_wf.add_trace(go.Bar(
                            x=vis_df["month"], y=vis_df[pct_col].tolist(), name=head_name,
                            customdata=[_pct_amt(p, a) for p, a in zip(vis_df[pct_col], vis_df[amt_col])],
                            hovertemplate=f"<b>%{{x}}</b><br>{head_name}: %{{customdata}}<extra></extra>",
                            marker_color=color,
                        ))

                # Trendlines
                fig_wf.add_trace(go.Scatter(
                    x=vis_df["month"], y=vis_df["np%"], name="Net Profit %",
                    mode="lines+markers", line=dict(color="#009688", width=2, dash="dot"),
                    marker=dict(size=6),
                    hovertemplate="<b>%{x}</b><br>Net Profit: %{y:.1f}%<extra></extra>",
                ))
                fig_wf.add_trace(go.Scatter(
                    x=vis_df["month"], y=vis_df["CM3%"], name="Profit after S&D %",
                    mode="lines+markers", line=dict(color="#FF5722", width=2, dash="dash"),
                    marker=dict(size=6),
                    hovertemplate="<b>%{x}</b><br>Profit after S&D: %{y:.1f}%<extra></extra>",
                ))

                fig_wf.update_layout(
                    height=550, barmode="stack",
                    title=dict(text="P&L Waterfall — % of Sales & Amounts (Cr BDT)", font=dict(size=13, color="#1a1a1a")),
                    yaxis=dict(title="% of Sales", side="left", showgrid=False, tickfont=dict(color="#1a1a1a"), title_font=dict(color="#1a1a1a")),
                    yaxis2=dict(title="% of Sales (Trend)", overlaying="y", side="right", showgrid=False, tickfont=dict(color="#1a1a1a"), title_font=dict(color="#1a1a1a")),
                    xaxis=dict(title="Month", tickfont=dict(color="#1a1a1a"), title_font=dict(color="#1a1a1a")),
                    legend=dict(
                        orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5,
                        font=dict(size=10, color="#1a1a1a"),
                        traceorder="normal", itemwidth=30,
                    ),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#1a1a1a"),
                    margin=dict(l=50, r=50, t=50, b=120),
                )
                st.plotly_chart(fig_wf, use_container_width=True)

            except Exception as e:
                st.error(f"Error processing financial data: {e}")
                st.info("Please re-upload the financial CSV file.")
        else:
            st.info("Upload financial data to see overview.")

    # --- PAGE: TRANSACTION P&L ---
    elif current_page == "Transaction P&L":
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;"> </span>
            <h2 style="margin: 0;">Transaction-Level P&L</h2>
        </div>
        <p style="color: #78909c; margin-top: -0.5rem; margin-bottom: 1.5rem;">
            Row-level profit & loss calculation with cost allocation
        </p>
        """, unsafe_allow_html=True)

        if st.session_state.txn_data is not None:
            df = st.session_state.txn_data.copy()

            # Apply filters from sidebar
            sel_txn_months = st.session_state.get("sb_txn_months", [])
            sel_txn_buyers = st.session_state.get("sb_txn_buyers", [])
            sel_txn_groups = st.session_state.get("sb_txn_groups", [])
            sel_txn_suppliers = st.session_state.get("sb_txn_suppliers", [])

            if "Reporting Month" in df.columns and sel_txn_months:
                df = df[df["Reporting Month"].isin(sel_txn_months)]
            if "Buyer Name" in df.columns:
                if sel_txn_buyers:
                    df = df[df["Buyer Name"].isin(sel_txn_buyers)]
                # Apply buyer group filter
                if sel_txn_groups:
                    df["_buyer_group_tmp"] = df["Buyer Name"].apply(extract_parent_buyer)
                    df = df[df["_buyer_group_tmp"].isin(sel_txn_groups)]
                    df.drop(columns=["_buyer_group_tmp"], errors="ignore", inplace=True)
            if "Supplier_Name" in df.columns and sel_txn_suppliers:
                df = df[df["Supplier_Name"].isin(sel_txn_suppliers)]

            if "Buyer Name" in df.columns:
                all_buyers = sorted(df["Buyer Name"].dropna().unique().tolist())
            else:
                all_buyers = []

            if "Reporting Month" in df.columns:
                all_months = sorted(df["Reporting Month"].dropna().unique().tolist())
            else:
                all_months = []

            # Auto-allocate from sidebar
            use_financial = st.session_state.get("sb_auto_alloc", False)

            month_buyer_costs = {}
            if use_financial and st.session_state.fin_data is not None:
                try:
                    month_buyer_costs = allocate_costs_by_month_buyer(
                        st.session_state.fin_data, df,
                        fin_alloc_on=st.session_state.fin_alloc_on,
                        fin_alloc_off=st.session_state.fin_alloc_off
                    )

                    st.write("**Cost Allocation by Month & Buyer:**")
                    alloc_rows = []
                    for m, buyers in month_buyer_costs.items():
                        m_norm = normalize_month(str(m))
                        for b, costs in buyers.items():
                            # Get buyer-month sales for admin % calculation
                            bm_sales = df[
                                (df["Reporting Month"].apply(lambda x: normalize_month(str(x))) == m_norm) &
                                (df["Buyer Name"] == b)
                            ]["Sales/Revenue"].sum()
                            admin_pct = (costs["admin_general"] / bm_sales * 100) if bm_sales > 0 else 0
                            alloc_rows.append({
                                "Month": m,
                                "Buyer": b,
                                "Season": costs.get("season", ""),
                                "Sales Share": f"{costs['sales_share']*100:.1f}%",
                                "Admin": fmt_fin(costs["admin_general"]),
                                "Admin %": f"{admin_pct:.1f}%",
                                "Finance %": f"{costs.get('finance_pct', 0)*100:.2f}%",
                                "Finance": fmt_fin(costs["financing"]),
                            })
                    if alloc_rows:
                        st.dataframe(pd.DataFrame(alloc_rows), use_container_width=True)
                except Exception as e:
                    st.error(f"Error allocating costs: {e}")
            elif all_buyers:
                st.info("Upload financial data for auto-allocation.")

            # Calculate P&L (triggered from sidebar or always from filtered df)
            if st.session_state.get("_do_calc_pnl"):
                if not month_buyer_costs and st.session_state.fin_data is not None:
                    try:
                        month_buyer_costs = allocate_costs_by_month_buyer(
                            st.session_state.fin_data, df,
                            fin_alloc_on=st.session_state.fin_alloc_on,
                            fin_alloc_off=st.session_state.fin_alloc_off
                        )
                    except Exception:
                        pass
                st.session_state["_do_calc_pnl"] = False

            # Always calculate from current filtered df
            pnl_df = calculate_row_level_pnl(df, month_buyer_costs)
            st.session_state.pnl_data = pnl_df

            if st.session_state.pnl_data is not None:
                pnl_df = st.session_state.pnl_data

                st.markdown("---")
                st.markdown("""
                <div class="section-header">
                    <span style="font-size: 1.3rem;"> </span>
                    <h3 style="margin: 0;">Row-Level P&L</h3>
                </div>
                """, unsafe_allow_html=True)

                def cm(val, sales):
                    """Contribution margin: % of sales."""
                    if sales and sales != 0:
                        return f"{val / sales * 100:.1f}%"
                    return "0.0%"

                def amt(val):
                    """Format amount."""
                    return fmt_fin(val)

                # Build formatted display
                pnl_display = pd.DataFrame({
                    "Month": pnl_df["Reporting Month"],
                    "Buyer": pnl_df["Buyer Name"],
                    "Sales": pnl_df["Sales/Revenue"].apply(amt),
                    "COGS": pnl_df["Cogs"].apply(amt),
                    "COGS %": [cm(v, s) for v, s in zip(pnl_df["Cogs"], pnl_df["Sales/Revenue"])],
                    "GP": pnl_df["GP"].apply(amt),
                    "GP %": [cm(v, s) for v, s in zip(pnl_df["GP"], pnl_df["Sales/Revenue"])],
                    "S&D": pnl_df["Total Selling Opex(F)"].apply(amt),
                    "S&D %": [cm(v, s) for v, s in zip(pnl_df["Total Selling Opex(F)"], pnl_df["Sales/Revenue"])],
                    "Profit after S&D": pnl_df["Profit_After_SD"].apply(amt),
                    "CM3 %": [cm(v, s) for v, s in zip(pnl_df["Profit_After_SD"], pnl_df["Sales/Revenue"])],
                    "Admin": pnl_df["Admin_Expense"].apply(amt),
                    "Admin %": [cm(v, s) for v, s in zip(pnl_df["Admin_Expense"], pnl_df["Sales/Revenue"])],
                    "Net Oper. Profit": pnl_df["Net_Operating_Profit"].apply(amt),
                    "NOP %": [cm(v, s) for v, s in zip(pnl_df["Net_Operating_Profit"], pnl_df["Sales/Revenue"])],
                    "Finance": pnl_df["Finance_Cost"].apply(amt),
                    "Fin. %": [cm(v, s) for v, s in zip(pnl_df["Finance_Cost"], pnl_df["Sales/Revenue"])],
                    "Net Profit": pnl_df["Net_Profit"].apply(amt),
                    "NP %": [cm(v, s) for v, s in zip(pnl_df["Net_Profit"], pnl_df["Sales/Revenue"])],
                })

                # Add supplier info if available in source data
                if "Supplier_Name" in df.columns or "Supplier_Location" in df.columns:
                    month_col = "Reporting Month" if "Reporting Month" in df.columns else "Reporting_Month"
                    buyer_col = "Buyer Name" if "Buyer Name" in df.columns else "Buyer_Name"
                    supplier_map = df.groupby([buyer_col, month_col]).agg(
                        **({} if "Supplier_Name" not in df.columns else {"Supplier Name": ("Supplier_Name", "first")}),
                        **({} if "Supplier_Location" not in df.columns else {"Supplier Location": ("Supplier_Location", "first")}),
                    ).reset_index()
                    pnl_display = pnl_display.merge(
                        supplier_map[[buyer_col, month_col] + [c for c in ["Supplier Name", "Supplier Location"] if c in supplier_map.columns]],
                        left_on=["Buyer", "Month"],
                        right_on=[buyer_col, month_col],
                        how="left"
                    )
                    for col in ["Supplier Name", "Supplier Location"]:
                        if col in pnl_display.columns:
                            cols = pnl_display.columns.tolist()
                            cols.insert(cols.index("Buyer") + 1, cols.pop(cols.index(col)))
                            pnl_display = pnl_display[cols]
                    pnl_display = pnl_display.drop(columns=[buyer_col, month_col], errors="ignore")

                st.dataframe(pnl_display, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("""
                <div class="section-header">
                    <span style="font-size: 1.3rem;"> </span>
                    <h3 style="margin: 0;">P&L Summary</h3>
                </div>
                """, unsafe_allow_html=True)
                summary = generate_pnl_summary(pnl_df)
                total_sales = summary["Total Sales"]
                summary_rows = [
                    ("Sales", summary["Total Sales"]),
                    ("COGS", summary["Total COGS"]),
                    ("Gross Profit", summary["Gross Profit"]),
                    ("S&D (Selling Opex)", summary["Total Selling Opex"]),
                    ("Profit After S&D", summary["Profit After S&D"]),
                    ("Admin & General Expense", summary["Total Admin Expense"]),
                    ("Net Operating Profit", summary["Net Operating Profit"]),
                    ("Finance Cost", summary["Total Finance Cost"]),
                    ("Net Profit", summary["Net Profit"]),
                ]
                summary_df = pd.DataFrame(summary_rows, columns=["Line Item", "Amount"])
                summary_df["Amount"] = summary_df["Amount"].apply(fmt_txn)
                summary_df["Contribution Margin"] = [
                    f"{v / total_sales * 100:.1f}%" if total_sales and total_sales != 0 else "0.0%"
                    for _, v in summary_rows
                ]
                st.table(summary_df)

                st.markdown("---")
                st.markdown("""
                <div class="section-header">
                    <span style="font-size: 1.3rem;"> </span>
                    <h3 style="margin: 0;">Buyer-Level Summary</h3>
                </div>
                """, unsafe_allow_html=True)
                buyer_summary = generate_buyer_summary(pnl_df)

                buyer_profit = buyer_summary[["Buyer Name", "Sales", "GP", "Profit_After_SD", "Net_Profit"]].copy()
                buyer_profit.columns = ["Buyer", "Sales", "Gross Profit", "Profit after S&D", "Net Profit"]
                total_sales_b = buyer_profit["Sales"].sum()
                buyer_profit["Sales %"] = buyer_profit["Sales"].apply(lambda x: f"{x / total_sales_b * 100:.1f}%" if total_sales_b else "0.0%")
                buyer_profit["GP %"] = buyer_profit.apply(lambda r: f"{r['Gross Profit'] / r['Sales'] * 100:.1f}%" if r["Sales"] else "0.0%", axis=1)
                buyer_profit["CM3 %"] = buyer_profit.apply(lambda r: f"{r['Profit after S&D'] / r['Sales'] * 100:.1f}%" if r["Sales"] else "0.0%", axis=1)
                buyer_profit["NP %"] = buyer_profit.apply(lambda r: f"{r['Net Profit'] / r['Sales'] * 100:.1f}%" if r["Sales"] else "0.0%", axis=1)
                for col in ["Sales", "Gross Profit", "Profit after S&D", "Net Profit"]:
                    buyer_profit[col] = buyer_profit[col].apply(fmt_txn)
                st.dataframe(buyer_profit, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("""
                <div class="section-header">
                    <span style="font-size: 1.3rem;"> </span>
                    <h3 style="margin: 0;">Buyer Group Summary</h3>
                </div>
                """, unsafe_allow_html=True)
                buyer_grouped = buyer_summary.copy()
                buyer_grouped["Buyer Group"] = buyer_grouped["Buyer Name"].apply(extract_parent_buyer)
                group_summary = buyer_grouped.groupby("Buyer Group").agg(
                    Sales=("Sales", "sum"),
                    GP=("GP", "sum"),
                    Profit_after_SD=("Profit_After_SD", "sum"),
                    Net_Profit=("Net_Profit", "sum"),
                ).reset_index()
                total_sales_g = group_summary["Sales"].sum()
                group_summary["Sales %"] = group_summary["Sales"].apply(lambda x: f"{x / total_sales_g * 100:.1f}%" if total_sales_g else "0.0%")
                group_summary["GP %"] = group_summary.apply(lambda r: f"{r['GP'] / r['Sales'] * 100:.1f}%" if r["Sales"] else "0.0%", axis=1)
                group_summary["CM3 %"] = group_summary.apply(lambda r: f"{r['Profit_after_SD'] / r['Sales'] * 100:.1f}%" if r["Sales"] else "0.0%", axis=1)
                group_summary["NP %"] = group_summary.apply(lambda r: f"{r['Net_Profit'] / r['Sales'] * 100:.1f}%" if r["Sales"] else "0.0%", axis=1)
                for col in ["Sales", "GP", "Profit_after_SD", "Net_Profit"]:
                    group_summary[col] = group_summary[col].apply(fmt_txn)
                group_summary.columns = ["Buyer Group", "Sales", "Gross Profit", "Profit after S&D", "Net Profit", "Sales %", "GP %", "CM3 %", "NP %"]
                st.dataframe(group_summary, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("""
                <div class="section-header">
                    <span style="font-size: 1.3rem;"> </span>
                    <h3 style="margin: 0;">Sales Concentration by Buyer Group</h3>
                </div>
                """, unsafe_allow_html=True)
                buyer_group_sales = buyer_summary.copy()
                buyer_group_sales["Buyer Group"] = buyer_group_sales["Buyer Name"].apply(extract_parent_buyer)
                grouped_sales = buyer_group_sales.groupby("Buyer Group")["Sales"].sum().reset_index()
                grouped_sales = grouped_sales.sort_values("Sales", ascending=False)
                total_grouped = grouped_sales["Sales"].sum()
                grouped_sales["Sales %"] = grouped_sales["Sales"].apply(lambda x: f"{x / total_grouped * 100:.1f}%" if total_grouped else "0.0%")
                grouped_sales["Sales"] = grouped_sales["Sales"].apply(fmt_txn)
                group_pie_data = buyer_group_sales.groupby("Buyer Group")["Sales"].sum().reset_index()
                total_pie = group_pie_data["Sales"].sum()
                group_pie_data["Pct"] = group_pie_data["Sales"].apply(lambda x: x / total_pie * 100 if total_pie else 0)
                fig_pie = px.pie(
                    group_pie_data,
                    values="Sales", names="Buyer Group",
                    title="Sales Concentration by Buyer Group",
                )
                fig_pie.update_traces(
                    textinfo="none",
                    hovertemplate="<b>%{label}</b><br>Sales: %{value:,.0f}<br>Concentration: %{customdata:.1f}%<extra></extra>",
                    customdata=group_pie_data["Pct"],
                )
                st.plotly_chart(fig_pie, use_container_width=True)

                csv_buffer = io.BytesIO()
                pnl_df.to_csv(csv_buffer, index=False)
                st.download_button("Download P&L CSV", csv_buffer.getvalue(), "pnl.csv", "text/csv")
        else:
            st.info("Upload transaction data to calculate P&L.")

    # --- PAGE: 6-MONTH PREDICTION ---
    elif current_page == "6-Month Prediction":
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;"> </span>
            <h2 style="margin: 0;">P&L Prediction (Jul'26 - Dec'26)</h2>
        </div>
        <p style="color: #78909c; margin-top: -0.5rem; margin-bottom: 1.5rem;">
            Forecast for the next 6 months with buyer-level breakdown
        </p>
        """, unsafe_allow_html=True)

        if st.session_state.fin_data is not None:
            months_ahead = months_ahead_sb

            # Generate forecast (triggered from sidebar)
            if st.session_state.get("_do_gen_forecast"):
                try:
                    with st.spinner("Predicting company-wide P&L..."):
                        combined = predict_pnl(st.session_state.fin_data, months_ahead)
                        st.session_state.prediction_data = combined

                    if st.session_state.txn_data is not None:
                        with st.spinner("Predicting buyer-level P&L..."):
                            buyer_preds = predict_by_buyer(
                                st.session_state.fin_data,
                                st.session_state.txn_data,
                                months_ahead,
                            )
                            st.session_state.buyer_prediction_data = buyer_preds

                    st.success("Forecast generated!")
                    st.session_state["_do_gen_forecast"] = False
                except Exception as e:
                    st.error(f"Error generating forecast: {e}")

            if st.session_state.prediction_data is not None:
                try:
                    combined = st.session_state.prediction_data
                    hist = combined[combined["type"] == "Historical"]
                    fore = combined[combined["type"] == "Forecast"]

                    # Apply month filter
                    if sel_pred_months:
                        combined = combined[combined["month"].isin(sel_pred_months)]
                        hist = hist[hist["month"].isin(sel_pred_months)]
                        fore = fore[fore["month"].isin(sel_pred_months)]

                    # Apply buyer filter
                    if sel_pred_buyer != "All Buyers" and st.session_state.buyer_prediction_data:
                        if sel_pred_buyer in st.session_state.buyer_prediction_data:
                            buyer_df = st.session_state.buyer_prediction_data[sel_pred_buyer]
                            if sel_pred_months:
                                buyer_df = buyer_df[buyer_df["month"].isin(sel_pred_months)]
                            # Use buyer data for display
                            combined = buyer_df.copy()
                            hist = combined[combined["type"] == "Historical"] if "type" in combined.columns else pd.DataFrame()
                            fore = combined[combined["type"] == "Forecast"] if "type" in combined.columns else pd.DataFrame()

                    # Map P&L head filter to column names
                    head_col_map = {
                        "Revenue": "revenue",
                        "COGS": "cogs",
                        "Gross Profit": "gross_profit",
                        "Total S&D": "total_sd",
                        "Profit after S&D": "profit_after_sd",
                        "Admin & General": "admin_general",
                        "Finance Cost": "financing",
                        "Net Profit": "net_profit",
                    }
                    selected_cols = ["month", "type"] + [head_col_map[h] for h in sel_pnl_heads if h in head_col_map]

                    st.markdown("---")
                    st.markdown("""
                    <div class="section-header">
                        <span style="font-size: 1.3rem;"> </span>
                        <h3 style="margin: 0;">Complete P&L (Historical + Forecast)</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    display = combined[selected_cols].copy() if all(c in combined.columns for c in selected_cols) else combined.copy()
                    for col in display.columns:
                        if col not in ["month", "type"]:
                            display[col] = display[col].apply(lambda x: fmt_fin(x) if isinstance(x, (int, float)) else x)
                    st.dataframe(display, use_container_width=True)

                    # Row-Level P&L Forecast
                    st.markdown("---")
                    st.markdown("""
                    <div class="section-header">
                        <span style="font-size: 1.3rem;"> </span>
                        <h3 style="margin: 0;">Row-Level P&L Forecast</h3>
                    </div>
                    """, unsafe_allow_html=True)

                    def cm_f(val, sales):
                        if sales and sales != 0:
                            return f"{val / sales * 100:.1f}%"
                        return "0.0%"

                    def amt_f(val):
                        return fmt_fin(val)

                    # Collect all buyer-month rows
                    all_rows = []
                    if st.session_state.buyer_prediction_data:
                        for b_name, b_df in st.session_state.buyer_prediction_data.items():
                            # Apply buyer filter
                            if sel_pred_buyer != "All Buyers" and b_name != sel_pred_buyer:
                                continue
                            b_filtered = b_df[b_df["month"].isin(fore["month"])] if not fore.empty else b_df
                            for _, row in b_filtered.iterrows():
                                all_rows.append(row)

                    # P&L head to row-level column mapping
                    row_head_map = {
                        "Revenue": ["Sales", None],
                        "COGS": ["COGS", "COGS %"],
                        "Gross Profit": ["GP", "GP %"],
                        "Total S&D": ["S&D", "S&D %"],
                        "Profit after S&D": ["Profit after S&D", "CM3 %"],
                        "Admin & General": ["Admin", "Admin %"],
                        "Finance Cost": ["Finance", "Fin. %"],
                        "Net Profit": ["Net Profit", "NP %"],
                    }
                    # Always show month, buyer, supplier cols; plus selected P&L heads
                    base_cols = ["Month", "Buyer"]
                    # Add supplier cols if present
                    txn = st.session_state.txn_data
                    if txn is not None and any(c in txn.columns for c in ["Supplier_Name", "Supplier_Location"]):
                        base_cols += [c for c in ["Supplier Name", "Supplier Location"] if True]

                    selected_amount_cols = []
                    selected_pct_cols = []
                    for h in sel_pnl_heads:
                        if h in row_head_map:
                            selected_amount_cols.append(row_head_map[h][0])
                            if row_head_map[h][1] is not None:
                                selected_pct_cols.append(row_head_map[h][1])

                    if all_rows:
                        row_display = pd.DataFrame({
                            "Month": [r["month"] for r in all_rows],
                            "Buyer": [r["buyer"] for r in all_rows],
                            "Sales": [amt_f(r["revenue"]) for r in all_rows],
                            "COGS": [amt_f(r["cogs"]) for r in all_rows],
                            "COGS %": [cm_f(r["cogs"], r["revenue"]) for r in all_rows],
                            "GP": [amt_f(r["gross_profit"]) for r in all_rows],
                            "GP %": [cm_f(r["gross_profit"], r["revenue"]) for r in all_rows],
                            "S&D": [amt_f(r["total_sd"]) for r in all_rows],
                            "S&D %": [cm_f(r["total_sd"], r["revenue"]) for r in all_rows],
                            "Profit after S&D": [amt_f(r["profit_after_sd"]) for r in all_rows],
                            "CM3 %": [cm_f(r["profit_after_sd"], r["revenue"]) for r in all_rows],
                            "Admin": [amt_f(r["admin_general"]) for r in all_rows],
                            "Admin %": [cm_f(r["admin_general"], r["revenue"]) for r in all_rows],
                            "Net Oper. Profit": [amt_f(r["net_operating_profit"]) for r in all_rows],
                            "NOP %": [cm_f(r["net_operating_profit"], r["revenue"]) for r in all_rows],
                            "Finance": [amt_f(r["financing"]) for r in all_rows],
                            "Fin. %": [cm_f(r["financing"], r["revenue"]) for r in all_rows],
                            "Net Profit": [amt_f(r["net_profit"]) for r in all_rows],
                            "NP %": [cm_f(r["net_profit"], r["revenue"]) for r in all_rows],
                        })

                        # Add supplier info if available
                        if txn is not None:
                            sup_cols = [c for c in ["Supplier_Name", "Supplier_Location"] if c in txn.columns]
                            if sup_cols:
                                buyer_col_t = "Buyer Name" if "Buyer Name" in txn.columns else "Buyer_Name"
                                supplier_map = txn.groupby([buyer_col_t]).agg(
                                    **({"Supplier Name": ("Supplier_Name", "first")} if "Supplier_Name" in txn.columns else {}),
                                    **({"Supplier Location": ("Supplier_Location", "first")} if "Supplier_Location" in txn.columns else {}),
                                ).reset_index()
                                row_display = row_display.merge(
                                    supplier_map[[buyer_col_t] + [c for c in ["Supplier Name", "Supplier Location"] if c in supplier_map.columns]],
                                    left_on="Buyer",
                                    right_on=buyer_col_t,
                                    how="left"
                                )
                                for col in ["Supplier Name", "Supplier Location"]:
                                    if col in row_display.columns:
                                        cols = row_display.columns.tolist()
                                        cols.insert(cols.index("Buyer") + 1, cols.pop(cols.index(col)))
                                        row_display = row_display[cols]
                                row_display = row_display.drop(columns=[buyer_col_t], errors="ignore")

                        # Apply P&L heads filter - keep only selected columns
                        keep_cols = ["Month", "Buyer"] + [c for c in ["Supplier Name", "Supplier Location"] if c in row_display.columns]
                        for h in sel_pnl_heads:
                            if h in row_head_map:
                                for c in row_head_map[h]:
                                    if c in row_display.columns:
                                        keep_cols.append(c)
                        keep_cols = [c for c in keep_cols if c in row_display.columns]
                        row_display = row_display[keep_cols]

                        st.dataframe(row_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("Select forecast months and generate forecast to see row-level P&L.")

                    # ═══════════════════════════════════════════════════════════════
                    # SINGLE DEAL FORECAST
                    # ═══════════════════════════════════════════════════════════════
                    st.markdown("---")
                    st.markdown("""
                    <div class="section-header">
                        <span style="font-size: 1.3rem;"> </span>
                        <h3 style="margin: 0;">  Single Deal P&L Forecast</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption("Input a deal to forecast its transaction-level P&L. Enter price per KG and quantity — revenue is auto-calculated. Season (on/off) affects S&D, finance cost and procurement ratios.")

                    if st.session_state.txn_data is not None:
                        txn_data = st.session_state.txn_data
                        buyer_col_t = "Buyer Name" if "Buyer Name" in txn_data.columns else "Buyer_Name"
                        supplier_col_t = "Supplier_Name" if "Supplier_Name" in txn_data.columns else None
                        month_col_t = "Reporting Month" if "Reporting Month" in txn_data.columns else "Reporting_Month"

                        all_buyers = sorted(txn_data[buyer_col_t].dropna().unique().tolist())
                        all_suppliers = sorted(txn_data[supplier_col_t].dropna().unique().tolist()) if supplier_col_t and supplier_col_t in txn_data.columns else []

                        # Season helper
                        def get_season_from_date(dt):
                            mon = dt.month
                            if mon in [11, 12, 1, 4, 5]:
                                return "On-Season"
                            return "Off-Season"

                        # Build finance lookups from alloc files
                        on_lookup = build_finance_pct_lookup(st.session_state.fin_alloc_on) if st.session_state.fin_alloc_on is not None else {}
                        off_lookup = build_finance_pct_lookup(st.session_state.fin_alloc_off) if st.session_state.fin_alloc_off is not None else {}

                        def get_buyer_finance_pct(buyer_name, season):
                            lookup = on_lookup if season == "On-Season" else off_lookup
                            if not lookup:
                                return 0
                            parent = extract_parent_buyer(buyer_name).lower()
                            if parent in lookup:
                                return lookup[parent]
                            for key, val in lookup.items():
                                if parent.startswith(key) or key.startswith(parent):
                                    return val
                            first_word = parent.split()[0] if parent.split() else ""
                            for key, val in lookup.items():
                                if key.startswith(first_word) and first_word:
                                    return val
                            return 0

                        # Rejection rate helpers
                        def calc_rejection_from_df(df):
                            if "Procure_Quantity_Kg" not in df.columns or "Receive_Quantity_KG" not in df.columns:
                                return 0, 0, 0, 0
                            n_total = df.shape[0]
                            if n_total == 0:
                                return 0, 0, 0, 0
                            tot_proc = float(pd.to_numeric(df["Procure_Quantity_Kg"], errors="coerce").fillna(0).sum())
                            tot_recv = float(pd.to_numeric(df["Receive_Quantity_KG"], errors="coerce").fillna(0).sum())
                            if "Status" in df.columns:
                                n_full_rej = int((df["Status"].astype(str).str.upper().str.strip() == "REJECT").sum())
                            else:
                                n_full_rej = 0
                            full_reject_pct = (n_full_rej / n_total * 100) if n_total > 0 else 0
                            partial_reject_pct = ((tot_proc - tot_recv) / tot_proc * 100) if tot_proc > 0 else 0
                            avg_reject_pct = (full_reject_pct + partial_reject_pct) / 2
                            return full_reject_pct, partial_reject_pct, avg_reject_pct, n_total

                        def get_buyer_rejection(buyer_name):
                            bh = txn_data[txn_data[buyer_col_t] == buyer_name]
                            full_r, partial_r, avg_r, n = calc_rejection_from_df(bh)
                            if n == 0:
                                # Fallback: company-wide
                                return calc_rejection_from_df(txn_data)
                            return full_r, partial_r, avg_r, n

                        with st.form("deal_forecast_form"):
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                deal_date = st.date_input("Deal Date")
                            with c2:
                                deal_buyer = st.selectbox("Buyer", all_buyers)
                            with c3:
                                deal_supplier = st.selectbox("Supplier", ["(Any)"] + all_suppliers)

                            c4, c5, c6 = st.columns(3)
                            with c4:
                                deal_price_kg = st.number_input("Price per KG (BDT)", min_value=0.0, step=1.0, format="%.2f")
                            with c5:
                                deal_qty = st.number_input("Procure Quantity (KG)", min_value=0.0, step=100.0, format="%.0f")
                            with c6:
                                # Auto-fill buyer's historical avg rejection
                                full_r_temp, partial_r_temp, avg_r_temp, _ = get_buyer_rejection(deal_buyer)
                                deal_rejection = st.number_input(
                                    "Rejection Rate (%)",
                                    min_value=0.0, max_value=100.0, step=0.01, format="%.2f",
                                    value=round(avg_r_temp, 2) if avg_r_temp > 0 else 0.0,
                                    help=f"Full: {full_r_temp:.2f}% | Partial: {partial_r_temp:.2f}% | Avg: {avg_r_temp:.2f}%"
                                )

                            submitted = st.form_submit_button("Forecast Deal P&L", type="primary")

                        if submitted:
                            if deal_qty <= 0 or deal_price_kg <= 0:
                                st.warning("Please enter quantity and price per KG greater than 0.")
                            else:
                                # Determine season from deal date
                                season = get_season_from_date(deal_date)

                                # Calculate quantities
                                deal_recv_qty = deal_qty * (1 - deal_rejection / 100)
                                deal_rejected_qty = deal_qty - deal_recv_qty
                                deal_sales = deal_recv_qty * deal_price_kg  # Sales revenue from received qty

                                # Get historical ratios for this buyer, split by season
                                buyer_hist = txn_data[txn_data[buyer_col_t] == deal_buyer]
                                if buyer_hist.empty:
                                    st.warning(f"No historical data found for buyer: {deal_buyer}")
                                else:
                                    # Map each transaction month to its season
                                    def txn_month_to_season(m):
                                        ms = str(m).upper()
                                        if any(x in ms for x in ["NOV", "DEC", "JAN", "APR", "MAY"]):
                                            return "On-Season"
                                        return "Off-Season"

                                    if month_col_t in buyer_hist.columns:
                                        buyer_hist = buyer_hist.copy()
                                        buyer_hist["_season"] = buyer_hist[month_col_t].apply(txn_month_to_season)
                                    else:
                                        buyer_hist = buyer_hist.copy()
                                        buyer_hist["_season"] = "On-Season"

                                    # Season-specific historical ratios
                                    same_season = buyer_hist[buyer_hist["_season"] == season]
                                    other_season = buyer_hist[buyer_hist["_season"] != season]

                                    # Ensure numeric columns
                                    for col in ["Sales/Revenue", "Cogs", "Total Selling Opex(F)"]:
                                        if col in buyer_hist.columns:
                                            buyer_hist[col] = pd.to_numeric(buyer_hist[col], errors="coerce").fillna(0)

                                    MIN_TXNS = 3  # minimum transactions for reliable ratios

                                    def calc_ratio(data, cost_col):
                                        if data.empty or "Sales/Revenue" not in data.columns:
                                            return 0
                                        s = float(data["Sales/Revenue"].sum())
                                        c = float(data[cost_col].sum()) if cost_col in data.columns else 0
                                        return (c / s * 100) if s > 0 else 0

                                    # COGS: prefer same-season if enough data, else all buyer data
                                    if len(same_season) >= MIN_TXNS:
                                        cogs_pct = calc_ratio(same_season, "Cogs")
                                        cogs_source_label = f"{season} ({len(same_season)} txns)"
                                    else:
                                        cogs_pct = calc_ratio(buyer_hist, "Cogs")
                                        cogs_source_label = f"All seasons ({len(buyer_hist)} txns)"

                                    # S&D: prefer same-season if enough data, else all buyer data
                                    if len(same_season) >= MIN_TXNS:
                                        sd_pct = calc_ratio(same_season, "Total Selling Opex(F)")
                                        sd_source_label = f"{season} ({len(same_season)} txns)"
                                    else:
                                        sd_pct = calc_ratio(buyer_hist, "Total Selling Opex(F)")
                                        sd_source_label = f"All seasons ({len(buyer_hist)} txns)"

                                    # Fallback: if buyer ratios are still 0, use parent buyer
                                    if (cogs_pct == 0 or sd_pct == 0) and st.session_state.txn_data is not None:
                                        parent = extract_parent_buyer(deal_buyer)
                                        parent_buyers = [b for b in all_buyers if extract_parent_buyer(b) == parent and b != deal_buyer]
                                        if parent_buyers:
                                            parent_hist = txn_data[txn_data[buyer_col_t].isin(parent_buyers)].copy()
                                            for col in ["Sales/Revenue", "Cogs", "Total Selling Opex(F)"]:
                                                if col in parent_hist.columns:
                                                    parent_hist[col] = pd.to_numeric(parent_hist[col], errors="coerce").fillna(0)
                                            if cogs_pct == 0:
                                                cogs_pct = calc_ratio(parent_hist, "Cogs")
                                                if cogs_pct > 0:
                                                    cogs_source_label = f"Parent: {parent} ({len(parent_buyers)} buyers)"
                                            if sd_pct == 0:
                                                sd_pct = calc_ratio(parent_hist, "Total Selling Opex(F)")
                                                if sd_pct > 0:
                                                    sd_source_label = f"Parent: {parent} ({len(parent_buyers)} buyers)"

                                    # Final fallback: company-wide
                                    if cogs_pct == 0 and fin_data:
                                        cogs_pct = calc_ratio(fin_df, "cogs") if "cogs" in fin_df.columns else 0
                                        if cogs_pct > 0:
                                            cogs_source_label = "Company-wide"
                                    if sd_pct == 0 and fin_data:
                                        sd_total_fin = fin_df["total_selling_opex"].sum() if "total_selling_opex" in fin_df.columns else 0
                                        sd_pct = (sd_total_fin / total_rev_fin * 100) if total_rev_fin > 0 else 0
                                        if sd_pct > 0:
                                            sd_source_label = "Company-wide"

                                    # Admin: company-wide
                                    fin_data = st.session_state.fin_data
                                    if fin_data:
                                        fin_df = pnl_to_dataframe(fin_data)
                                        total_rev_fin = fin_df["revenue"].sum()
                                        total_admin = fin_df["admin_general"].sum()
                                        admin_pct = (total_admin / total_rev_fin * 100) if total_rev_fin > 0 else 0
                                    else:
                                        admin_pct = 0

                                    # Finance: buyer-specific from on/off season alloc files
                                    buyer_fin_pct = get_buyer_finance_pct(deal_buyer, season)
                                    fin_pct = buyer_fin_pct * 100  # convert from decimal to percentage

                                    # Calculate deal P&L
                                    deal_cogs = deal_sales * cogs_pct / 100
                                    deal_gp = deal_sales - deal_cogs
                                    deal_sd = deal_sales * sd_pct / 100
                                    deal_profit_after_sd = deal_gp - deal_sd
                                    deal_admin = deal_sales * admin_pct / 100
                                    deal_nop = deal_profit_after_sd - deal_admin
                                    deal_finance = deal_sales * fin_pct / 100
                                    deal_np = deal_nop - deal_finance

                                    def deal_amt(v):
                                        return fmt_crore(v)

                                    def deal_pct(v, base):
                                        return f"{v / base * 100:.1f}%" if base > 0 else "0.0%"

                                    # Season badge
                                    season_badge = "  On-Season" if season == "On-Season" else "  Off-Season"
                                    st.success(f"**Forecast for {deal_buyer}** — {deal_date.strftime('%b %d, %Y')} | {season_badge}")
                                    if deal_supplier != "(Any)":
                                        st.caption(f"Supplier: {deal_supplier}")

                                    # Quantity & Price summary
                                    q1, q2, q3, q4 = st.columns(4)
                                    with q1:
                                        st.metric("Procure Qty", f"{deal_qty:,.0f} KG")
                                    with q2:
                                        st.metric("Forecast Reject", f"{deal_rejection:.2f}%")
                                    with q3:
                                        st.metric("Receive Qty", f"{deal_recv_qty:,.0f} KG")
                                    with q4:
                                        st.metric("Rejected KG", f"{deal_rejected_qty:,.0f} KG")

                                    p1, p2, p3, p4 = st.columns(4)
                                    with p1:
                                        st.metric("Price/KG", f"BDT {deal_price_kg:,.2f}")
                                    with p2:
                                        st.metric("Sales Revenue", deal_amt(deal_sales))
                                    with p3:
                                        wc_val = deal_qty * deal_price_kg
                                        st.metric("Working Capital", deal_amt(wc_val))
                                    with p4:
                                        rej_value = deal_rejected_qty * deal_price_kg
                                        st.metric("Rejected Value", deal_amt(rej_value))

                                    # Debug: show season data counts
                                    on_count = len(buyer_hist[buyer_hist["_season"] == "On-Season"])
                                    off_count = len(buyer_hist[buyer_hist["_season"] != "On-Season"])
                                    full_r, partial_r, avg_r, n_buyer = get_buyer_rejection(deal_buyer)
                                    with st.expander("  Data Sources & Ratios", expanded=False):
                                        st.write(f"On-Season transactions: {on_count} | Off-Season transactions: {off_count}")
                                        st.write(f"Buyer rejection data: {n_buyer} transactions")
                                        st.write(f"  Full Reject: {full_r:.2f}% | Partial Reject: {partial_r:.2f}% | Avg: {avg_r:.2f}%")
                                        st.write(f"COGS source: {cogs_source_label} | S&D source: {sd_source_label}")
                                        st.write(f"COGS %: {cogs_pct:.1f}% | S&D %: {sd_pct:.1f}% | Finance %: {fin_pct:.2f}% | Admin %: {admin_pct:.1f}%")

                                    # Full P&L Forecast Table
                                    forecast_data = pd.DataFrame({
                                        "Line Item": [
                                            "Procure Quantity", "Rejection Rate", "Receive Quantity", "Rejected Quantity",
                                            "", "Sales Revenue", "COGS", "Gross Profit", "Gross Margin",
                                            "", "Total S&D", "Profit after S&D", "CM3 Margin",
                                            "", "Admin & General", "Net Operating Profit", "NOP Margin",
                                            "", "Finance Cost", "Net Profit", "NP Margin",
                                        ],
                                        "Amount": [
                                            f"{deal_qty:,.0f} KG", f"{deal_rejection:.2f}%",
                                            f"{deal_recv_qty:,.0f} KG", f"{deal_rejected_qty:,.0f} KG",
                                            "",
                                            deal_amt(deal_sales), deal_amt(deal_cogs), deal_amt(deal_gp),
                                            deal_pct(deal_gp, deal_sales),
                                            "",
                                            deal_amt(deal_sd), deal_amt(deal_profit_after_sd),
                                            deal_pct(deal_profit_after_sd, deal_sales),
                                            "",
                                            deal_amt(deal_admin), deal_amt(deal_nop),
                                            deal_pct(deal_nop, deal_sales),
                                            "",
                                            deal_amt(deal_finance), deal_amt(deal_np),
                                            deal_pct(deal_np, deal_sales),
                                        ],
                                        "% of Sales": [
                                            "", "", "", "",
                                            "",
                                            "100.0%", deal_pct(deal_cogs, deal_sales), deal_pct(deal_gp, deal_sales), "",
                                            "",
                                            deal_pct(deal_sd, deal_sales), deal_pct(deal_profit_after_sd, deal_sales), "",
                                            "",
                                            deal_pct(deal_admin, deal_sales), deal_pct(deal_nop, deal_sales), "",
                                            "",
                                            deal_pct(deal_finance, deal_sales), deal_pct(deal_np, deal_sales), "",
                                        ],
                                        "Source": [
                                            "Input", "Historical forecast", "Calculated", "Calculated",
                                            "",
                                            "Price/KG × Receive Qty",
                                            f"COGS: {cogs_source_label}", "", "",
                                            "",
                                            f"S&D: {sd_source_label}", "", "",
                                            "",
                                            f"Company-wide ({admin_pct:.1f}%)", "", "",
                                            "",
                                            f"{season} buyer-specific ({fin_pct:.2f}%)", "", "",
                                        ],
                                    })
                                    st.dataframe(forecast_data, use_container_width=True, hide_index=True)

                                    # Decision summary
                                    st.markdown("---")
                                    if deal_np < 0:
                                        st.error(f"  **Deal is loss-making** at NP {deal_amt(deal_np)}. Consider increasing price, reducing rejection, or cutting COGS/S&D.")
                                    elif deal_np < (deal_sales * 0.02):
                                        st.warning(f"  **Thin margin** — NP {deal_amt(deal_np)} ({deal_pct(deal_np, deal_sales)} of sales). Review pricing or cost structure.")
                                    else:
                                        st.success(f"  **Deal is profitable** — NP {deal_amt(deal_np)} ({deal_pct(deal_np, deal_sales)} of sales).")

                                    with st.expander("  Ratio Assumptions"):
                                        st.write(f"**Season:** {season} — On-Season: Nov, Dec, Jan, Apr, May | Off-Season: Feb, Mar, Jun–Oct")
                                        st.write(f"**Price/KG:** BDT {deal_price_kg:,.2f}")
                                        st.write(f"**Procure Qty:** {deal_qty:,.0f} KG → Receive: {deal_recv_qty:,.0f} KG (reject {deal_rejection:.2f}%)")
                                        st.write(f"**Sales Revenue:** {deal_recv_qty:,.0f} KG × BDT {deal_price_kg:,.2f} = {deal_amt(deal_sales)}")
                                        st.write(f"**COGS %:** {cogs_pct:.1f}% (source: {cogs_source_label})")
                                        st.write(f"**S&D %:** {sd_pct:.1f}% (source: {sd_source_label})")
                                        st.write(f"**Admin %:** {admin_pct:.1f}% (company-wide)")
                                        st.write(f"**Finance %:** {fin_pct:.2f}% (buyer-specific {season.lower()} rate)")
                                        if fin_pct > 0:
                                            st.write(f"  → Parent buyer: **{extract_parent_buyer(deal_buyer)}**")
                    else:
                        st.info("Upload transaction data to use the Single Deal Forecast.")

                    st.markdown("---")
                    st.markdown("""
                    <div class="section-header">
                        <span style="font-size: 1.3rem;"> </span>
                        <h3 style="margin: 0;">Full P&L with Contribution Margin</h3>
                    </div>
                    """, unsafe_allow_html=True)

                    if not hist.empty:
                        st.write("**Historical (Jan-Jun '26)**")
                        hist_summary = pnl_summary_table(combined, "Historical")
                        # Filter summary by P&L heads
                        if "Line Item" in hist_summary.columns:
                            head_items = [h for h in sel_pnl_heads]
                            hist_summary = hist_summary[hist_summary["Line Item"].str.contains("|".join(head_items), na=False, case=False)]
                        st.dataframe(hist_summary, use_container_width=True, hide_index=True)

                    if not fore.empty:
                        st.write(f"**Forecast ({fore['month'].iloc[0]} - {fore['month'].iloc[-1]})**")
                        fore_summary = pnl_summary_table(combined, "Forecast")
                        if "Line Item" in fore_summary.columns:
                            head_items = [h for h in sel_pnl_heads]
                            fore_summary = fore_summary[fore_summary["Line Item"].str.contains("|".join(head_items), na=False, case=False)]
                        st.dataframe(fore_summary, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.markdown("""
                    <div class="section-header">
                        <span style="font-size: 1.3rem;"> </span>
                        <h3 style="margin: 0;">Forecast Charts</h3>
                    </div>
                    """, unsafe_allow_html=True)

                    # Filter pnl_items by selected heads
                    all_pnl_items = [
                        ("revenue", "Revenue", "#4CAF50"),
                        ("cogs", "COGS", "#f44336"),
                        ("gross_profit", "Gross Profit", "#FF9800"),
                        ("total_sd", "Total S&D", "#FF5722"),
                        ("profit_after_sd", "Profit after S&D", "#2196F3"),
                        ("admin_general", "Admin & General", "#9C27B0"),
                        ("financing", "Finance Cost", "#607D8B"),
                        ("net_profit", "Net Profit", "#00BCD4"),
                    ]
                    pnl_items = [(col, title, color) for col, title, color in all_pnl_items if title in sel_pnl_heads]

                    if pnl_items:
                        # Calculate % of sales for each P&L item
                        for col, title, color in pnl_items:
                            pct_col = f"{col}_pct"
                            combined[pct_col] = np.where(
                                combined["revenue"] != 0,
                                combined[col] / combined["revenue"] * 100,
                                0
                            )

                        n_items = len(pnl_items)
                        n_rows = (n_items + 1) // 2
                        fig = make_subplots(rows=n_rows, cols=2, subplot_titles=[t[1] for t in pnl_items])

                        for i, (col, title, color) in enumerate(pnl_items):
                            r, c = divmod(i, 2)
                            pct_col = f"{col}_pct"

                            # Bar chart with hover showing % of sales
                            fig.add_trace(go.Bar(
                                x=combined["month"], y=combined[col], name=title,
                                customdata=[[f"{p:.1f}%", fmt_crore(v)] for p, v in zip(combined[pct_col], combined[col])],
                                hovertemplate=f"<b>%{{x}}</b><br>{title}: %{{customdata[1]}}<br>% of Sales: %{{customdata[0]}}<extra></extra>",
                                marker_color=["#4CAF50" if t == "Historical" else color for t in combined["type"]],
                            ), row=r+1, col=c+1)

                        fig.update_layout(height=max(400, n_rows * 300), showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)

                    csv_buffer = io.BytesIO()
                    combined.to_csv(csv_buffer, index=False)
                    st.download_button("Download Full Forecast CSV", csv_buffer.getvalue(), "forecast_pnl.csv", "text/csv")
                except Exception as e:
                    st.error(f"Error displaying forecast: {e}")
        else:
            st.info("Upload financial data to generate predictions.")

    # --- PAGE: ROIC ANALYSIS ---
    elif current_page == "ROIC Analysis":
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;"> </span>
            <h2 style="margin: 0;">ROIC & Working Capital Analysis</h2>
        </div>
        <p style="color: #78909c; margin-top: -0.5rem; margin-bottom: 1.5rem;">
            Working capital efficiency, revenue planning, and salary coverage
        </p>
        """, unsafe_allow_html=True)

        # ── Helper: Season classifier ──
        def get_season(month_str):
            m = str(month_str).upper()
            if any(x in m for x in ["NOV", "DEC", "JAN"]):
                return "On-Season"
            elif any(x in m for x in ["APR", "MAY"]):
                return "On-Season"
            return "Off-Season"

        # ── Helper: Finance % lookup by buyer & season ──
        on_lookup = build_finance_pct_lookup(st.session_state.fin_alloc_on) if st.session_state.fin_alloc_on is not None else {}
        off_lookup = build_finance_pct_lookup(st.session_state.fin_alloc_off) if st.session_state.fin_alloc_off is not None else {}

        def get_buyer_finance_pct(buyer_name, season):
            lookup = on_lookup if season == "On-Season" else off_lookup
            if not lookup:
                return 0
            parent = extract_parent_buyer(buyer_name).lower()
            if parent in lookup:
                return lookup[parent]
            for key, val in lookup.items():
                if parent.startswith(key) or key.startswith(parent):
                    return val
            first_word = parent.split()[0] if parent.split() else ""
            for key, val in lookup.items():
                if key.startswith(first_word) and first_word:
                    return val
            return 0

        # ── Helper: Parse budget file rows ──
        def parse_budget_file(budget_df):
            """Extract key P&L rows and monthly values from budget file."""
            month_names = ["Jul'26", "Aug'26", "Sep'26", "Oct'26", "Nov'26", "Dec'26",
                           "Jan'27", "Feb'27", "Mar'27", "Apr'27", "May'27", "Jun'27"]
            month_aliases = {
                "Jul'26": ["jul'26", "jul 26", "jul26", "july'26", "july 26", "july26"],
                "Aug'26": ["aug'26", "aug 26", "aug26", "august'26", "august 26", "august26"],
                "Sep'26": ["sep'26", "sep 26", "sep26", "september'26", "september 26", "september26"],
                "Oct'26": ["oct'26", "oct 26", "oct26", "october'26", "october 26", "october26"],
                "Nov'26": ["nov'26", "nov 26", "nov26", "november'26", "november 26", "november26"],
                "Dec'26": ["dec'26", "dec 26", "dec26", "december'26", "december 26", "december26"],
                "Jan'27": ["jan'27", "jan 27", "jan27", "january'27", "january 27", "january27"],
                "Feb'27": ["feb'27", "feb 27", "feb27", "february'27", "february 27", "february27"],
                "Mar'27": ["mar'27", "mar 27", "mar27", "march'27", "march 27", "march27"],
                "Apr'27": ["apr'27", "apr 27", "apr27", "april'27", "april 27", "april27"],
                "May'27": ["may'27", "may 27", "may27"],
                "Jun'27": ["jun'27", "jun 27", "jun27", "june'27", "june 27", "june27"],
            }

            def find_month_col(col_name, aliases):
                col_lower = str(col_name).strip().lower()
                for alias in aliases:
                    if alias in col_lower:
                        return True
                return False

            def safe_float(val):
                try:
                    return float(str(val).replace(",", ""))
                except:
                    return None

            # Find key rows (FIRST match only)
            rows = {}
            target_rows = {
                "revenue": "revenue",
                "cogs": "cogs",
                "gross_profit": "gross profit",
                "selling_opex": "selling opex",
                "marketing": "marketing cost",
                "sga": "sg&a",
                "salary": "salary",
                "finance": "cost of capital",
                "net_profit": "cm7",
                "req_cap": "req cap",
                "cycle": "cycle",
            }

            for _, row in budget_df.iterrows():
                first_val = str(row.iloc[0]).strip().lower() if pd.notna(row.iloc[0]) else ""
                for key, pattern in target_rows.items():
                    if pattern in first_val and key not in rows:
                        rows[key] = row

            # Extract monthly values
            result = {m: {} for m in month_names}
            for m, aliases in month_aliases.items():
                for col in budget_df.columns:
                    if find_month_col(col, aliases):
                        for key, row in rows.items():
                            try:
                                val = safe_float(row[col])
                                if val is not None:
                                    result[m][key] = val
                            except:
                                pass
                        break

            return result, month_names

        # ═══════════════════════════════════════════════════════════════
        # SECTION 1: BUDGET P&L ANALYSIS
        # ═══════════════════════════════════════════════════════════════
        if st.session_state.budget_data is not None:
            budget_df = st.session_state.budget_data
            budget_data, month_names = parse_budget_file(budget_df)

            # Determine which months to display based on sidebar filter
            roic_month = st.session_state.get("sb_roic_month", "All Months")
            if roic_month == "All Months":
                display_months = month_names
            else:
                display_months = [roic_month] if roic_month in month_names else []

            if not display_months:
                st.warning(f"No budget data found for **{roic_month}**.")
                st.stop()

            # Build monthly req cap lookup from budget data (needed by Sections 4 & 5)
            monthly_req_caps = {}
            for m in month_names:
                d = budget_data.get(m, {})
                monthly_req_caps[m] = d.get("req_cap", 0)

            # Debug info
            with st.expander("  Debug: Budget File Info", expanded=False):
                st.write(f"Budget file shape: {budget_df.shape}")
                st.write(f"Columns: {budget_df.columns.tolist()[:14]}")
                st.write(f"Rows found by parser: {list(budget_data.get(month_names[0], {}).keys())}")
                st.write(f"Jul'26 data: {budget_data.get(month_names[0], {})}")
                st.write(f"Selected month filter: {roic_month} → showing {len(display_months)} month(s)")

            st.markdown("---")
            st.markdown("""
            <div class="section-header">
                <span style="font-size: 1.3rem;"> </span>
                <h3 style="margin: 0;">  Budget P&L Summary (FY 2026-27)</h3>
            </div>
            """, unsafe_allow_html=True)

            # Build monthly P&L table (filtered)
            pnl_rows = []
            for m in display_months:
                d = budget_data.get(m, {})
                rev = d.get("revenue", 0)
                cogs = d.get("cogs", 0)
                gp = d.get("gross_profit", 0)
                selling = d.get("selling_opex", 0)
                marketing = d.get("marketing", 0)
                sga = d.get("sga", 0)
                salary = d.get("salary", 0)
                finance = d.get("finance", 0)
                np_val = d.get("net_profit", 0)
                req_cap = d.get("req_cap", 0)
                cycle = d.get("cycle", 0)

                gp_pct = gp / rev * 100 if rev else 0
                np_pct = np_val / rev * 100 if rev else 0

                pnl_rows.append({
                    "Month": m,
                    "Season": get_season(m),
                    "Revenue (Cr)": fmt_crore(rev),
                    "COGS (Cr)": fmt_crore(cogs),
                    "GP (Cr)": fmt_crore(gp),
                    "GP%": f"{gp_pct:.1f}%",
                    "S&D (Cr)": fmt_crore(selling + marketing),
                    "Admin (Cr)": fmt_crore(sga),
                    "Salary (Cr)": fmt_crore(salary),
                    "Finance (Cr)": fmt_crore(finance),
                    "NP (Cr)": fmt_crore(np_val),
                    "NP%": f"{np_pct:.1f}%",
                })

            st.dataframe(pd.DataFrame(pnl_rows), use_container_width=True, hide_index=True)

            # Period totals (filtered)
            period = {k: sum(budget_data.get(m, {}).get(k, 0) for m in display_months) for k in
                      ["revenue", "cogs", "gross_profit", "selling_opex", "marketing", "sga", "salary", "finance", "net_profit"]}
            total_rev = period["revenue"]
            total_salary = period["salary"]
            total_finance = period["finance"]
            current_np_margin = period["net_profit"] / total_rev * 100 if total_rev else 0
            if total_rev:
                label = f"{len(display_months)} Month(s)" if len(display_months) < 12 else "Annual"
                st.write(f"**{label} Totals:** Revenue {fmt_crore(total_rev)} | GP {fmt_crore(period['gross_profit'])} ({period['gross_profit']/total_rev*100:.1f}%) | NP {fmt_crore(period['net_profit'])} ({period['net_profit']/total_rev*100:.1f}%)")

            # ═══════════════════════════════════════════════════════════════
            # SECTION 2: WORKING CAPITAL & TURNOVER
            # ═══════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("""
            <div class="section-header">
                <span style="font-size: 1.3rem;"> </span>
                <h3 style="margin: 0;">  Working Capital & Turnover Ratio</h3>
            </div>
            """, unsafe_allow_html=True)

            wc_rows = []
            on_cycle_vals = []
            off_cycle_vals = []
            on_rev_vals = []
            off_rev_vals = []
            on_wc_vals = []
            off_wc_vals = []

            for m in display_months:
                d = budget_data.get(m, {})
                rev = d.get("revenue", 0)
                req_cap = d.get("req_cap", 0)
                cycle = d.get("cycle", 0)
                season = get_season(m)

                actual_cycle = rev / req_cap if req_cap > 0 else cycle
                if season == "On-Season":
                    on_cycle_vals.append(actual_cycle)
                    on_rev_vals.append(rev)
                    on_wc_vals.append(req_cap)
                else:
                    off_cycle_vals.append(actual_cycle)
                    off_rev_vals.append(rev)
                    off_wc_vals.append(req_cap)

                wc_rows.append({
                    "Month": m,
                    "Season": season,
                    "Revenue (Cr)": fmt_crore(rev),
                    "WC Required (Cr)": fmt_crore(req_cap),
                    "Cycle (Budget)": f"{cycle:.2f}x",
                    "Cycle (Actual)": f"{actual_cycle:.2f}x",
                })

            st.dataframe(pd.DataFrame(wc_rows), use_container_width=True, hide_index=True)

            # Seasonal WC metrics (filtered)
            on_avg_cycle = np.mean(on_cycle_vals) if on_cycle_vals else 0
            off_avg_cycle = np.mean(off_cycle_vals) if off_cycle_vals else 0
            on_peak_wc = max(on_wc_vals) if on_wc_vals else 0
            off_peak_wc = max(off_wc_vals) if off_wc_vals else 0
            peak_wc = max(on_peak_wc, off_peak_wc)
            total_wc = sum(d.get("req_cap", 0) for m, d in budget_data.items() if m in display_months)
            monthly_wc_avg = total_wc / len(display_months) if display_months else 0

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if on_wc_vals:
                    st.metric("On-Season Peak WC", fmt_crore(on_peak_wc))
                    st.caption(f"Avg Cycle: {on_avg_cycle:.2f}x")
                else:
                    st.metric("On-Season Peak WC", "N/A")
                    st.caption("No on-season months selected")
            with c2:
                if off_wc_vals:
                    st.metric("Off-Season Peak WC", fmt_crore(off_peak_wc))
                    st.caption(f"Avg Cycle: {off_avg_cycle:.2f}x")
                else:
                    st.metric("Off-Season Peak WC", "N/A")
                    st.caption("No off-season months selected")
            with c3:
                st.metric("  Max WC Needed", fmt_crore(peak_wc))
                st.caption("Peak cash locked")
            with c4:
                st.metric("Monthly WC Avg", fmt_crore(monthly_wc_avg))
                st.caption(f"Total WC: {fmt_crore(total_wc)}")

            # WC Turnover explanation
            if on_wc_vals and off_wc_vals:
                st.info(
                    f"**On-Season** (Nov-Jan, Apr-May): WC turns over **{on_avg_cycle:.2f}x** — for every 1 Cr WC, generate {on_avg_cycle:.2f} Cr revenue.\n\n"
                    f"**Off-Season** (Jul-Oct, Feb-Mar): WC turns over **{off_avg_cycle:.2f}x** — for every 1 Cr WC, generate {off_avg_cycle:.2f} Cr revenue."
                )
            elif on_wc_vals:
                st.info(f"**On-Season months selected.** WC turns over **{on_avg_cycle:.2f}x** — for every 1 Cr WC, generate {on_avg_cycle:.2f} Cr revenue.")
            else:
                st.info(f"**Off-Season months selected.** WC turns over **{off_avg_cycle:.2f}x** — for every 1 Cr WC, generate {off_avg_cycle:.2f} Cr revenue.")

            # ═══════════════════════════════════════════════════════════════
            # SECTION 3: MINIMUM NP TO COVER SALARY
            # ═══════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("""
            <div class="section-header">
                <span style="font-size: 1.3rem;"> </span>
                <h3 style="margin: 0;">  Minimum Net Profit to Cover Salary</h3>
            </div>
            """, unsafe_allow_html=True)

            if total_rev > 0 and total_salary > 0:
                min_np_needed = total_salary
                min_np_margin_needed = total_salary / total_rev * 100

                if current_np_margin > 0:
                    rev_needed_at_current_margin = total_salary / (current_np_margin / 100)
                else:
                    rev_needed_at_current_margin = None

                period_label = roic_month if roic_month != "All Months" else "Annual"
                st.write(f"**{period_label} Salary Coverage:**")
                s1, s2, s3, s4 = st.columns(4)
                with s1:
                    st.metric("Total Salary", fmt_crore(total_salary))
                    st.caption(f"{total_salary/total_rev*100:.1f}% of revenue")
                with s2:
                    st.metric("Current NP", fmt_crore(period["net_profit"]))
                    st.caption(f"{current_np_margin:.1f}% margin")
                with s3:
                    st.metric("Min NP Needed", fmt_crore(min_np_needed))
                    st.caption(f"{min_np_margin_needed:.1f}% margin")
                with s4:
                    if current_np_margin > 0:
                        st.metric("Rev Needed (current margin)", fmt_crore(rev_needed_at_current_margin))
                        st.caption(f"At {current_np_margin:.1f}% NP margin")
                    else:
                        st.metric("Rev Needed", "N/A")
                        st.caption("NP margin is negative")

                np_gap = min_np_margin_needed - current_np_margin
                if np_gap > 0:
                    st.warning(
                        f"**Gap:** NP margin needs to improve by **{np_gap:.2f} percentage points** to cover salary. "
                        f"Current: {current_np_margin:.2f}% → Needed: {min_np_margin_needed:.2f}%"
                    )
                else:
                    st.success(f"**Current NP margin ({current_np_margin:.2f}%) is sufficient** to cover salary.")

                # Margin breakdown
                st.write("**Margin Analysis:**")
                gp_margin = period["gross_profit"] / total_rev * 100 if total_rev else 0
                sd_margin = (period["selling_opex"] + period["marketing"]) / total_rev * 100 if total_rev else 0
                admin_pct = period["sga"] / total_rev * 100 if total_rev else 0
                finance_margin = period["finance"] / total_rev * 100 if total_rev else 0
                salary_margin = total_salary / total_rev * 100 if total_rev else 0

                margin_table = pd.DataFrame({
                    "P&L Head": ["Revenue", "GP%", "S&D%", "Admin%", "Finance%", "NP%", "Salary%", "Min NP Margin Needed"],
                    "Value": [
                        fmt_crore(total_rev),
                        f"{gp_margin:.1f}%",
                        f"{sd_margin:.1f}%",
                        f"{admin_pct:.1f}%",
                        f"{finance_margin:.1f}%",
                        f"{current_np_margin:.2f}%",
                        f"{salary_margin:.1f}%",
                        f"{min_np_margin_needed:.2f}%",
                    ],
                    "Note": [
                        "",
                        f"GP - S&D - Admin - Finance = NP",
                        "",
                        "",
                        "Fixed — cannot reduce",
                        f"{'✅' if current_np_margin >= min_np_margin_needed else '❌'} {'Sufficient' if current_np_margin >= min_np_margin_needed else 'Insufficient'}",
                        "Salary as % of revenue",
                        f"Need NP ≥ {fmt_crore(min_np_needed)}",
                    ]
                })
                st.dataframe(margin_table, use_container_width=True, hide_index=True)

            else:
                st.info("Upload budget file with revenue and salary data to calculate.")

            # ═══════════════════════════════════════════════════════════════
            # ROW-LEVEL P&L FORECAST — Per-deal forecast with full P&L
            # ═══════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("""
            <div class="section-header">
                <span style="font-size: 1.3rem;"> </span>
                <h3 style="margin: 0;">Row-Level P&L Forecast</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Add deals to generate a per-deal P&L forecast with all heads.")

            # Ensure admin_pct and salary_margin are available
            if "admin_pct" not in dir() or admin_pct is None:
                admin_pct = (period["sga"] / total_rev * 100) if total_rev > 0 and "sga" in period else 0
            if "salary_margin" not in dir() or salary_margin is None:
                salary_margin = (total_salary / total_rev * 100) if total_rev > 0 and total_salary > 0 else 0

            if st.session_state.txn_data is not None:
                txn_data = st.session_state.txn_data
                buyer_col_t = "Buyer Name" if "Buyer Name" in txn_data.columns else "Buyer_Name"
                supplier_col_t = "Supplier_Name" if "Supplier_Name" in txn_data.columns else None
                all_buyers = sorted(txn_data[buyer_col_t].dropna().unique().tolist())
                all_suppliers = sorted(txn_data[supplier_col_t].dropna().unique().tolist()) if supplier_col_t and supplier_col_t in txn_data.columns else []

                # ── Historical rejection rate analysis per buyer ──
                for col in ["Procure_Quantity_Kg", "Receive_Quantity_KG", "Status"]:
                    if col in txn_data.columns:
                        if col != "Status":
                            txn_data[col] = pd.to_numeric(txn_data[col], errors="coerce").fillna(0)

                def calc_rejection_from_df(df):
                    if "Procure_Quantity_Kg" not in df.columns or "Receive_Quantity_KG" not in df.columns:
                        return 0, 0, 0, 0, 0, 0
                    n_total = df.shape[0]
                    if n_total == 0:
                        return 0, 0, 0, 0, 0, 0
                    tot_proc = float(pd.to_numeric(df["Procure_Quantity_Kg"], errors="coerce").fillna(0).sum())
                    tot_recv = float(pd.to_numeric(df["Receive_Quantity_KG"], errors="coerce").fillna(0).sum())
                    if "Status" in df.columns:
                        n_full_rej = int((df["Status"].astype(str).str.upper().str.strip() == "REJECT").sum())
                    else:
                        n_full_rej = 0
                    full_reject_pct = (n_full_rej / n_total * 100) if n_total > 0 else 0
                    partial_reject_pct = ((tot_proc - tot_recv) / tot_proc * 100) if tot_proc > 0 else 0
                    avg_reject_pct = (full_reject_pct + partial_reject_pct) / 2
                    return full_reject_pct, partial_reject_pct, avg_reject_pct, tot_proc, tot_recv, n_total

                overall_full, overall_partial, overall_avg, overall_proc, overall_recv, overall_n = calc_rejection_from_df(txn_data)

                def get_buyer_rejection(buyer_name):
                    bh = txn_data[txn_data[buyer_col_t] == buyer_name]
                    full_r, partial_r, avg_r, tp, tn, n = calc_rejection_from_df(bh)
                    if n == 0:
                        return overall_full, overall_partial, overall_avg, 0, 0, 0
                    return full_r, partial_r, avg_r, tp, tn, n

                def get_buyer_ratios(buyer_name):
                    bh = txn_data[txn_data[buyer_col_t] == buyer_name].copy()
                    for col in ["Sales/Revenue", "Cogs", "Total Selling Opex(F)"]:
                        if col in bh.columns:
                            bh[col] = pd.to_numeric(bh[col], errors="coerce").fillna(0)
                    s = float(bh["Sales/Revenue"].sum()) if "Sales/Revenue" in bh.columns else 0
                    c = float(bh["Cogs"].sum()) if "Cogs" in bh.columns else 0
                    sd = float(bh["Total Selling Opex(F)"].sum()) if "Total Selling Opex(F)" in bh.columns else 0
                    cogs_pct = (c / s * 100) if s > 0 else 0
                    sd_pct = (sd / s * 100) if s > 0 else 0
                    if cogs_pct == 0 and total_rev > 0:
                        cogs_pct = period["cogs"] / total_rev * 100 if "cogs" in period else 0
                    if sd_pct == 0 and total_rev > 0:
                        sd_pct = (period["selling_opex"] + period["marketing"]) / total_rev * 100 if "selling_opex" in period else 0
                    return cogs_pct, sd_pct

                def get_buyer_fin_pct(buyer_name, deal_date):
                    mon = deal_date.month
                    season = "On-Season" if mon in [11, 12, 1, 4, 5] else "Off-Season"
                    return get_buyer_finance_pct(buyer_name, season) * 100

                # Initialize deals
                if "row_forecast_deals" not in st.session_state:
                    st.session_state.row_forecast_deals = []

                # ── Input Form ──
                with st.form("row_forecast_form"):
                    st.write("**Add New Deal**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        dp_buyer = st.selectbox("Buyer Name", all_buyers, key="rf_buyer")
                    with c2:
                        dp_date = st.date_input("Deal Date", key="rf_date")
                    with c3:
                        dp_supplier = st.selectbox("Supplier Name", ["(Optional)"] + all_suppliers, key="rf_supplier")

                    c4, c5 = st.columns(2)
                    with c4:
                        dp_proc_qty = st.number_input("Quantity Ordered (KG)", min_value=0.0, step=100.0, format="%.0f", key="rf_qty")
                    with c5:
                        dp_price_kg = st.number_input("Price per KG (BDT)", min_value=0.0, step=1.0, format="%.2f", key="rf_price")

                    add_col, clear_col = st.columns([1, 1])
                    with add_col:
                        add_deal = st.form_submit_button("  Add Deal", type="primary")
                    with clear_col:
                        clear_all = st.form_submit_button("  Clear All Deals")

                if clear_all:
                    st.session_state.row_forecast_deals = []
                    st.rerun()

                if add_deal and dp_proc_qty > 0 and dp_price_kg > 0:
                    # Get buyer-specific ratios
                    cogs_pct, sd_pct = get_buyer_ratios(dp_buyer)
                    fin_pct = get_buyer_fin_pct(dp_buyer, dp_date)
                    full_r, partial_r, avg_r, _, _, _ = get_buyer_rejection(dp_buyer)
                    season = "On-Season" if dp_date.month in [11, 12, 1, 4, 5] else "Off-Season"
                    rejection_rate = avg_r

                    # Calculate P&L
                    dp_recv_qty = dp_proc_qty * (1 - rejection_rate / 100)
                    dp_revenue = dp_recv_qty * dp_price_kg
                    deal_cogs = dp_revenue * cogs_pct / 100
                    deal_gp = dp_revenue - deal_cogs
                    deal_sd = dp_revenue * sd_pct / 100
                    deal_admin = dp_revenue * admin_pct / 100
                    deal_nop = deal_gp - deal_sd - deal_admin
                    deal_finance = dp_revenue * fin_pct / 100
                    deal_np = deal_nop - deal_finance
                    deal_wc = dp_proc_qty * dp_price_kg

                    deal_entry = {
                        "buyer": dp_buyer,
                        "supplier": dp_supplier if dp_supplier != "(Optional)" else "",
                        "date": dp_date,
                        "month": dp_date.strftime("%b-%y"),
                        "season": season,
                        "proc_qty": dp_proc_qty,
                        "recv_qty": dp_recv_qty,
                        "price_kg": dp_price_kg,
                        "rejection_rate": rejection_rate,
                        "revenue": dp_revenue,
                        "cogs_pct": cogs_pct,
                        "cogs": deal_cogs,
                        "gp": deal_gp,
                        "gp_pct": (deal_gp / dp_revenue * 100) if dp_revenue > 0 else 0,
                        "sd_pct": sd_pct,
                        "sd": deal_sd,
                        "admin_pct": admin_pct,
                        "admin": deal_admin,
                        "nop": deal_nop,
                        "nop_pct": (deal_nop / dp_revenue * 100) if dp_revenue > 0 else 0,
                        "fin_pct": fin_pct,
                        "finance": deal_finance,
                        "np": deal_np,
                        "np_pct": (deal_np / dp_revenue * 100) if dp_revenue > 0 else 0,
                        "wc": deal_wc,
                    }
                    st.session_state.row_forecast_deals.append(deal_entry)
                    st.rerun()

                # ── Display Forecast Table ──
                deals = st.session_state.row_forecast_deals
                if deals:
                    st.markdown("---")
                    st.write(f"**Row-Level P&L Forecast ({len(deals)} Deal{'s' if len(deals) != 1 else ''})**")

                    forecast_rows = []
                    for d in deals:
                        forecast_rows.append({
                            "Month": d["month"],
                            "Buyer": d["buyer"],
                            "Supplier": d["supplier"],
                            "Qty (KG)": f"{d['proc_qty']:,.0f}",
                            "Price/KG": f"{d['price_kg']:,.0f}",
                            "Reject %": f"{d['rejection_rate']:.2f}%",
                            "Sales": fmt_crore(d["revenue"]),
                            "COGS": fmt_crore(d["cogs"]),
                            "COGS %": f"{d['cogs_pct']:.1f}%",
                            "GP": fmt_crore(d["gp"]),
                            "GP %": f"{d['gp_pct']:.1f}%",
                            "S&D": fmt_crore(d["sd"]),
                            "S&D %": f"{d['sd_pct']:.1f}%",
                            "Admin": fmt_crore(d["admin"]),
                            "Admin %": f"{d['admin_pct']:.1f}%",
                            "Finance": fmt_crore(d["finance"]),
                            "Finance %": f"{d['fin_pct']:.1f}%",
                            "NOP": fmt_crore(d["nop"]),
                            "NOP %": f"{d['nop_pct']:.1f}%",
                            "NP": fmt_crore(d["np"]),
                            "NP %": f"{d['np_pct']:.1f}%",
                            "WC": fmt_crore(d["wc"]),
                        })

                    # Totals row
                    t_rev = sum(d["revenue"] for d in deals)
                    t_cogs = sum(d["cogs"] for d in deals)
                    t_gp = sum(d["gp"] for d in deals)
                    t_sd = sum(d["sd"] for d in deals)
                    t_admin = sum(d["admin"] for d in deals)
                    t_nop = sum(d["nop"] for d in deals)
                    t_fin = sum(d["finance"] for d in deals)
                    t_np = sum(d["np"] for d in deals)
                    t_wc = sum(d["wc"] for d in deals)

                    forecast_rows.append({
                        "Month": "TOTAL",
                        "Buyer": "",
                        "Supplier": "",
                        "Qty (KG)": f"{sum(d['proc_qty'] for d in deals):,.0f}",
                        "Price/KG": "",
                        "Reject %": "",
                        "Sales": fmt_crore(t_rev),
                        "COGS": fmt_crore(t_cogs),
                        "COGS %": f"{t_cogs/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "GP": fmt_crore(t_gp),
                        "GP %": f"{t_gp/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "S&D": fmt_crore(t_sd),
                        "S&D %": f"{t_sd/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "Admin": fmt_crore(t_admin),
                        "Admin %": f"{t_admin/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "Finance": fmt_crore(t_fin),
                        "Finance %": f"{t_fin/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "NOP": fmt_crore(t_nop),
                        "NOP %": f"{t_nop/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "NP": fmt_crore(t_np),
                        "NP %": f"{t_np/t_rev*100:.1f}%" if t_rev > 0 else "0.0%",
                        "WC": fmt_crore(t_wc),
                    })

                    forecast_df = pd.DataFrame(forecast_rows)
                    st.dataframe(forecast_df, use_container_width=True, hide_index=True)

                    # KPIs
                    st.write("**Summary:**")
                    s1, s2, s3, s4, s5 = st.columns(5)
                    with s1:
                        st.metric("Total Revenue", fmt_crore(t_rev))
                    with s2:
                        st.metric("Total GP", fmt_crore(t_gp))
                        st.caption(f"{t_gp/t_rev*100:.1f}%" if t_rev > 0 else "0%")
                    with s3:
                        st.metric("Total NOP", fmt_crore(t_nop))
                        st.caption(f"{t_nop/t_rev*100:.1f}%" if t_rev > 0 else "0%")
                    with s4:
                        st.metric("Total NP", fmt_crore(t_np))
                        st.caption(f"{t_np/t_rev*100:.1f}%" if t_rev > 0 else "0%")
                    with s5:
                        st.metric("Total WC", fmt_crore(t_wc))

                    # Salary coverage
                    if total_salary > 0:
                        st.markdown("---")
                        st.write("**Salary Coverage Insight:**")
                        if t_np >= total_salary:
                            st.success(f"**NP {fmt_crore(t_np)} covers salary {fmt_crore(total_salary)}.** Surplus: {fmt_crore(t_np - total_salary)}")
                        else:
                            gap = total_salary - t_np
                            st.warning(f"**NP {fmt_crore(t_np)} is short of salary {fmt_crore(total_salary)}.** Gap: {fmt_crore(gap)}")

                    # Remove individual deals
                    st.markdown("---")
                    st.write("**Remove Deal:**")
                    for i, d in enumerate(deals):
                        col_a, col_b = st.columns([4, 1])
                        with col_a:
                            st.caption(f"#{i+1} — {d['buyer']} | {d['month']} | {d['proc_qty']:,.0f} KG | Rev: {fmt_crore(d['revenue'])}")
                        with col_b:
                            if st.button("Remove", key=f"rm_deal_{i}"):
                                st.session_state.row_forecast_deals.pop(i)
                                st.rerun()
                else:
                    st.info("Add deals above to see the row-level P&L forecast.")
            else:
                st.info("Upload transaction data to use the Row-Level P&L Forecast.")

            # ═══════════════════════════════════════════════════════════════
            # SECTION 4: BUYER-WISE MIN NP & SALES TARGETS (from millwise budget)
            # ═══════════════════════════════════════════════════════════════
            if st.session_state.buyer_budget_data is not None:
                st.markdown("---")
                st.markdown("""
                <div class="section-header">
                    <span style="font-size: 1.3rem;"> </span>
                    <h3 style="margin: 0;">  Buyer-Wise NP Margin & Sales Targets</h3>
                </div>
                """, unsafe_allow_html=True)

                mill_df = st.session_state.buyer_budget_data

                # Parse millwise budget: extract per-buyer monthly revenue
                # Revenue section: Row 40 = header, Row 41+ = crop headers + buyer rows
                # Row format: Name, UnitPrice, "1,000", Total, Jul'26..Jun'27
                def parse_millwise_revenue(mill_df):
                    """Extract per-buyer monthly revenue from millwise budget."""
                    month_names = ["Jul'26", "Aug'26", "Sep'26", "Oct'26", "Nov'26", "Dec'26",
                                   "Jan'27", "Feb'27", "Mar'27", "Apr'27", "May'27", "Jun'27"]
                    buyer_revenue = {}
                    crop_headers = ["paddy", "maize", "turmeric", "mustard", "chilli"]

                    def safe_float_mill(val):
                        try:
                            v = str(val).replace(",", "").replace("#REF!", "0").strip()
                            if not v or v == "-":
                                return 0
                            return float(v)
                        except:
                            return 0

                    # Find revenue section start (row with "Revenue data")
                    rev_start = None
                    for i, row in mill_df.iterrows():
                        val = str(row.iloc[0]).strip().lower() if pd.notna(row.iloc[0]) else ""
                        if "revenue data" in val:
                            rev_start = i
                            break
                    if rev_start is None:
                        rev_start = 40

                    # Parse revenue rows - skip header row, identify crop headers vs buyer rows
                    current_crop = None
                    for i in range(rev_start + 1, len(mill_df)):
                        row = mill_df.iloc[i]
                        name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                        name_lower = name.lower()

                        # Skip empty rows
                        if not name:
                            current_crop = None
                            continue

                        # Crop headers: known crop names
                        if name_lower in crop_headers:
                            current_crop = name
                            continue

                        # Skip the total row at the end (empty name in col 0, or "Total")
                        # Check if col 1 is numeric (unit price for buyer rows)
                        col1_val = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                        try:
                            col1_num = float(col1_val.replace(",", ""))
                        except:
                            continue  # Not a buyer row (header, total, etc.)

                        # Extract monthly revenue from columns 4-15 (Jul'26 to Jun'27)
                        try:
                            total_val = safe_float_mill(row.iloc[3]) if len(row) > 3 else 0
                            monthly_vals = []
                            for ci in range(4, 16):
                                if ci < len(row):
                                    monthly_vals.append(safe_float_mill(row.iloc[ci]))
                                else:
                                    monthly_vals.append(0)

                            # Only add if there's actual data
                            if name not in buyer_revenue:
                                buyer_revenue[name] = {"crop": current_crop, "total": 0, "monthly": {}}
                            buyer_revenue[name]["total"] += total_val
                            for mi, m in enumerate(month_names):
                                buyer_revenue[name]["monthly"][m] = buyer_revenue[name]["monthly"].get(m, 0) + monthly_vals[mi]
                        except Exception:
                            pass

                    return buyer_revenue, month_names

                buyer_rev_data, mill_month_names = parse_millwise_revenue(mill_df)

                if not buyer_rev_data:
                    st.warning("Could not parse buyer-wise revenue from millwise budget file.")
                else:
                    # Build buyer summary
                    buyer_rows = []
                    total_rev_all = sum(d["total"] for d in buyer_rev_data.values())
                    for buyer, data in sorted(buyer_rev_data.items(), key=lambda x: -x[1]["total"]):
                        buyer_rows.append({
                            "Buyer": buyer,
                            "Crop": data["crop"] or "-",
                            "Total Rev (Cr)": data["total"],
                            "Share %": (data["total"] / total_rev_all * 100) if total_rev_all > 0 else 0,
                        })
                    buyer_summary = pd.DataFrame(buyer_rows)

                    # Filter by selected month
                    if roic_month != "All Months" and roic_month in mill_month_names:
                        filtered_buyers = []
                        for buyer, data in buyer_rev_data.items():
                            monthly_rev = data["monthly"].get(roic_month, 0)
                            if monthly_rev > 0:
                                filtered_buyers.append({
                                    "Buyer": buyer,
                                    "Crop": data["crop"] or "-",
                                    "Revenue (Cr)": monthly_rev,
                                    "Share %": 0,
                                })
                        if filtered_buyers:
                            filter_df = pd.DataFrame(filtered_buyers)
                            filter_total = filter_df["Revenue (Cr)"].sum()
                            filter_df["Share %"] = filter_df["Revenue (Cr)"] / filter_total * 100 if filter_total > 0 else 0

                            # Allocate salary & WC by sales share
                            filter_df["Salary (Cr)"] = filter_df["Share %"] / 100 * total_salary
                            filter_df["Min NP Margin %"] = filter_df.apply(
                                lambda r: (r["Salary (Cr)"] / r["Revenue (Cr)"] * 100) if r["Revenue (Cr)"] > 0 else 0, axis=1
                            )
                            # WC allocation using actual monthly req cap
                            month_req_cap = monthly_req_caps.get(roic_month, 0)
                            filter_df["WC Required (Cr)"] = filter_df["Share %"] / 100 * month_req_cap
                            # NP contribution = buyer revenue * per-buyer NP margin (from txn data)
                            def get_buyer_npm(buyer_name):
                                if st.session_state.txn_data is None:
                                    return current_np_margin
                                txn = st.session_state.txn_data
                                bc = "Buyer Name" if "Buyer Name" in txn.columns else "Buyer_Name"
                                bh = txn[txn[bc].astype(str).str.upper().str.strip() == buyer_name.upper().strip()]
                                if len(bh) == 0:
                                    bh = txn[txn[bc].astype(str).str.upper().str.strip().str.startswith(buyer_name.upper().strip())]
                                if len(bh) == 0:
                                    bh = txn[txn[bc].astype(str).str.upper().str.contains(buyer_name.upper().strip(), na=False)]
                                if len(bh) == 0:
                                    return current_np_margin
                                for c in ["Sales/Revenue", "Cogs", "Total Selling Opex(F)"]:
                                    if c in bh.columns:
                                        bh[c] = pd.to_numeric(bh[c], errors="coerce").fillna(0)
                                s = float(bh["Sales/Revenue"].sum()) if "Sales/Revenue" in bh.columns else 0
                                cogs = float(bh["Cogs"].sum()) if "Cogs" in bh.columns else 0
                                sd = float(bh["Total Selling Opex(F)"].sum()) if "Total Selling Opex(F)" in bh.columns else 0
                                if s <= 0:
                                    return current_np_margin
                                fin_pct = total_finance / total_rev * 100 if total_rev > 0 else 0
                                buyer_npm = 100 - (cogs / s * 100) - (sd / s * 100) - admin_pct - fin_pct
                                return buyer_npm
                            filter_df["NP Contribution (Cr)"] = filter_df.apply(
                                lambda r: r["Revenue (Cr)"] * (get_buyer_npm(r["Buyer"]) / 100), axis=1
                            )
                            # ROIC = NP / WC
                            filter_df["ROIC %"] = filter_df.apply(
                                lambda r: (r["NP Contribution (Cr)"] / r["WC Required (Cr)"] * 100) if r["WC Required (Cr)"] > 0 else 0, axis=1
                            )

                            # Min sales rev needed per buyer
                            if current_np_margin > 0:
                                filter_df["Min Rev Needed (Cr)"] = filter_df["Salary (Cr)"] / (current_np_margin / 100)
                                filter_df["Gap (Cr)"] = filter_df["Min Rev Needed (Cr)"] - filter_df["Revenue (Cr)"]
                            else:
                                filter_df["Min Rev Needed (Cr)"] = None
                                filter_df["Gap (Cr)"] = None

                            # Display
                            disp = filter_df.copy()
                            disp["Revenue (Cr)"] = disp["Revenue (Cr)"].apply(fmt_crore)
                            disp["Share %"] = disp["Share %"].apply(lambda x: f"{x:.1f}%")
                            disp["Salary (Cr)"] = disp["Salary (Cr)"].apply(fmt_crore)
                            disp["Min NP Margin %"] = disp["Min NP Margin %"].apply(lambda x: f"{x:.1f}%")
                            disp["WC Required (Cr)"] = disp["WC Required (Cr)"].apply(fmt_crore)
                            disp["NP Contribution (Cr)"] = disp["NP Contribution (Cr)"].apply(fmt_crore)
                            disp["ROIC %"] = disp["ROIC %"].apply(lambda x: f"{x:.1f}%")
                            disp["Min Rev Needed (Cr)"] = disp["Min Rev Needed (Cr)"].apply(
                                lambda x: fmt_crore(x) if x else "N/A"
                            )
                            disp["Gap (Cr)"] = disp["Gap (Cr)"].apply(
                                lambda x: fmt_crore(x) if x and not np.isnan(x) else "N/A"
                            )

                            disp.columns = ["Buyer", "Crop", "Revenue (Cr)", "Share", "Salary (Cr)",
                                            "Min NP Margin", "WC Required (Cr)", "NP Contribution (Cr)", "ROIC",
                                            "Min Rev Needed (Cr)", "Gap (Cr)"]
                            st.dataframe(disp, use_container_width=True, hide_index=True)

                            # Chart
                            fig = go.Figure()
                            fig.add_trace(go.Bar(
                                x=filter_df["Buyer"].tolist(),
                                y=filter_df["ROIC %"].tolist(),
                                name="ROIC (%)",
                                marker_color="#4CAF50",
                            ))
                            fig.add_trace(go.Bar(
                                x=filter_df["Buyer"].tolist(),
                                y=filter_df["Share %"].tolist(),
                                name="Sales Share (%)",
                                marker_color="#2196F3",
                            ))
                            fig.update_layout(
                                title=f"Buyer-Wise: ROIC vs Sales Share ({roic_month})",
                                barmode="group", height=400, xaxis_tickangle=-45,
                                yaxis_title="%", yaxis_tickfont=dict(color="#1a1a1a"),
                                xaxis_tickfont=dict(color="#1a1a1a"),
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning(f"No buyer revenue found for **{roic_month}**.")
                    else:
                        # Show annual summary
                        disp = buyer_summary.copy()
                        disp["Total Rev (Cr)"] = disp["Total Rev (Cr)"].apply(fmt_crore)
                        disp["Share %"] = disp["Share %"].apply(lambda x: f"{x:.1f}%")
                        disp.columns = ["Buyer", "Crop", "Total Rev (Cr)", "Share"]
                        st.dataframe(disp, use_container_width=True, hide_index=True)

                    st.info(
                        "**Min NP Margin** = Buyer's allocated Salary ÷ Buyer Revenue — minimum profit margin this buyer must generate to cover its salary.\n\n"
                        "**WC Required** = Working capital allocated by buyer's sales share of company's monthly requirement.\n\n"
                        "**NP Contribution** = Buyer Revenue × Buyer's Own NP Margin (from txn COGS% & S&D%) — estimated net profit this buyer generates.\n\n"
                        "**ROIC** = NP Contribution ÷ WC Required × 100 — return on working capital invested in this buyer."
                    )
            else:
                st.info("Upload **Millwise Budget** (Step 7 in sidebar) for buyer-wise analysis.")

            # ═══════════════════════════════════════════════════════════════
            # SECTION 5: REQUIRED WC — OVERALL & BUYERWISE (from millwise budget)
            # ═══════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("""
            <div class="section-header">
                <span style="font-size: 1.3rem;"> </span>
                <h3 style="margin: 0;">  Required Working Capital — Overall & Buyerwise</h3>
            </div>
            """, unsafe_allow_html=True)

            # Overall WC summary - monthly_req_caps already computed above
            yearly_wc = sum(monthly_req_caps.values())
            if roic_month != "All Months" and roic_month in month_names:
                period_wc = monthly_req_caps.get(roic_month, 0)
                w1, w2 = st.columns(2)
                with w1:
                    st.metric("  WC Required", fmt_crore(period_wc))
                    st.caption(f"{roic_month} only")
                with w2:
                    st.metric("  Max WC Peak", fmt_crore(peak_wc))
                    st.caption("Highest single month")
            else:
                monthly_wc = yearly_wc / len(display_months) if display_months else 0
                w1, w2, w3 = st.columns(3)
                with w1:
                    st.metric("  Total WC Required", fmt_crore(yearly_wc))
                    st.caption("Yearly aggregate")
                with w2:
                    st.metric("  Monthly WC Avg", fmt_crore(monthly_wc))
                    st.caption("Monthly average")
                with w3:
                    st.metric("  Max WC Peak", fmt_crore(peak_wc))
                    st.caption("Highest single month")

            # Buyer-wise WC from millwise budget
            if st.session_state.buyer_budget_data is not None:
                mill_df = st.session_state.buyer_budget_data
                buyer_rev_data, mill_month_names = parse_millwise_revenue(mill_df)

                if buyer_rev_data:
                    total_rev_all = sum(d["total"] for d in buyer_rev_data.values())

                    # Per-buyer NP margin from transaction data (shared by both branches)
                    def get_buyer_np_margin_tx(buyer_name):
                        if st.session_state.txn_data is None:
                            return current_np_margin
                        txn = st.session_state.txn_data
                        bc = "Buyer Name" if "Buyer Name" in txn.columns else "Buyer_Name"
                        # Try exact match first, then partial (budget names like "ACI FOODS" match txn "ACI Foods - Saraswatipur")
                        bh = txn[txn[bc].astype(str).str.upper().str.strip() == buyer_name.upper().strip()]
                        if len(bh) == 0:
                            bh = txn[txn[bc].astype(str).str.upper().str.strip().str.startswith(buyer_name.upper().strip())]
                        if len(bh) == 0:
                            bh = txn[txn[bc].astype(str).str.upper().str.contains(buyer_name.upper().strip(), na=False)]
                        if len(bh) == 0:
                            return current_np_margin
                        for c in ["Sales/Revenue", "Cogs", "Total Selling Opex(F)"]:
                            if c in bh.columns:
                                bh[c] = pd.to_numeric(bh[c], errors="coerce").fillna(0)
                        s = float(bh["Sales/Revenue"].sum()) if "Sales/Revenue" in bh.columns else 0
                        cogs = float(bh["Cogs"].sum()) if "Cogs" in bh.columns else 0
                        sd = float(bh["Total Selling Opex(F)"].sum()) if "Total Selling Opex(F)" in bh.columns else 0
                        if s <= 0:
                            return current_np_margin
                        cogs_pct = cogs / s * 100
                        sd_pct = sd / s * 100
                        buyer_npm = 100 - cogs_pct - sd_pct - admin_pct - (total_finance / total_rev * 100 if total_rev > 0 else 0)
                        return buyer_npm

                    if roic_month != "All Months" and roic_month in mill_month_names:
                        # Single month view - use actual req cap for that month
                        month_req_cap = monthly_req_caps.get(roic_month, 0)

                        filtered = []
                        for buyer, data in buyer_rev_data.items():
                            monthly_rev = data["monthly"].get(roic_month, 0)
                            if monthly_rev > 0:
                                month_total_rev = sum(d["monthly"].get(roic_month, 0) for d in buyer_rev_data.values())
                                share = monthly_rev / month_total_rev if month_total_rev > 0 else 0
                                buyer_wc = share * month_req_cap
                                # Per-buyer NP margin from transaction data
                                buyer_npm = get_buyer_np_margin_tx(buyer)
                                buyer_np = monthly_rev * (buyer_npm / 100)
                                buyer_roic = (buyer_np / buyer_wc * 100) if buyer_wc > 0 else 0
                                filtered.append({
                                    "Buyer": buyer,
                                    "Revenue (Cr)": monthly_rev,
                                    "Share": share,
                                    "WC Required (Cr)": buyer_wc,
                                    "NP Contribution (Cr)": buyer_np,
                                    "ROIC": buyer_roic,
                                })
                        if filtered:
                            b_disp = pd.DataFrame(filtered)
                            # Add total row
                            total_rev_m = b_disp["Revenue (Cr)"].sum()
                            total_wc_m = b_disp["WC Required (Cr)"].sum()
                            total_np_m = b_disp["NP Contribution (Cr)"].sum()
                            total_roic_m = (total_np_m / total_wc_m * 100) if total_wc_m > 0 else 0
                            total_row_m = pd.DataFrame([{
                                "Buyer": "TOTAL",
                                "Revenue (Cr)": total_rev_m,
                                "Share": 1.0,
                                "WC Required (Cr)": total_wc_m,
                                "NP Contribution (Cr)": total_np_m,
                                "ROIC": total_roic_m,
                            }])
                            b_disp = pd.concat([b_disp, total_row_m], ignore_index=True)
                            b_disp["Revenue (Cr)"] = b_disp["Revenue (Cr)"].apply(fmt_crore)
                            b_disp["Share"] = b_disp["Share"].apply(lambda x: f"{x*100:.1f}%")
                            b_disp["WC Required (Cr)"] = b_disp["WC Required (Cr)"].apply(fmt_crore)
                            b_disp["NP Contribution (Cr)"] = b_disp["NP Contribution (Cr)"].apply(fmt_crore)
                            b_disp["ROIC"] = b_disp["ROIC"].apply(lambda x: f"{x:.1f}%")
                            st.dataframe(b_disp, use_container_width=True, hide_index=True)
                    else:
                        # Annual summary - allocate WC by annual revenue share
                        filtered = []
                        for buyer, data in buyer_rev_data.items():
                            if data["total"] > 0:
                                share = data["total"] / total_rev_all if total_rev_all > 0 else 0
                                buyer_yearly_wc = share * yearly_wc
                                # Per-buyer NP margin from transaction data
                                buyer_npm = get_buyer_np_margin_tx(buyer)
                                buyer_annual_np = data["total"] * (buyer_npm / 100)
                                buyer_roic = (buyer_annual_np / buyer_yearly_wc * 100) if buyer_yearly_wc > 0 else 0
                                filtered.append({
                                    "Buyer": buyer,
                                    "Annual Rev (Cr)": data["total"],
                                    "Share": share,
                                    "Yearly WC (Cr)": buyer_yearly_wc,
                                    "NP Contribution (Cr)": buyer_annual_np,
                                    "ROIC": buyer_roic,
                                })
                        if filtered:
                            b_disp = pd.DataFrame(filtered)
                            # Add total row
                            total_rev_val = b_disp["Annual Rev (Cr)"].sum()
                            total_wc_val = b_disp["Yearly WC (Cr)"].sum()
                            total_np_val = b_disp["NP Contribution (Cr)"].sum()
                            total_roic = (total_np_val / total_wc_val * 100) if total_wc_val > 0 else 0
                            total_row = pd.DataFrame([{
                                "Buyer": "TOTAL",
                                "Annual Rev (Cr)": total_rev_val,
                                "Share": 1.0,
                                "Yearly WC (Cr)": total_wc_val,
                                "NP Contribution (Cr)": total_np_val,
                                "ROIC": total_roic,
                            }])
                            b_disp = pd.concat([b_disp, total_row], ignore_index=True)
                            b_disp["Annual Rev (Cr)"] = b_disp["Annual Rev (Cr)"].apply(fmt_crore)
                            b_disp["Share"] = b_disp["Share"].apply(lambda x: f"{x*100:.1f}%")
                            b_disp["Yearly WC (Cr)"] = b_disp["Yearly WC (Cr)"].apply(fmt_crore)
                            b_disp["NP Contribution (Cr)"] = b_disp["NP Contribution (Cr)"].apply(fmt_crore)
                            b_disp["ROIC"] = b_disp["ROIC"].apply(lambda x: f"{x:.1f}%")
                            st.dataframe(b_disp, use_container_width=True, hide_index=True)

            # ═══════════════════════════════════════════════════════════════
            # SECTION 6: ROIC SENSITIVITY
            # ═══════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("""
            <div class="section-header">
                <span style="font-size: 1.3rem;"> </span>
                <h3 style="margin: 0;">  ROIC at Different Profit Levels</h3>
            </div>
            """, unsafe_allow_html=True)

            roic_rows = []
            for np_target in [0, 0.01, 0.02, 0.03, 0.05, 0.08]:
                profit = total_rev * np_target
                roic_pct = (profit / peak_wc * 100) if peak_wc > 0 else 0
                roic_rows.append({
                    "NP Margin": f"{np_target*100:.1f}%",
                    "Net Profit (Cr)": fmt_crore(profit),
                    "ROIC (on Peak WC)": f"{roic_pct:.1f}%",
                    "Covers Salary?": "✅" if profit >= total_salary else "❌",
                })
            st.dataframe(pd.DataFrame(roic_rows), use_container_width=True, hide_index=True)

            st.caption("ROIC = Net Profit / Peak Working Capital × 100")

        else:
            st.info("  Upload a **Budget File** (Step 5 in sidebar) to see ROIC analysis.")

    # --- PAGE: SALARY COVERAGE CALCULATOR ---
else:
    st.info("  Upload data from the sidebar to get started.")
    st.info("  Upload data from the sidebar to get started.")
    st.markdown("""
    ### Getting Started

    **1. Transaction Data** (Row-Level):
    - Required: Sales/Revenue, Cogs, Total Selling Opex(F), Profit .After - S& D, Buyer Name
    - Optional: Reporting Month (for month-level cost allocation)

    **2. Financial Data** (Monthly P&L):
    - Full P&L with Revenue, COGS, S&D, Admin/General, Finance costs
    - P&L line items as column headers, months as rows

    **3. Working Capital Data** (Optional):
    - For ROIC (Return on Invested Capital) analysis
    - Include: Cash, Receivables, Inventory, Payables, Fixed Assets

    ### P&L Formula (Strict)
    1. Gross Profit = Revenue - COGS
    2. Total S&D = Selling Opex + Marketing + Other S&D
    3. Profit after S&D = GP - Total S&D
    4. Total Admin & General = Salary + Field Visit + Legal/Sub + Engagement + Admin + General + Misc
    5. Net Operating Profit = Profit after S&D - Admin & General + Other Income
    6. Profit before Financing = Net Operating Profit + Interest Income
    7. Finance Cost = Crowdfunding + Bank/NBFI + Factoring
    8. Profit before Tax = Profit before Financing - Finance Cost
    9. Net Profit = Profit before Tax - Tax
    """)
