import pandas as pd

df = pd.read_csv("data/processed/barbados.csv")

print("likely_speech:")
print(df["likely_speech"].value_counts())
print()
print("content_type:")
print(df["content_type"].value_counts())
print()

for i, row in df.iterrows():
    print(f"--- {row['title']} ({row['date']}) ---")
    print("Text length:", len(str(row["full_text"])))
    print(str(row["full_text"])[:200])
    print()