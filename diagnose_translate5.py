import pandas as pd
from deep_translator import GoogleTranslator
import time

df = pd.read_csv("data/processed/xipeoplecn.csv")

def is_failed(text):
    if not isinstance(text, str) or not text.strip():
        return True
    return "TRANSLATION FAILED" in text

failed_row = df[df["full_text_en"].apply(is_failed)].iloc[0]
text = str(failed_row["full_text"])

for size in [700, 800, 900, 1000, 1100]:
    sample = text[:size]
    try:
        translator = GoogleTranslator(source="zh-CN", target="en")
        result = translator.translate(sample)
        print(f"size={size}: SUCCESS ({len(result) if result else 0} chars back)")
    except Exception as e:
        print(f"size={size}: FAILED - {repr(e)}")
    time.sleep(2)