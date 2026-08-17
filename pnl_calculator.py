import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from sklearn.linear_model import LinearRegression


COLUMN_MAP = {
    "Sales/Revenue": "Sales",
    "Cogs": "COGS",
    "Total Selling Opex(F)": "Selling_Opex",
    "Profit .After - S& D": "Profit_After_SD",
    "Buyer Name": "Buyer",
    "Sales Date": "Sales_Date",
    "Reporting Month": "Reporting_Month",
    "Product Name": "Product",
    "Net Sales Amount": "Net_Sales",
    "Total Cogs": "Total_Cogs",
    "Gross Quantity": "Gross_Qty",
    "Receive Quantity KG": "Receive_Qty",
    "Unit Price2": "Unit_Price_Sales",
    "Total Truck Rent": "Truck_Rent",
    "Total Selling Opex1": "Total_Selling_Opex1",
}

def normalize_col(col: str) -> str:
    import re
    s = col.lower().strip()
    s = s.replace("/", " ")
    s = s.replace("(", " ").replace(")", " ")
    s = re.sub(r"[\s_]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


REQUIRED_COLS = [
    "Sales/Revenue",
    "Cogs",
    "Total Selling Opex(F)",
    "Profit .After - S& D",
    "Buyer Name",
]

OPTIONAL_COLS = [
    "Reporting Month",
    "Sales Date",
]


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.replace(r"[\n\r]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    return df


def match_column(df: pd.DataFrame, target: str) -> str:
    target_norm = normalize_col(target)
    for col in df.columns:
        if normalize_col(col) == target_norm:
            return col
    return None


def validate_data(df: pd.DataFrame) -> Tuple[bool, list]:
    df = clean_column_names(df)
    missing = []
    for col in REQUIRED_COLS:
        if match_column(df, col) is None:
            missing.append(col)
    return len(missing) == 0, missing


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_map = {}
    for col in df.columns:
        for target in REQUIRED_COLS + OPTIONAL_COLS:
            if match_column(pd.DataFrame(columns=[col]), target) == col and col != target:
                rename_map[col] = target
                break
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_column_names(df)
    df = rename_columns(df)
    df = df.copy()

    for col in ["Sales/Revenue", "Cogs", "Total Selling Opex(F)", "Profit .After - S& D"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "").str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "Reporting Month" in df.columns:
        df["Reporting Month"] = df["Reporting Month"].astype(str).str.strip()

    return df


def calculate_row_level_pnl(
    df: pd.DataFrame,
    month_buyer_costs: Dict[str, Dict[str, Dict[str, float]]],
) -> pd.DataFrame:
    """Calculate full P&L at transaction level using per-month per-buyer cost allocation."""
    df = df.copy()
    df["GP"] = df["Sales/Revenue"] - df["Cogs"]
    df["GP_Pct"] = np.where(df["Sales/Revenue"] != 0, df["GP"] / df["Sales/Revenue"] * 100, 0)
    df["Profit_After_SD"] = df["GP"] - df["Total Selling Opex(F)"]
    df["Profit_After_SD_Pct"] = np.where(
        df["Sales/Revenue"] != 0, df["Profit_After_SD"] / df["Sales/Revenue"] * 100, 0
    )

    for col in [
        "Admin_Expense", "Finance_Cost", "Delivery_Cost_Alloc", "Selling_Labor_Alloc",
        "Selling_Packaging_Alloc", "Selling_Others_Alloc", "COD_Charge_Alloc",
        "Marketing_Alloc", "Branding_Alloc", "Call_Center_Alloc",
        "Other_SD_Alloc", "Discount_Alloc", "Other_Income_Alloc",
    ]:
        df[col] = 0.0

    if month_buyer_costs:
        from financial_parser import normalize_month

        for idx, row in df.iterrows():
            month = normalize_month(str(row.get("Reporting Month", "")))
            buyer = row.get("Buyer Name", "")

            for txn_month, buyers in month_buyer_costs.items():
                if normalize_month(txn_month) == month and buyer in buyers:
                    costs = buyers[buyer]
                    buyer_month_sales = df[
                        (df["Reporting Month"].apply(lambda x: normalize_month(str(x))) == month) &
                        (df["Buyer Name"] == buyer)
                    ]["Sales/Revenue"].sum()

                    if buyer_month_sales > 0:
                        ratio = row["Sales/Revenue"] / buyer_month_sales
                        df.at[idx, "Admin_Expense"] = costs.get("admin_general", 0) * ratio
                        df.at[idx, "Finance_Cost"] = costs.get("financing", 0) * ratio
                    break

    df["Net_Operating_Profit"] = df["Profit_After_SD"] - df["Admin_Expense"]
    df["Net_Profit"] = df["Net_Operating_Profit"] - df["Finance_Cost"]
    df["Net_Profit_Pct"] = np.where(
        df["Sales/Revenue"] != 0, df["Net_Profit"] / df["Sales/Revenue"] * 100, 0
    )

    return df


def generate_buyer_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = df.groupby("Buyer Name").agg(
        Sales=("Sales/Revenue", "sum"),
        COGS=("Cogs", "sum"),
        Selling_Opex=("Total Selling Opex(F)", "sum"),
        Admin_Expense=("Admin_Expense", "sum"),
        Finance_Cost=("Finance_Cost", "sum"),
        Net_Profit=("Net_Profit", "sum"),
        Transactions=("Sales/Revenue", "count"),
    ).reset_index()

    summary["GP"] = summary["Sales"] - summary["COGS"]
    summary["Profit_After_SD"] = summary["GP"] - summary["Selling_Opex"]
    summary["Net_Operating_Profit"] = summary["Profit_After_SD"] - summary["Admin_Expense"]
    summary["GP_Pct"] = np.where(summary["Sales"] != 0, summary["GP"] / summary["Sales"] * 100, 0)
    summary["Net_Profit_Pct"] = np.where(summary["Sales"] != 0, summary["Net_Profit"] / summary["Sales"] * 100, 0)

    return summary


def generate_pnl_summary(df: pd.DataFrame) -> dict:
    return {
        "Total Sales": df["Sales/Revenue"].sum(),
        "Total COGS": df["Cogs"].sum(),
        "Gross Profit": df["GP"].sum(),
        "Total Selling Opex": df["Total Selling Opex(F)"].sum(),
        "Profit After S&D": df["Profit_After_SD"].sum(),
        "Total Admin Expense": df["Admin_Expense"].sum(),
        "Net Operating Profit": df["Net_Operating_Profit"].sum(),
        "Total Finance Cost": df["Finance_Cost"].sum(),
        "Net Profit": df["Net_Profit"].sum(),
    }


def predict_next_period(
    df: pd.DataFrame,
    periods: int = 1,
    group_by: Optional[str] = None,
) -> pd.DataFrame:
    df = df.copy()

    if "Reporting Month" in df.columns:
        df["Period_Num"] = pd.Categorical(df["Reporting Month"]).codes
    elif "Sales Date" in df.columns:
        df["Period_Num"] = df["Sales Date"].dt.to_period("M").astype(str)
        df["Period_Num"] = pd.Categorical(df["Period_Num"]).codes
    else:
        df["Period_Num"] = 0

    if group_by and group_by in df.columns:
        grouped = df.groupby([group_by, "Period_Num"]).agg(
            Sales=("Sales/Revenue", "sum"),
            COGS=("Cogs", "sum"),
            Selling_Opex=("Total Selling Opex(F)", "sum"),
        ).reset_index()
    else:
        grouped = df.groupby("Period_Num").agg(
            Sales=("Sales/Revenue", "sum"),
            COGS=("Cogs", "sum"),
            Selling_Opex=("Total Selling Opex(F)", "sum"),
        ).reset_index()
        group_by = None

    predictions = []
    groups = grouped[group_by].unique() if group_by else [None]

    for grp in groups:
        if grp is not None:
            grp_data = grouped[grouped[group_by] == grp]
        else:
            grp_data = grouped

        if len(grp_data) < 2:
            continue

        X = grp_data["Period_Num"].values.reshape(-1, 1)

        for metric in ["Sales", "COGS", "Selling_Opex"]:
            y = grp_data[metric].values
            model = LinearRegression()
            model.fit(X, y)

            future_X = np.arange(
                grp_data["Period_Num"].max() + 1,
                grp_data["Period_Num"].max() + 1 + periods,
            ).reshape(-1, 1)
            pred = model.predict(future_X)

            for i, p in enumerate(pred):
                predictions.append({
                    "Group": grp if grp else "All",
                    "Forecast_Period": i + 1,
                    "Metric": metric,
                    "Predicted_Value": max(0, p),
                    "Trend_Slope": model.coef_[0],
                })

    pred_df = pd.DataFrame(predictions)
    return pred_df


def format_currency(value: float) -> str:
    if value == 0:
        return "BDT 0.00 Cr"
    val_crore = value / 10_000_000
    abs_val = abs(val_crore)
    sign = "-" if val_crore < 0 else ""
    if abs_val >= 100:
        return f"BDT {sign}{abs_val:,.0f} Cr"
    elif abs_val >= 1:
        return f"BDT {sign}{abs_val:,.2f} Cr"
    elif abs_val >= 0.1:
        return f"BDT {sign}{abs_val:.2f} Cr"
    elif abs_val >= 0.01:
        return f"BDT {sign}{abs_val:.3f} Cr"
    elif abs_val >= 0.001:
        return f"BDT {sign}{abs_val:.4f} Cr"
    else:
        return f"BDT {sign}{abs_val:.5f} Cr"
