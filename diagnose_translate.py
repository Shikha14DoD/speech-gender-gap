from deep_translator import GoogleTranslator
import time

test_texts = [
    "你好，世界",
    "中国经济发展",
    "习近平在讲话中强调了改革开放的重要性。",
]

for i, text in enumerate(test_texts, 1):
    print(f"\nAttempt {i}: {text}")
    try:
        translator = GoogleTranslator(source="zh-CN", target="en")
        result = translator.translate(text)
        print("SUCCESS:", result)
    except Exception as e:
        print("FAILED:", repr(e))
    time.sleep(3)