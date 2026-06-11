import pandas as pd
from pathlib import Path

output_dir = Path("outputs/public")
output_dir.mkdir(parents=True, exist_ok=True)

data = [
    {
        "auction_year": 2024,
        "parcel_number": "00635500000200",
        "property_type": "Vacant Land",
        "minimum_bid": 28761,
        "selling_price": 599700,
        "bid_multiple": round(599700 / 28761, 2),
    },
    {
        "auction_year": 2025,
        "parcel_number": "00910700007200",
        "property_type": "Residential",
        "minimum_bid": 19318,
        "selling_price": 380400,
        "bid_multiple": round(380400 / 19318, 2),
    },
]

df = pd.DataFrame(data)

csv_path = output_dir / "sample_foreclosure_dataset.csv"
xlsx_path = output_dir / "sample_foreclosure_dataset.xlsx"

df.to_csv(csv_path, index=False)
df.to_excel(xlsx_path, index=False)

print(f"CSV written to: {csv_path}")
print(f"Excel written to: {xlsx_path}")
print()
print(df)