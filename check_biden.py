import pandas as pd

df = pd.read_csv("data/processed/biden.csv")
sample = df.sample(4, random_state=1)
for i, row in sample.iterrows():
    print(f"--- {row['title'][:80]} ({row['date']}) ---")
    print("Length:", len(str(row["full_text"])))
    print(str(row["full_text"])[:150])
    print()