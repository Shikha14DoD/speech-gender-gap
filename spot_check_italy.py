import pandas as pd

df = pd.read_csv("data/processed/italy.csv")

print("=== Sample from likely_speech='yes' (should be clearly real speeches) ===")
print(df[df['likely_speech']=='yes'][['title']].sample(5, random_state=7).to_string())

print("\n=== Sample from likely_speech='maybe' (the ambiguous bucket) ===")
print(df[df['likely_speech']=='maybe'][['title']].sample(10, random_state=7).to_string())

print("\n=== Sample from content_type='Other' (least specific label) ===")
print(df[df['content_type']=='Other'][['title', 'likely_speech']].sample(10, random_state=7).to_string())