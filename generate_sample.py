import pandas as pd
import numpy as np

np.random.seed(42)

buyers = ["ABC Corp", "XYZ Ltd", "Global Trading", "National Imports", "Prime Distributors"]
products = ["Product A", "Product B", "Product C", "Product D"]
months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08"]

rows = []
for i in range(100):
    buyer = np.random.choice(buyers)
    product = np.random.choice(products)
    month = np.random.choice(months)
    qty = np.random.randint(50, 500)
    unit_price = np.random.uniform(80, 150)
    sales = qty * unit_price
    cogs = sales * np.random.uniform(0.45, 0.55)
    sd = sales * np.random.uniform(0.08, 0.15)
    gp = sales - cogs
    op = gp - sd

    rows.append({
        "Sales Date": f"2025-{np.random.randint(1,13):02d}-{np.random.randint(1,29):02d}",
        "Buyer Name": buyer,
        "Product Name": product,
        "Reporting Month": month,
        "Gross Quantity": qty,
        "Receive Quantity KG": qty * np.random.uniform(0.95, 1.0),
        "Unit Price2": round(unit_price, 2),
        "Net Sales Amount": round(sales, 2),
        "Sales/Revenue": round(sales, 2),
        "Cost Of Product": round(cogs * 0.8, 2),
        "Cogs": round(cogs, 2),
        "Total Selling Opex(F)": round(sd, 2),
        "Profit .After - S& D": round(op, 2),
        "Total Cogs": round(cogs, 2),
        "GP": round(gp, 2),
        "GP %": round(gp / sales * 100, 2),
    })

df = pd.DataFrame(rows)
df.to_csv("sample_data.csv", index=False)
print(f"Generated {len(df)} sample transactions")
print(f"Total Sales: {df['Sales/Revenue'].sum():,.2f}")
print(f"Total COGS: {df['Cogs'].sum():,.2f}")
print(f"Buyers: {df['Buyer Name'].unique()}")
