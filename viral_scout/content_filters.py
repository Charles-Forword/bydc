"""
AI 기반 콘텐츠 필터
- 협찬/광고성 리뷰 감지
- 진정한 질문글 판별
- 댓글 감성 분석
"""

import requests
import json
from config import AI_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY


# 협찬 감지 키워드
SPONSORED_KEYWORDS = [
    "협찬", "지원", "제공받", "무상", "체험단", 
    "이벤트 당첨", "리뷰어", "서포터즈", "앰버서더",
    "원고료", "광고", "PR", "프로모션"
]

# 질문 패턴
QUESTION_PATTERNS = [
    "어떤가요", "괜찮나요", "추천", "어떻게", "어때요",
    "먹여도 될까요", "괜찮을까요", "고민", "궁금",
    "문의", "질문", "여쭤", "도와주세요"
]


def detect_sponsored_content(title, content):
    """
    협찬/광고성 콘텐츠 감지
    
    Returns:
        bool: True면 협찬글 (필터링 대상)
    """
    # 1단계: 키워드 확인
    full_text = title + content
    for keyword in SPONSORED_KEYWORDS:
        if keyword in full_text:
            return True
    
    # 2단계: AI 진정성 판단
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return False  # API 키 없으면 키워드만으로 판단
    
    try:
        prompt = f"""다음 글이 협찬/광고성 리뷰인지 판단해주세요:

제목: {title}
본문: {content[:500]}

판단 기준:
1. 지나치게 일방적으로 긍정적
2. 구매 유도 문구 포함
3. 제품 특징만 나열 (경험 없음)
4. 할인 링크, 쿠폰 제공

YES 또는 NO로만 답변:"""

        ai_response = call_ai_api(prompt, max_tokens=10)
        
        return "YES" in ai_response.upper()
    
    except Exception as e:
        print(f"      ⚠️ AI 협찬 감지 실패: {e}")
        return False


def is_genuine_question(title, content):
    """
    진짜 질문글인지 판단
    
    Returns:
        bool: True면 질문글 (우선순위 높음)
    """
    # 1단계: 패턴 확인
    full_text = title + content[:200]
    
    # 제목에 물음표
    has_question_mark = "?" in title or "?" in title
    
    # 질문 패턴
    has_question_pattern = any(pattern in full_text for pattern in QUESTION_PATTERNS)
    
    if has_question_mark and has_question_pattern:
        return True
    
    # 2단계: AI 판단 (경계선 케이스)
    if not has_question_mark or not GEMINI_API_KEY:
        return False
    
    try:
        prompt = f"""다음 글이 제품에 대한 진짜 질문글인지 판단해주세요:

제목: {title}
본문: {content[:300]}

진짜 질문이란:
- 구매 전 고민/문의
- 사용 경험 물어봄
- 추천 요청

YES 또는 NO로만 답변:"""

        ai_response = call_ai_api(prompt, max_tokens=10)
        
        return "YES" in ai_response.upper()
    
    except:
        return False


def analyze_comment_sentiment(comment_text):
    """
    댓글 감성 분석
    
    Returns:
        str: "긍정", "부정", "중립"
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        # 간단한 키워드 기반 폴백
        positive_words = ["좋아요", "만족", "추천", "괜찮", "좋네요", "굿"]
        negative_words = ["별로", "실망", "안좋", "설사", "안맞", "후회", "최악"]
        
        pos_count = sum(1 for w in positive_words if w in comment_text)
        neg_count = sum(1 for w in negative_words if w in comment_text)
        
        if neg_count > pos_count:
            return "부정"
        elif pos_count > neg_count:
            return "긍정"
        else:
            return "중립"
    
    try:
        prompt = f"""다음 댓글의 감성을 분석하세요:

"{comment_text}"

'긍정', '부정', '중립' 중 하나로만 답변:"""

        ai_response = call_ai_api(prompt, max_tokens=10)
        
        if "부정" in ai_response:
            return "부정"
        elif "긍정" in ai_response:
            return "긍정"
        else:
            return "중립"
    
    except:
        return "중립"


def analyze_comments_batch(comments_list):
    """
    댓글 목록 일괄 분석
    
    Returns:
        dict: 감성 통계 + 주요 부정 의견
    """
    if not comments_list:
        return {
            "긍정_개수": 0,
            "부정_개수": 0,
            "중립_개수": 0,
            "부정_예시": [],
            "주요_불만": ""
        }
    
    positive = []
    negative = []
    neutral = []
    
    for comment in comments_list:
        sentiment = analyze_comment_sentiment(comment['content'])
        
        comment['sentiment'] = sentiment
        
        if sentiment == "긍정":
            positive.append(comment)
        elif sentiment == "부정":
            negative.append(comment)
        else:
            neutral.append(comment)
    
    # 부정 의견 주요 이슈 추출
    key_issues = extract_key_issues(negative) if negative else ""
    
    return {
        "긍정_개수": len(positive),
        "부정_개수": len(negative),
        "중립_개수": len(neutral),
        "부정_예시": [c['content'][:50] for c in negative[:3]],
        "주요_불만": key_issues
    }


def extract_key_issues(negative_comments):
    """
    부정 댓글에서 주요 이슈 추출
    """
    if not negative_comments or (not GEMINI_API_KEY and not OPENAI_API_KEY):
        return ""
    
    try:
        comments_text = "\n- ".join([c['content'][:100] for c in negative_comments[:5]])
        
        prompt = f"""다음 부정적 댓글들의 공통 불만사항을 한 줄로 요약:

{comments_text}

핵심 이슈만 간단히 (예: 알러지 반응, 기호성 낮음):"""

        return call_ai_api(prompt, max_tokens=50)
    
    except:
        return ""


def call_ai_api(prompt, max_tokens=100):
    """AI API 호출 (Gemini 또는 OpenAI)"""
    
    if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens
            }
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            raise Exception(f"Gemini API error: {response.status_code}")
    
    elif AI_PROVIDER == "openai" and OPENAI_API_KEY:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            raise Exception(f"OpenAI API error: {response.status_code}")
    
    else:
        raise Exception("No AI API key configured")




def analyze_cafe_content(title, content):
    """
    카페 게시글 AI 분석 (요약 + 주요내용 키워드 추출)
    
    Returns:
        dict: {"요약": "...", "주요내용": "키워드1, 키워드2, ..."}
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return {"요약": title[:100], "주요내용": ""}
    
    try:
        prompt = f"""다음 카페 게시글을 분석해주세요:

제목: {title}
본문: {content[:800]}

다음 형식으로만 답변:
요약: (100자 이내로 핵심 요약)
주요내용: (반려동물/제품 관련 키워드만 콤마로 나열, 예: 강아지, 식사거부, 설사, 보양대첩, 워밍)"""

        ai_response = call_ai_api(prompt, max_tokens=200)
        
        # 응답 파싱
        summary = ""
        keywords = ""
        
        for line in ai_response.split('\n'):
            if line.startswith("요약:"):
                summary = line.replace("요약:", "").strip()[:100]
            elif line.startswith("주요내용:"):
                keywords = line.replace("주요내용:", "").strip()
        
        return {
            "요약": summary or title[:100],
            "주요내용": keywords
        }
    
    except Exception as e:
        print(f"      ⚠️ AI 분석 실패: {e}")
        return {"요약": title[:100], "주요내용": ""}


if __name__ == "__main__":
    # 테스트
    print("=== 협찬 감지 테스트 ===")
    test1 = detect_sponsored_content(
        "[협찬] 보양대첩 워밍 후기",
        "이번에 협찬받아 사용해봤어요. 정말 좋네요!"
    )
    print(f"협찬글 감지: {test1}")  # True
    
    print("\n=== 질문글 판별 테스트 ===")
    test2 = is_genuine_question(
        "보양대첩 어떤가요?",
        "우리 강아지한테 먹여도 괜찮을까요? 알러지가 있는데..."
    )
    print(f"질문글 판별: {test2}")  # True
    
    print("\n=== 댓글 감성 분석 테스트 ===")
    test3 = analyze_comment_sentiment("우리 아이는 설사가 나왔어요...")
    print(f"감성: {test3}")  # 부정
