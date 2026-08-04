import pandas as pd
from src.translate_helper import _chunk_text, CHUNK_CHAR_LIMIT

df = pd.read_csv("data/processed/xipeoplecn.csv")

# Grab the first row that's still failed
def is_failed(text):
    if not isinstance(text, str) or not text.strip():
        return True
    return "TRANSLATION FAILED" in text

failed_row = df[df["full_text_en"].apply(is_failed)].iloc[0]
text = str(failed_row["full_text"])

print("Title:", failed_row["title"])
print("Total text length:", len(text))

chunks = _chunk_text(text)
print(f"\nSplit into {len(chunks)} chunks:")
for i, c in enumerate(chunks, 1):
    print(f"  Chunk {i}: {len(c)} characters")