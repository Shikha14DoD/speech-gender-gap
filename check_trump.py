import pandas as pd


df = pd.read_csv("data/processed/trump.csv")
sample = df.sample(3, random_state=1)
for i, row in sample.iterrows():
    print(f"--- {row['title'][:80]} ({row['date']}) ---")
    print("Length:", len(str(row["full_text"])))
    print(str(row["full_text"])[:150])
    print()
    
df = pd.read_csv("data/processed/trump.csv")
print(df["content_type"].value_counts())

df = pd.read_csv("data/processed/trump.csv")
print(df[df["likely_speech"] == "maybe"]["title"].head(15).to_string())