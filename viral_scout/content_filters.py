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
    협찬/광고성 콘텐츠 감지 (약화 버전)
    
    명시적 협찬 키워드만 체크 (AI 판단 제거)
    - 이유: AI 판단은 느리고 오탐(false positive)이 많음
    - 진짜 고객 리뷰도 긍정적이면 협찬으로 오인됨
    
    Returns:
        bool: True면 명확한 협찬글 (필터링 대상)
    """
    # 명시적 협찬 키워드만 확인 (AI 판단 제거)
    full_text = title + content[:500]  # 본문 전체 대신 앞부분만 체크
    
    for keyword in SPONSORED_KEYWORDS:
        if keyword in full_text:
            return True
    
    # AI 판단 제거 - 너무 많은 정상 리뷰를 차단함
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




def remove_hashtags(text):
    """
    텍스트에서 해시태그 제거
    """
    import re
    # Remove hashtags (한글/영문/숫자)
    text = re.sub(r'#[\w가-힣]+', '', text)
    return text.strip()


# 사용자 지정 핵심 키워드 목록 (J열용)
CORE_KEYWORDS = [
    "보양대첩", "건강백서", "밥이보약", "듀먼", "수입",
    "강아지", "고양이", "기호", "소화", "변",
    "기력", "활력", "식욕", "설사", "거부"
]

# 경쟁사 목록 (K열용)
COMPETITORS = [
    "건강백서", "밥이보약", "듀먼", "국개대표",
    "퓨리나", "힐스", "로얄캐닌"
]


def extract_keywords_hybrid(title, content):
    """
    핵심 키워드 추출 (J열: 핵심연관키워드)
    지정된 키워드 목록에서만 매칭
    
    Returns:
        str: 콤마로 구분된 키워드 문자열
    """
    found_keywords = []
    full_text = (title + " " + content[:1000])
    
    for keyword in CORE_KEYWORDS:
        if keyword in full_text:
            found_keywords.append(keyword)
    
    return ", ".join(found_keywords) if found_keywords else ""


def extract_competitors(title, content):
    """
    경쟁사 언급 추출 (K열: 경쟁사언급)
    지정된 경쟁사 목록에서만 매칭
    
    Returns:
        str: 콤마로 구분된 경쟁사 문자열
    """
    found_competitors = []
    full_text = (title + " " + content[:1000])
    
    for competitor in COMPETITORS:
        if competitor in full_text:
            found_competitors.append(competitor)
    
    return ", ".join(found_competitors) if found_competitors else ""


def analyze_cafe_content(title, content):
    """
    카페 게시글 AI 요약 (본문 요약만, 키워드는 별도 함수)
    
    Returns:
        dict: {"요약": "..."}
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        # API 없으면 본문 첫 100자 반환
        clean_content = remove_hashtags(content)
        return {"요약": clean_content[:100] if clean_content else title[:100]}
    
    try:
        # 해시태그 제거
        clean_title = remove_hashtags(title)
        clean_content = remove_hashtags(content)
        
        # 짧은 프롬프트 (토큰 절약)
        prompt = f"""다음 글을 100자 이내로 요약:

제목: {clean_title}
본문: {clean_content[:300]}

요약만 작성 (해시태그 제외):"""

        ai_response = call_ai_api(prompt, max_tokens=100)
        summary = ai_response.strip()[:100]
        
        return {"요약": summary or clean_content[:100]}
    
    except Exception as e:
        print(f"      ⚠️ AI 요약 실패: {e}")
        clean_content = remove_hashtags(content)
        return {"요약": clean_content[:100] if clean_content else title[:100]}


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
