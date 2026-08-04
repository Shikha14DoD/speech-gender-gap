import pandas as pd
from deep_translator import GoogleTranslator

df = pd.read_csv("data/processed/xipeoplecn.csv")

def is_failed(text):
    if not isinstance(text, str) or not text.strip():
        return True
    return "TRANSLATION FAILED" in text

failed_row = df[df["full_text_en"].apply(is_failed)].iloc[0]
text = str(failed_row["full_text"])

print("Text length:", len(text))
print("Attempting direct translation...")

try:
    translator = GoogleTranslator(source="zh-CN", target="en")
    result = translator.translate(text)
    print("SUCCESS, length of result:", len(result) if result else 0)
except Exception as e:
    print("FAILED:", repr(e))