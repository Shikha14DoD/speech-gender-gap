import pandas as pd

df = pd.read_csv("data/processed/slovenia.csv")
has_president = df["title"].str.contains("President", case=False, na=False)
print("Rows with 'President' in title:", has_president.sum(), "of", len(df))
print()
print(df[has_president]["likely_speech"].value_counts())