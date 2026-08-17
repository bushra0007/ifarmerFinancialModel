import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from sklearn.linear_model import LinearRegression


def parse_financial_csv(filepath) -> dict:
    """Parse the financial data CSV - full P&L hierarchy."""
    if hasattr(filepath, 'read'):
        filepath.seek(0)
        df = pd.read_csv(filepath, header=0)
    else:
        df = pd.read_csv(filepath, header=0)

    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    def find_col(keywords, exclude=None):
        exclude = exclude or []
        for c in df.columns:
            norm = c.lower().strip()
            if all(k in norm for k in keywords) and not any(e in norm for e in exclude):
                return c
        return None

    month_col = df.columns[0]
    months = df[month_col].dropna().astype(str).tolist()

    def get_val(col_name, month_row_idx):
        if col_name is None or col_name not in df.columns:
            return 0.0
        val = df.iloc[month_row_idx][col_name]
        if pd.isna(val):
            return 0.0
        s = str(val).replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            return 0.0

    # === SALES & COGS ===
    revenue_col = find_col(["total", "revenue"])
    cogs_col = find_col(["total", "cost", "goods", "sold"])

    # === SELLING & DISTRIBUTION ===
    delivery_col = find_col(["delivery", "cost"])
    selling_labor_col = find_col(["selling", "opex", "labor"])
    selling_pkg_col = find_col(["selling", "opex", "packaging"])
    selling_others_col = find_col(["selling", "opex", "others"])
    cod_col = find_col(["cod", "charge"])
    total_selling_opex_col = find_col(["total", "selling", "opex"], exclude=["distribution"])

    branding_col = find_col(["branding", "expenses"])
    call_center_col = find_col(["call", "center"])
    total_marketing_col = find_col(["total", "marketing", "expenses"])

    other_sd_exp_col = find_col(["other", "selling", "distribution", "expenses"])
    discount_col = find_col(["discount", "expense"])
    total_other_sd_col = find_col(["total", "other", "selling", "distribution", "expenses"])
    total_sd_col = find_col(["total", "selling", "distribution", "expense"], exclude=["other"])

    # === ADMIN & GENERAL ===
    salary_core_col = find_col(["salary", "core"])
    salary_field_col = find_col(["salary", "field"])
    bonus_core_col = find_col(["bonus", "core"])
    bonus_field_col = find_col(["bonus", "field"])
    perf_bonus_col = find_col(["performance", "bonus"])
    total_salary_col = find_col(["total", "salary", "expenses"])

    fd_perdiem_col = find_col(["field", "visit", "per-diem"])
    fd_accom_col = find_col(["field", "visit", "accommodation"])
    fd_meeting_col = find_col(["field", "visit", "official", "meeting"])
    fd_conveyance_col = find_col(["field", "visit", "conveyance"])
    fd_misc_col = find_col(["field", "visit", "miscellaneous"])
    total_fd_col = find_col(["total", "field", "visit", "cost"])

    legal_exp_col = find_col(["legal", "regulatory"])
    membership_col = find_col(["membership", "subscription"])
    rd_col = find_col(["research", "development"])
    total_legal_col = find_col(["total", "legal", "subscription", "advisory"])

    celebration_col = find_col(["celebration", "recreation"])
    total_engagement_col = find_col(["total", "employee", "engagement"])

    conveyance_col = find_col(["conveyance", "expenses"], exclude=["field"])
    printing_col = find_col(["printing", "stationary"])
    repair_col = find_col(["repair", "maintenance"])
    meals_col = find_col(["meals", "entertainment"])
    office_col = find_col(["office", "general", "supplies"])
    total_admin_exp_col = find_col(["total", "administrative", "expenses"])

    internet_col = find_col(["internet", "expense"])
    mobile_col = find_col(["mobile", "bill"])
    rent_col = find_col(["rent", "expense"])
    utility_col = find_col(["utility", "expenses"])
    bank_mfs_col = find_col(["bank", "mfs", "charge"])
    insurance_col = find_col(["insurance", "premium"])
    total_general_col = find_col(["total", "general", "expenses"])

    misc_exp_col = find_col(["miscellaneous", "expenses"], exclude=["field", "visit"])
    bd_col = find_col(["business", "development"])
    other_exp_col = find_col(["other", "expense"], exclude=["income", "selling", "operating"])
    postage_col = find_col(["postage", "courier"])
    total_misc_col = find_col(["total", "miscellaneous", "expenses"])
    total_admin_general_col = find_col(["total", "administrative", "general", "expenses"])

    # === OTHER INCOME ===
    other_income_detail_col = find_col(["other", "income"], exclude=["total", "operating"])
    total_other_income_col = find_col(["total", "other", "operating", "income"])

    # === FINANCE COST ===
    # Handle both "interest" and "interset" (typo in CSV)
    crowdfunding_col = find_col(["crowd", "funding"], exclude=["total"])
    total_crowdfunding_col = find_col(["total", "crowd", "funding"])

    bank_interest_col = find_col(["city", "bank"], exclude=["total", "factoring"])
    sbl_col = find_col(["expense", "sbl"], exclude=["total", "factoring"])
    total_bank_interest_col = find_col(["total", "loan", "bank"])

    factoring_svc_col = find_col(["service", "charges", "factoring"], exclude=["total"])
    factoring_int_col = find_col(["expense", "factoring"], exclude=["total"])
    total_factoring_col = find_col(["total", "factoring"])

    total_financing_col = find_col(["summary", "financing", "costs"])

    tax_col = find_col(["tax", "profit"], exclude=["before"])
    interest_income_col = find_col(["total", "interest", "income"])

    result = {}
    for idx, month in enumerate(months):
        # === 1. SALES ===
        revenue = get_val(revenue_col, idx)

        # === 2. COGS ===
        cogs = get_val(cogs_col, idx)

        # === 3. GROSS PROFIT = Revenue - COGS ===
        gp = revenue - cogs

        # === 4. SELLING & DISTRIBUTION ===
        delivery = get_val(delivery_col, idx)
        selling_labor = get_val(selling_labor_col, idx)
        selling_pkg = get_val(selling_pkg_col, idx)
        selling_others = get_val(selling_others_col, idx)
        cod = get_val(cod_col, idx)
        total_selling_opex = delivery + selling_labor + selling_pkg + selling_others + cod

        branding = get_val(branding_col, idx)
        call_center = get_val(call_center_col, idx)
        total_marketing = branding + call_center

        other_sd = get_val(other_sd_exp_col, idx)
        discount = get_val(discount_col, idx)
        total_other_sd = other_sd + discount
        total_sd = total_selling_opex + total_marketing + total_other_sd

        # === 5. PROFIT AFTER S&D (OP) = GP - Total SD ===
        profit_after_sd = gp - total_sd

        # === 6. ADMIN & GENERAL ===
        salary_core = get_val(salary_core_col, idx)
        salary_field = get_val(salary_field_col, idx)
        bonus_core = get_val(bonus_core_col, idx)
        bonus_field = get_val(bonus_field_col, idx)
        perf_bonus = get_val(perf_bonus_col, idx)
        total_salary = salary_core + salary_field + bonus_core + bonus_field + perf_bonus

        fd_perdiem = get_val(fd_perdiem_col, idx)
        fd_accom = get_val(fd_accom_col, idx)
        fd_meeting = get_val(fd_meeting_col, idx)
        fd_conveyance = get_val(fd_conveyance_col, idx)
        fd_misc = get_val(fd_misc_col, idx)
        total_field_visit = fd_perdiem + fd_accom + fd_meeting + fd_conveyance + fd_misc

        legal = get_val(legal_exp_col, idx)
        membership = get_val(membership_col, idx)
        rd = get_val(rd_col, idx)
        total_legal_sub = legal + membership + rd

        celebration = get_val(celebration_col, idx)
        total_engagement = celebration

        conveyance = get_val(conveyance_col, idx)
        printing = get_val(printing_col, idx)
        repair = get_val(repair_col, idx)
        meals = get_val(meals_col, idx)
        office = get_val(office_col, idx)
        total_admin_exp = conveyance + printing + repair + meals + office

        internet = get_val(internet_col, idx)
        mobile = get_val(mobile_col, idx)
        rent = get_val(rent_col, idx)
        utility = get_val(utility_col, idx)
        bank_mfs = get_val(bank_mfs_col, idx)
        insurance = get_val(insurance_col, idx)
        total_general = internet + mobile + rent + utility + bank_mfs + insurance

        misc = get_val(misc_exp_col, idx)
        bd = get_val(bd_col, idx)
        other_exp = get_val(other_exp_col, idx)
        postage = get_val(postage_col, idx)
        total_misc = misc + bd + other_exp + postage

        total_admin_general = total_salary + total_field_visit + total_legal_sub + total_engagement + total_admin_exp + total_general + total_misc

        # === 7. OTHER INCOME ===
        other_income = get_val(total_other_income_col, idx)

        # === 8. NET OPERATING PROFIT = Profit after S&D - Admin & General + Other Income ===
        net_operating = profit_after_sd - total_admin_general + other_income

        # === 9. INTEREST INCOME ===
        interest_income = get_val(interest_income_col, idx)

        # === 10. PROFIT BEFORE FINANCING AND TAX ===
        profit_before_financing = net_operating + interest_income

        # === 11. FINANCE COST ===
        crowdfunding_int = get_val(total_crowdfunding_col, idx)
        bank_int = get_val(total_bank_interest_col, idx)
        factoring_cost = get_val(total_factoring_col, idx)
        total_financing = crowdfunding_int + bank_int + factoring_cost

        # === 12. PROFIT BEFORE TAX = Profit before Financing - Finance Cost ===
        profit_before_tax = profit_before_financing - total_financing

        # === 13. TAX ===
        tax = get_val(tax_col, idx)

        # === 14. NET PROFIT = Profit before Tax - Tax ===
        net_profit = profit_before_tax - tax

        result[month] = {
            # Sales
            "revenue": revenue,
            # COGS
            "cogs": cogs,
            # Gross Profit
            "gross_profit": gp,
            # S&D - Selling Opex
            "delivery_cost": delivery,
            "selling_labor": selling_labor,
            "selling_packaging": selling_pkg,
            "selling_others": selling_others,
            "cod_charge": cod,
            "total_selling_opex": total_selling_opex,
            # S&D - Marketing
            "branding": branding,
            "call_center": call_center,
            "total_marketing": total_marketing,
            # S&D - Other S&D
            "other_sd_exp": other_sd,
            "discount": discount,
            "total_other_sd": total_other_sd,
            # Total S&D
            "total_sd": total_sd,
            # Profit after S&D
            "profit_after_sd": profit_after_sd,
            # Admin & General - Salary
            "salary_core": salary_core,
            "salary_field": salary_field,
            "bonus_core": bonus_core,
            "bonus_field": bonus_field,
            "perf_bonus": perf_bonus,
            "total_salary": total_salary,
            # Admin & General - Field Visit
            "fd_perdiem": fd_perdiem,
            "fd_accom": fd_accom,
            "fd_meeting": fd_meeting,
            "fd_conveyance": fd_conveyance,
            "fd_misc": fd_misc,
            "total_field_visit": total_field_visit,
            # Admin & General - Legal/Sub/Advisory
            "legal": legal,
            "membership": membership,
            "rd": rd,
            "total_legal_sub": total_legal_sub,
            # Admin & General - Employee Engagement
            "celebration": celebration,
            "total_engagement": total_engagement,
            # Admin & General - Administrative
            "conveyance": conveyance,
            "printing": printing,
            "repair": repair,
            "meals": meals,
            "office": office,
            "total_admin_exp": total_admin_exp,
            # Admin & General - General
            "internet": internet,
            "mobile": mobile,
            "rent": rent,
            "utility": utility,
            "bank_mfs": bank_mfs,
            "insurance": insurance,
            "total_general": total_general,
            # Admin & General - Miscellaneous
            "misc_exp": misc,
            "bd_exp": bd,
            "other_exp": other_exp,
            "postage": postage,
            "total_misc": total_misc,
            # Total Admin & General
            "admin_general": total_admin_general,
            # Other Income
            "other_income": other_income,
            # Net Operating Profit
            "net_operating_profit": net_operating,
            # Interest Income
            "interest_income": interest_income,
            # Profit before Financing
            "profit_before_financing": profit_before_financing,
            # Finance Cost
            "crowdfunding_int": crowdfunding_int,
            "bank_int": bank_int,
            "factoring_cost": factoring_cost,
            "financing": total_financing,
            # Profit before Tax
            "profit_before_tax": profit_before_tax,
            # Tax
            "tax": tax,
            # Net Profit
            "net_profit": net_profit,
        }

    return {"months": months, "data": result}


def pnl_to_dataframe(financial_data: dict) -> pd.DataFrame:
    rows = []
    for month in financial_data["months"]:
        row = financial_data["data"][month]
        row["month"] = month
        rows.append(row)
    return pd.DataFrame(rows)


def get_cost_ratios(financial_data: dict) -> dict:
    df = pnl_to_dataframe(financial_data)
    total_revenue = df["revenue"].sum()
    return {
        "cogs_ratio": df["cogs"].sum() / total_revenue if total_revenue else 0,
        "sd_ratio": df["total_sd"].sum() / total_revenue if total_revenue else 0,
        "admin_ratio": df["admin_general"].sum() / total_revenue if total_revenue else 0,
        "financing_ratio": df["financing"].sum() / total_revenue if total_revenue else 0,
        "gross_margin": df["gross_profit"].sum() / total_revenue if total_revenue else 0,
        "net_margin": df["net_profit"].sum() / total_revenue if total_revenue else 0,
        "monthly_averages": {col: df[col].mean() for col in df.columns if col != "month"},
        "monthly_totals": {col: df[col].sum() for col in df.columns if col != "month"},
    }


def normalize_month(s: str) -> str:
    """Normalize month string to 'mon-YY' format for matching."""
    import re
    s = str(s).lower().strip()
    s = s.replace("\u2018", "-").replace("\u2019", "-").replace("'", "-").replace("_", "-").replace(" ", "")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = s.replace("--", "-").strip("-")
    parts = s.split("-")
    if len(parts) == 2:
        mon, yr = parts
        months = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}
        if mon in months and yr not in months:
            return f"{mon}-{yr}"
        elif yr in months and mon not in months:
            return f"{yr}-{mon}"
        return f"{mon}-{yr}"
    return s


def extract_parent_buyer(buyer_name: str) -> str:
    """Extract parent buyer name from a full buyer name.
    
    Examples:
        'ACI Foods - Bikrompur' -> 'ACI Foods'
        'ACI Godrej - Shirajgonj' -> 'ACI Godrej'
        'CP Bangladesh - Birganj' -> 'CP Bangladesh'
        'CP Bangladesh Bhaluka' -> 'CP Bangladesh'
        'Nourish - Bhaluka' -> 'Nourish'
        'Nourish Chittagong' -> 'Nourish'
        'New Hope Feed Mill - Bogura' -> 'New Hope Feed Mill'
        'Kazi Farms Ltd - Bhola' -> 'Kazi Farms Ltd'
        'MGI - Tanvir Food Ltd - Bogra' -> 'MGI'
        'MGI - Tanvir Foods Ltd (Bogura)' -> 'MGI'
        'TK Group - Naogaon' -> 'TK Group'
        'Bangladesh Edible Oil Ltd' -> 'Bangladesh Edible Oil'
    """
    s = str(buyer_name).strip()
    s_lower = s.lower()

    # Known parent mappings for exact or fuzzy matches
    known_parents = {
        'mgi': 'MGI',
        'nourish': 'Nourish',
        'tk group': 'TK Group',
        'cp bangladesh': 'CP Bangladesh',
        'aci foods': 'ACI Foods',
        'aci godrej': 'ACI Godrej',
        'kazi farms': 'Kazi Farms',
        'new hope': 'New Hope',
        'paragon feed': 'Paragon Feed',
        'quality feed': 'Quality Feed',
        'bangladesh edible oil': 'Bangladesh Edible Oil',
        'bombey': 'Bombey Sweets',
        'shwapno': 'Shwapno',
    }

    # Check known parents first
    for key, parent in known_parents.items():
        if s_lower.startswith(key):
            return parent

    # Generic: split on ' - ' and take first part
    if ' - ' in s:
        return s.split(' - ')[0].strip()

    # No delimiter: try first 1-2 words as parent
    words = s.split()
    if len(words) >= 2:
        return ' '.join(words[:2])
    return s


def build_finance_pct_lookup(alloc_df: pd.DataFrame) -> Dict[str, float]:
    """Build a parent-buyer -> weighted average finance cost % lookup from a finance cost file.
    
    Groups all factory entries under the same parent buyer and computes
    a sales-revenue-weighted average of their monthly finance cost %.
    
    For buyers WITH factoring: uses the '30-day conversion' / 'monthly finance cost' % column.
    For buyers WITHOUT factoring: uses the crowdfunding interest rate (per year / 12 for monthly).
    """
    if alloc_df is None or alloc_df.empty:
        return {}

    # Find the percentage column (30-day conversion or monthly finance cost %)
    pct_col = None
    for col in alloc_df.columns:
        col_lower = str(col).lower()
        if any(x in col_lower for x in ['30-day', 'monthly finance', 'weighted average finance cost', 'per day']):
            if 'finance' in col_lower and ('%' in str(col) or 'percent' in col_lower or '30' in col_lower):
                pct_col = col
                break
    if pct_col is None:
        for col in alloc_df.columns:
            col_lower = str(col).lower()
            if 'finance' in col_lower and '%' in str(col):
                pct_col = col
                break
    if pct_col is None:
        numeric_cols = alloc_df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) >= 2:
            pct_col = numeric_cols[-2]
        elif len(numeric_cols) >= 1:
            pct_col = numeric_cols[-1]

    if pct_col is None:
        return {}

    # Find crowdfunding interest column (per year %, used as fallback for non-factoring buyers)
    crowdfund_col = None
    for col in alloc_df.columns:
        col_lower = str(col).lower()
        if 'crowd' in col_lower and 'interest' in col_lower:
            crowdfund_col = col
            break

    # Find factoring status column
    factoring_col = None
    for col in alloc_df.columns:
        col_lower = str(col).lower().strip()
        if col_lower == 'factoring status':
            factoring_col = col
            break

    # Find sales revenue column (for weighting)
    sales_col = None
    for col in alloc_df.columns:
        col_lower = str(col).lower().strip()
        if 'sales' in col_lower and 'revenue' in col_lower:
            sales_col = col
            break
    if sales_col is None:
        for col in alloc_df.columns:
            col_lower = str(col).lower().strip()
            if 'revenue' in col_lower or 'sales' in col_lower:
                sales_col = col
                break

    def parse_pct(val):
        """Parse a percentage value from string, return as decimal or None."""
        if pd.isna(val):
            return None
        s = str(val).strip()
        if not s or s == ' ':
            return None
        try:
            return float(s.replace('%', '').replace(',', '')) / 100
        except (ValueError, TypeError):
            return None

    # Group by parent buyer
    parent_groups = {}  # parent -> list of (pct_decimal, sales_revenue)
    for _, row in alloc_df.iterrows():
        buyer_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if not buyer_name:
            continue

        # Parse percentage from main pct column
        pct_val = parse_pct(row[pct_col]) if pct_col else None

        # If no pct value, use crowdfunding interest (annual / 12 = monthly)
        if pct_val is None and crowdfund_col:
            crowdfund_annual = parse_pct(row[crowdfund_col])
            if crowdfund_annual is not None:
                pct_val = crowdfund_annual / 12  # Convert annual to monthly

        if pct_val is None:
            continue

        # Parse sales revenue for weighting
        sales_val = 0
        if sales_col and sales_col in alloc_df.columns:
            try:
                sales_val = float(str(row[sales_col]).replace(',', '').replace('%', '').strip() or '0')
            except (ValueError, TypeError):
                sales_val = 0

        parent = extract_parent_buyer(buyer_name)
        if parent not in parent_groups:
            parent_groups[parent] = []
        parent_groups[parent].append((pct_val, sales_val))

    # Compute weighted average for each parent
    lookup = {}
    for parent, entries in parent_groups.items():
        total_sales = sum(s for _, s in entries)
        if total_sales > 0:
            weighted_pct = sum(p * s for p, s in entries) / total_sales
        else:
            weighted_pct = sum(p for p, _ in entries) / len(entries)
        lookup[parent.lower()] = weighted_pct  # Already in decimal form

    return lookup


def allocate_costs_by_month_buyer(
    financial_data: dict,
    txn_df: pd.DataFrame,
    fin_alloc_on: pd.DataFrame = None,
    fin_alloc_off: pd.DataFrame = None,
    buyer_col: str = "Buyer Name",
    month_col: str = "Reporting Month",
    sales_col: str = "Sales/Revenue",
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Allocate Admin/General and Finance costs to (month, buyer) pairs.
    
    - Admin/General: allocated by profit after S&D % (operating profit %)
    - Finance: allocated by per-buyer monthly % from on/off-season files
      (grouped by parent buyer with weighted average)
    """
    fin_df = pnl_to_dataframe(financial_data)

    month_map_fin = {}
    for m in financial_data["months"]:
        norm = normalize_month(m)
        month_map_fin[norm] = m

    txn_month_map = {}
    for tm in txn_df[month_col].astype(str).str.strip().unique():
        norm = normalize_month(tm)
        txn_month_map[norm] = tm

    mapping = {}
    for txn_norm, txn_orig in txn_month_map.items():
        for fin_norm, fin_orig in month_map_fin.items():
            if fin_norm == txn_norm:
                mapping[txn_norm] = fin_orig
                break

    def get_season(month_str):
        m = str(month_str).upper()
        if any(x in m for x in ["NOV", "DEC", "JAN", "APR", "MAY"]):
            return "On-Season"
        return "Off-Season"

    # Pre-build grouped finance cost lookups (parent -> weighted avg %)
    on_lookup = build_finance_pct_lookup(fin_alloc_on) if fin_alloc_on is not None else {}
    off_lookup = build_finance_pct_lookup(fin_alloc_off) if fin_alloc_off is not None else {}

    def get_finance_pct_for_buyer(buyer_name, season, fin_alloc_on, fin_alloc_off):
        """Get monthly finance cost % for a buyer using parent-grouped weighted average."""
        lookup = on_lookup if season == "On-Season" else off_lookup
        if not lookup:
            return 0

        parent = extract_parent_buyer(buyer_name)
        parent_lower = parent.lower()

        # Direct match on parent
        if parent_lower in lookup:
            return lookup[parent_lower]

        # Fuzzy: check if any lookup key starts with parent or vice versa
        for key, val in lookup.items():
            if parent_lower.startswith(key) or key.startswith(parent_lower):
                return val

        # Last resort: partial match on first word
        first_word = parent_lower.split()[0] if parent_lower.split() else ""
        for key, val in lookup.items():
            if key.startswith(first_word) and first_word:
                return val

        return 0

    allocation = {}
    for txn_month in txn_df[month_col].astype(str).str.strip().unique():
        txn_norm = normalize_month(txn_month)
        fin_month = mapping.get(txn_norm)
        if fin_month is None:
            continue

        fin_row = financial_data["data"].get(fin_month, {})
        month_txns = txn_df[txn_df[month_col].apply(lambda x: normalize_month(str(x))) == txn_norm]

        if month_txns.empty or fin_row.get("revenue", 0) == 0:
            continue

        buyer_sales = month_txns.groupby(buyer_col)[sales_col].sum()
        total_buyer_sales = buyer_sales.sum()

        if total_buyer_sales == 0:
            continue

        admin = fin_row.get("admin_general", 0)
        revenue = fin_row.get("revenue", 0)
        season = get_season(txn_month)

        allocation[txn_month] = {}
        for buyer in buyer_sales.index:
            share = buyer_sales[buyer] / total_buyer_sales

            # Admin/General allocation by profit after S&D % (operating profit %)
            if revenue > 0:
                admin_pct = admin / revenue
            else:
                admin_pct = 0
            buyer_admin = buyer_sales[buyer] * admin_pct

            # Finance allocation: use per-buyer % from on/off-season file
            fin_pct = get_finance_pct_for_buyer(buyer, season, fin_alloc_on, fin_alloc_off)
            financing = buyer_sales[buyer] * fin_pct

            allocation[txn_month][buyer] = {
                "sales_share": share,
                "admin_general": buyer_admin,
                "financing": financing,
                "finance_pct": fin_pct,
                "season": season,
            }

    return allocation


def predict_pnl(financial_data: dict, months_ahead: int = 6) -> pd.DataFrame:
    """Linear regression forecast for full P&L following exact formulas."""
    df = pnl_to_dataframe(financial_data)
    x = np.arange(len(df)).reshape(-1, 1)

    metrics = [
        "revenue", "cogs",
        "delivery_cost", "selling_labor", "selling_packaging", "selling_others", "cod_charge",
        "branding", "call_center",
        "other_sd_exp", "discount",
        "salary_core", "salary_field", "bonus_core", "bonus_field", "perf_bonus",
        "fd_perdiem", "fd_accom", "fd_meeting", "fd_conveyance", "fd_misc",
        "legal", "membership", "rd",
        "celebration",
        "conveyance", "printing", "repair", "meals", "office",
        "internet", "mobile", "rent", "utility", "bank_mfs", "insurance",
        "misc_exp", "bd_exp", "other_exp", "postage",
        "other_income", "interest_income",
        "crowdfunding_int", "bank_int", "factoring_cost",
        "tax",
    ]

    future_x = np.arange(len(df), len(df) + months_ahead).reshape(-1, 1)
    predictions = {}
    for metric in metrics:
        y = df[metric].values
        model = LinearRegression()
        model.fit(x, y)
        pred = model.predict(future_x)
        predictions[metric] = np.maximum(pred, 0)

    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    last_num = len(df)
    future_months = []
    for i in range(months_ahead):
        n = last_num + i
        yr = 26 + n // 12
        mon = n % 12
        future_months.append(f"{month_abbr[mon]}-{yr}")

    # Build forecast following exact P&L formulas
    pred_rows = []
    for i, m in enumerate(future_months):
        rev = predictions["revenue"][i]
        cogs_val = predictions["cogs"][i]
        gp = rev - cogs_val

        # S&D
        selling_opex = (predictions["delivery_cost"][i] + predictions["selling_labor"][i] +
                        predictions["selling_packaging"][i] + predictions["selling_others"][i] +
                        predictions["cod_charge"][i])
        marketing = predictions["branding"][i] + predictions["call_center"][i]
        other_sd = predictions["other_sd_exp"][i] + predictions["discount"][i]
        total_sd = selling_opex + marketing + other_sd

        profit_after_sd = gp - total_sd

        # Admin & General
        salary = (predictions["salary_core"][i] + predictions["salary_field"][i] +
                  predictions["bonus_core"][i] + predictions["bonus_field"][i] +
                  predictions["perf_bonus"][i])
        field_visit = (predictions["fd_perdiem"][i] + predictions["fd_accom"][i] +
                       predictions["fd_meeting"][i] + predictions["fd_conveyance"][i] +
                       predictions["fd_misc"][i])
        legal_sub = predictions["legal"][i] + predictions["membership"][i] + predictions["rd"][i]
        engagement = predictions["celebration"][i]
        admin_exp = (predictions["conveyance"][i] + predictions["printing"][i] +
                     predictions["repair"][i] + predictions["meals"][i] + predictions["office"][i])
        general = (predictions["internet"][i] + predictions["mobile"][i] + predictions["rent"][i] +
                   predictions["utility"][i] + predictions["bank_mfs"][i] + predictions["insurance"][i])
        misc = (predictions["misc_exp"][i] + predictions["bd_exp"][i] +
                predictions["other_exp"][i] + predictions["postage"][i])
        total_admin = salary + field_visit + legal_sub + engagement + admin_exp + general + misc

        other_income = predictions["other_income"][i]
        net_operating = profit_after_sd - total_admin + other_income

        interest_income = predictions["interest_income"][i]
        profit_before_financing = net_operating + interest_income

        financing = (predictions["crowdfunding_int"][i] + predictions["bank_int"][i] +
                     predictions["factoring_cost"][i])
        profit_before_tax = profit_before_financing - financing
        tax = predictions["tax"][i]
        net_profit = profit_before_tax - tax

        pred_rows.append({
            "month": m, "type": "Forecast",
            "revenue": rev, "cogs": cogs_val, "gross_profit": gp,
            "total_selling_opex": selling_opex, "total_marketing": marketing,
            "total_other_sd": other_sd, "total_sd": total_sd,
            "profit_after_sd": profit_after_sd,
            "total_salary": salary, "total_field_visit": field_visit,
            "total_legal_sub": legal_sub, "total_engagement": engagement,
            "total_admin_exp": admin_exp, "total_general": general,
            "total_misc": misc, "admin_general": total_admin,
            "other_income": other_income, "net_operating_profit": net_operating,
            "interest_income": interest_income, "profit_before_financing": profit_before_financing,
            "financing": financing, "profit_before_tax": profit_before_tax,
            "tax": tax, "net_profit": net_profit,
        })

    # Historical rows
    hist_rows = []
    for _, row in df.iterrows():
        hist_rows.append({
            "month": row["month"], "type": "Historical",
            "revenue": row["revenue"], "cogs": row["cogs"], "gross_profit": row["gross_profit"],
            "total_selling_opex": row["total_selling_opex"], "total_marketing": row["total_marketing"],
            "total_other_sd": row["total_other_sd"], "total_sd": row["total_sd"],
            "profit_after_sd": row["profit_after_sd"],
            "total_salary": row["total_salary"], "total_field_visit": row["total_field_visit"],
            "total_legal_sub": row["total_legal_sub"], "total_engagement": row["total_engagement"],
            "total_admin_exp": row["total_admin_exp"], "total_general": row["total_general"],
            "total_misc": row["total_misc"], "admin_general": row["admin_general"],
            "other_income": row["other_income"], "net_operating_profit": row["net_operating_profit"],
            "interest_income": row["interest_income"], "profit_before_financing": row["profit_before_financing"],
            "financing": row["financing"], "profit_before_tax": row["profit_before_tax"],
            "tax": row["tax"], "net_profit": row["net_profit"],
        })

    return pd.DataFrame(hist_rows + pred_rows)


def predict_by_buyer(
    financial_data: dict,
    txn_df: pd.DataFrame,
    months_ahead: int = 6,
    buyer_col: str = "Buyer Name",
    month_col: str = "Reporting Month",
    sales_col: str = "Sales/Revenue",
) -> Dict[str, pd.DataFrame]:
    """Predict P&L at buyer level."""
    overall_forecast = predict_pnl(financial_data, months_ahead)
    hist = overall_forecast[overall_forecast["type"] == "Historical"].copy()
    fore = overall_forecast[overall_forecast["type"] == "Forecast"].copy()

    buyer_sales_history = txn_df.groupby(buyer_col)[sales_col].sum()
    total_history_sales = buyer_sales_history.sum()
    buyer_shares = (buyer_sales_history / total_history_sales).to_dict() if total_history_sales else {}

    fin_df = pnl_to_dataframe(financial_data)
    total_fin_admin = fin_df["admin_general"].sum()
    total_fin_financing = fin_df["financing"].sum()

    buyer_predictions = {}
    for buyer, share in buyer_shares.items():
        bdf = fore.copy()
        bdf["buyer"] = buyer
        bdf["sales_share"] = share

        bdf["revenue"] = bdf["revenue"] * share
        bdf["cogs"] = bdf["cogs"] * share
        bdf["gross_profit"] = bdf["revenue"] - bdf["cogs"]
        bdf["total_selling_opex"] = bdf["total_selling_opex"] * share
        bdf["total_marketing"] = bdf["total_marketing"] * share
        bdf["total_other_sd"] = bdf["total_other_sd"] * share
        bdf["total_sd"] = bdf["total_sd"] * share
        bdf["profit_after_sd"] = bdf["gross_profit"] - bdf["total_sd"]
        bdf["total_salary"] = bdf["total_salary"] * share
        bdf["total_field_visit"] = bdf["total_field_visit"] * share
        bdf["total_legal_sub"] = bdf["total_legal_sub"] * share
        bdf["total_engagement"] = bdf["total_engagement"] * share
        bdf["total_admin_exp"] = bdf["total_admin_exp"] * share
        bdf["total_general"] = bdf["total_general"] * share
        bdf["total_misc"] = bdf["total_misc"] * share
        bdf["admin_general"] = total_fin_admin * share
        bdf["other_income"] = bdf["other_income"] * share
        bdf["net_operating_profit"] = bdf["profit_after_sd"] - bdf["admin_general"] + bdf["other_income"]
        bdf["interest_income"] = bdf["interest_income"] * share
        bdf["profit_before_financing"] = bdf["net_operating_profit"] + bdf["interest_income"]
        bdf["financing"] = total_fin_financing * share
        bdf["profit_before_tax"] = bdf["profit_before_financing"] - bdf["financing"]
        bdf["tax"] = bdf["tax"] * share
        bdf["net_profit"] = bdf["profit_before_tax"] - bdf["tax"]
        buyer_predictions[buyer] = bdf

    return buyer_predictions


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
