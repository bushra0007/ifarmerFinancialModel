import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from tabulate import tabulate


@dataclass
class HistoricalData:
    periods: List[str]
    revenue: List[float]
    cost_of_goods_sold: List[float]
    operating_expenses: List[float]
    interest_expense: List[float] = field(default_factory=list)
    tax_rate: float = 0.25

    def __post_init__(self):
        n = len(self.periods)
        if not self.interest_expense:
            self.interest_expense = [0.0] * n


class ProfitLossPredictor:
    def __init__(self, data: HistoricalData):
        self.data = data
        self.n_periods = len(data.periods)
        self.x = np.arange(self.n_periods).reshape(-1, 1)

    def _predict_trend(self, values: List[float], future_periods: int) -> np.ndarray:
        from sklearn.linear_model import LinearRegression

        model = LinearRegression()
        model.fit(self.x, values)
        future_x = np.arange(self.n_periods, self.n_periods + future_periods).reshape(-1, 1)
        predictions = model.predict(future_x)
        return np.maximum(predictions, 0)

    def predict(self, future_periods: int = 4, period_labels: Optional[List[str]] = None) -> pd.DataFrame:
        if period_labels is None:
            last_period = self.data.periods[-1]
            period_labels = [f"Forecast {i+1}" for i in range(future_periods)]

        revenue_pred = self._predict_trend(self.data.revenue, future_periods)
        cogs_pred = self._predict_trend(self.data.cost_of_goods_sold, future_periods)
        opex_pred = self._predict_trend(self.data.operating_expenses, future_periods)
        interest_pred = self._predict_trend(self.data.interest_expense, future_periods)

        gross_profit = revenue_pred - cogs_pred
        operating_income = gross_profit - opex_pred
        ebt = operating_income - interest_pred
        taxes = np.maximum(ebt * self.data.tax_rate, 0)
        net_income = ebt - taxes

        all_periods = self.data.periods + period_labels
        all_revenue = self.data.revenue + revenue_pred.tolist()
        all_cogs = self.data.cost_of_goods_sold + cogs_pred.tolist()
        all_gross = [r - c for r, c in zip(self.data.revenue, self.data.cost_of_goods_sold)] + gross_profit.tolist()
        all_opex = self.data.operating_expenses + opex_pred.tolist()
        all_op_income = [g - o for g, o in zip(
            [r - c for r, c in zip(self.data.revenue, self.data.cost_of_goods_sold)],
            self.data.operating_expenses
        )] + operating_income.tolist()
        all_interest = self.data.interest_expense + interest_pred.tolist()
        hist_op_inc = [g - o for g, o in zip(
            [r - c for r, c in zip(self.data.revenue, self.data.cost_of_goods_sold)],
            self.data.operating_expenses
        )]
        all_ebt = [o - i for o, i in zip(hist_op_inc, self.data.interest_expense)] + ebt.tolist()
        all_tax = [max(e * self.data.tax_rate, 0) for e in all_ebt[:self.n_periods]] + taxes.tolist()
        all_net = [e - t for e, t in zip(all_ebt[:self.n_periods], all_tax[:self.n_periods])] + net_income.tolist()

        df = pd.DataFrame({
            "Period": all_periods,
            "Revenue": all_revenue,
            "COGS": all_cogs,
            "Gross Profit": all_gross,
            "Operating Expenses": all_opex,
            "Operating Income": all_op_income,
            "Interest Expense": all_interest,
            "Earnings Before Tax": all_ebt,
            "Tax": all_tax,
            "Net Income": all_net,
        })

        df["Type"] = ["Historical"] * self.n_periods + ["Forecast"] * future_periods
        return df

    def format_currency(self, value: float) -> str:
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:,.2f}M"
        elif abs(value) >= 1_000:
            return f"${value/1_000:,.2f}K"
        return f"${value:,.2f}"

    def print_report(self, future_periods: int = 4, period_labels: Optional[List[str]] = None):
        df = self.predict(future_periods, period_labels)

        print("\n" + "=" * 80)
        print("PROFIT & LOSS STATEMENT - HISTORICAL & PREDICTIVE")
        print("=" * 80 + "\n")

        headers = list(df.columns[:-1])
        rows = []
        for _, row in df.iterrows():
            formatted_row = [row["Period"]]
            for col in headers[1:]:
                formatted_row.append(self.format_currency(row[col]))
            if row["Type"] == "Forecast":
                formatted_row[0] = f"*{formatted_row[0]}"
            rows.append(formatted_row)

        print(tabulate(rows, headers=headers, tablefmt="grid", stralign="right"))

        hist = df[df["Type"] == "Historical"]
        fore = df[df["Type"] == "Forecast"]

        print("\n" + "-" * 50)
        print("SUMMARY")
        print("-" * 50)
        print(f"Historical Avg Revenue:     {self.format_currency(hist['Revenue'].mean())}")
        print(f"Forecast Avg Revenue:       {self.format_currency(fore['Revenue'].mean())}")
        print(f"Revenue Growth Rate:        {((fore['Revenue'].mean() / hist['Revenue'].mean()) - 1) * 100:.1f}%")
        print(f"Historical Avg Net Income:  {self.format_currency(hist['Net Income'].mean())}")
        print(f"Forecast Avg Net Income:    {self.format_currency(fore['Net Income'].mean())}")
        print(f"Net Profit Margin (Hist):   {hist['Net Income'].mean() / hist['Revenue'].mean() * 100:.1f}%")
        print(f"Net Profit Margin (Fore):   {fore['Net Income'].mean() / fore['Revenue'].mean() * 100:.1f}%")
        print("\n* Forecast values")
        print()


def main():
    historical = HistoricalData(
        periods=["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"],
        revenue=[500_000, 520_000, 540_000, 560_000, 580_000, 610_000, 640_000, 670_000],
        cost_of_goods_sold=[250_000, 260_000, 270_000, 280_000, 290_000, 305_000, 320_000, 335_000],
        operating_expenses=[120_000, 125_000, 130_000, 135_000, 140_000, 145_000, 150_000, 155_000],
        interest_expense=[5_000, 5_000, 5_000, 5_000, 5_000, 5_000, 5_000, 5_000],
        tax_rate=0.25
    )

    predictor = ProfitLossPredictor(historical)
    predictor.print_report(
        future_periods=4,
        period_labels=["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"]
    )


if __name__ == "__main__":
    main()
