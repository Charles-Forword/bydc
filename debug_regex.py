import re

def clean_ai_text(text):
    """AI 응답에서 마크다운/이모지 제거 (버그 재현용)"""
    if not text:
        return ""
    text = text.replace("**", "").replace("*", "")
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # Emoticons
        u"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
        u"\U0001F680-\U0001F6FF"  # Transport and Map
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        u"\U00002702-\U000027B0"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    return re.sub(r'\s+', ' ', text).strip()

# 테스트 케이스
samples = [
    "3개월 냥이 사료 바꿔준 뒤 1주일째 설사..",  # Row 371 Original
    "항생제 설사 40일만에 잡았네요ㅠ 사료는 유지해야할까요?",  # Row 375 Original
    "ibd설사냥이 사료영양소(조단백,조지방)에 대하여 질문있습니다", # Row 378 Original
    "안녕하세요 Hello 123 !@#"
]

print("=== Regex Bug Reproduction ===")
for s in samples:
    cleaned = clean_ai_text(s)
    print(f"Original: {s}")
    print(f"Cleaned : {cleaned}")
    print("-" * 20)
