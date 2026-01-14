import pandas as pd
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://www.nepalstock.com/todaysprice/export"
try:
    df = pd.read_csv(url)
    print("Columns:", list(df.columns))
    print("\nFirst 3 rows:")
    print(df.head(3))
except Exception as e:
    print(f"Error: {e}")
