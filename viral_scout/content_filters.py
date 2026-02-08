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

# 경쟁사/브랜드 목록 (J열/K열용)
# 한국 주요 사료/간식 브랜드 (약 50개)
COMPETITORS = [
    "보양대첩", "로얄캐닌", "힐스", "퓨리나", "네추럴코어", 
    "건강백서", "밥이보약", "듀먼", "하림", "더리얼", 
    "시저", "ANF", "오리젠", "아카나", "지위픽", 
    "K9", "스텔라앤츄이스", "빅독", "닥터맘마", "레이앤이본", 
    "도거박스", "웰츠", "나우", "닥터독", 
    "몽슈슈", "페디그리", "프로플랜", "이나바", "템테이션", 
    "위스카스", "쉐바", "짐펫", "조공", "잇츄", 
    "핏펫", "국개대표", "알모네이쳐", "윔지스", "그리니즈",
    "포켄스", "브리지테일", "페스룸", "바잇미", "릴리스키친",
    "세니메드", "스페시픽", "벨릭서", "하이포알러제닉",
    # 짧은 브랜드명 보완
    "고 네추럴", "고 사료", "Go! Solutions", "Go 사료"
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


def extract_brands_regex(text):
    """
    텍스트에서 브랜드명 추출 (Regex/List 기반)
    """
    found_brands = set()
    for brand in COMPETITORS:
        if brand in text:
            found_brands.add(brand)
    return list(found_brands)

def merge_and_sort_brands(ai_brands_str, text):
    """
    AI 추출 브랜드와 Regex 추출 브랜드를 병합하고 정렬
    규칙: '보양대첩' 최우선, 그 외에는 발견된 순서 또는 가나다순
    """
    # 1. Regex로 확실한 브랜드 찾기
    regex_brands = extract_brands_regex(text)
    
    # 2. AI 결과를 리스트로 변환
    ai_brands = [b.strip() for b in ai_brands_str.split(',') if b.strip()]
    
    # 3. 병합 (Set으로 중복 제거)
    all_brands = set(regex_brands + ai_brands)
    
    # 4. 정렬
    sorted_brands = sorted(list(all_brands))
    
    # 5. 보양대첩 최우선 처리
    if "보양대첩" in sorted_brands:
        sorted_brands.remove("보양대첩")
        sorted_brands.insert(0, "보양대첩")
        
    return ", ".join(sorted_brands)

def extract_competitors(title, content):
    """(Deprecated) Legacy function, kept for compatibility if needed"""
    return merge_and_sort_brands("", title + " " + content)


def clean_ai_response(text):
    """
    AI 응답에서 마크다운 기호(**), 이모지 등 제거
    """
    import re
    # ** 마크다운 제거
    text = text.replace("**", "")
    text = text.replace("*", "")
    # 이모지 제거 (유니코드 이모지 범위)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # Emoticons
        u"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
        u"\U0001F680-\U0001F6FF"  # Transport and Map
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        u"\U00002702-\U000027B0"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    # 불필요한 공백 정리
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
        
        # 명확한 프롬프트 (반려동물 사료 관련 요약)
        # 명확한 프롬프트 (반려동물 사료 관련 요약)
        prompt = f"""반려동물 사료 관련 카페 글을 요약해주세요.

제목: {clean_title}
본문: {clean_content[:500]}

규칙:
1. 이 글이 "강아지" 또는 "고양이"와 직접적으로 관련된 글인지 가장 먼저 판단하세요. (소라게, 햄스터, 사람 음식 등은 False)
3. 전체 내용을 '음슴체'(~함, ~임)로 끝나는 완전한 문장으로 작성 (권장 100자, 최대 150자)
4. 마크다운(**), 이모지, 해시태그 사용 금지
5. "요약:", "결론:" 같은 라벨 없이 바로 내용만 작성
6. '브랜드언급'에는 본문에 언급된 모든 사료/간식 브랜드명을 쉼표로 구분해 나열하세요. 단, "보양대첩"이 포함되어 있다면 반드시 맨 처음에 적으세요. (예: 보양대첩, 로얄캐닌, 건강백서)

아래 JSON 형식으로만 응답 (다른 말 없이 JSON만):
{{
  "반려동물관련": true 또는 false,
  "요약": "핵심 내용 요약 (음슴체)",
  "브랜드언급": "보양대첩을 최우선으로 한 브랜드 목록 (없으면 빈칸)"
}}"""

        ai_response = call_ai_api(prompt, max_tokens=200)
        
        # 디버깅: AI 원본 응답 출력
        print(f"      📝 AI 원본 응답: {ai_response[:100]}...")
        
        # JSON 파싱 시도
        try:
            if "```" in ai_response:
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
            
            analysis = json.loads(ai_response)
            
            # 마크다운, 이모지 제거 후처리
            summary = clean_ai_response(analysis.get("요약", ""))[:150]
            is_relevant = analysis.get("반려동물관련", True)
            
            # 브랜드 언급: AI 결과 + Regex 결과 병합
            ai_brand_mention = clean_ai_response(analysis.get("브랜드언급", ""))
            final_brand_mention = merge_and_sort_brands(ai_brand_mention, title + " " + content)
            
            # 빈 응답이면 폴백
            if not summary or len(summary) < 10:
                print(f"      ⚠️ AI 요약 너무 짧음, 본문으로 대체")
                summary = clean_content[:100] if clean_content else title[:100]
                
            return {
                "요약": summary, 
                "반려동물관련": is_relevant,
                "브랜드언급": final_brand_mention
            }
            
        except Exception as json_err:
            print(f"      ⚠️ JSON 파싱 실패: {json_err}")
            # 파싱 실패 시 텍스트라도 건지기 위한 폴백
            clean_text = clean_ai_response(ai_response)
            
            # 폴백 상황에서도 Regex로 브랜드 추출 시도
            fallback_brands = extract_brands_regex(title + " " + content)
            fallback_brand_str = ", ".join(sorted(fallback_brands))
            
            return {
                "요약": clean_text[:100], 
                "반려동물관련": True,
                "브랜드언급": fallback_brand_str
            }
    
    except Exception as e:
        print(f"      ⚠️ AI 요약 실패: {e}")
        clean_content = remove_hashtags(content)
        return {"요약": clean_content[:100] if clean_content else title[:100]}



def analyze_daily_summary(blog_rows, cafe_rows):
    """
    일일 수집 데이터 통합 분석 (전문가 모드)
    
    Args:
        blog_rows: 블로그 수집 데이터 리스트
        cafe_rows: 카페 수집 데이터 리스트
        
    Returns:
        str: 전문가 분석 리포트 텍스트
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return "AI API가 설정되지 않아 통합 분석을 수행할 수 없습니다."

    # 데이터 요약
    total_count = len(blog_rows) + len(cafe_rows)
    if total_count == 0:
        return "수집된 데이터가 없습니다."
        
    # 제목과 요약만 추출해서 프롬프트 구성
    content_summary = "【블로그 데이터】\n"
    for row in blog_rows[:15]:  # 토큰 제한 고려 상위 15개
        content_summary += f"- {row[2]} (요약: {row[5]})\n"
        
    content_summary += "\n【카페 데이터】\n"
    for row in cafe_rows[:15]:  # 토큰 제한 고려 상위 15개
        content_summary += f"- {row[3]} (요약: {row[6]})\n"
        
    prompt = f"""당신은 반려동물 식품 브랜드 '보양대첩'의 마케팅 전략 전문가입니다.
오늘 수집된 블로그와 카페의 '인기 게시글(관련도순)' 데이터를 분석하고 전략을 제안하세요.

[수집된 데이터 요약]
{content_summary}

---
[분석 요구사항]
다음 3가지 관점에서 예리하게 분석하여 보고해주세요. (존댓말, 각 항목별 2~3문장)

1. 🗣️ 소비자 반응 (Consumer Voice)
   - 소비자들이 느끼는 날것의 감정이나 불편함은 무엇인가?
   - 보양대첩 판매자가 놓치지 말아야 할 '액기스' 정보는?

2. 🏭 시장 트렌드 & 제조사 전략 (Market & Manufacturer)
   - 현재 시장의 흐름이나 경쟁사들의 움직임에서 포착된 패턴은?
   - 소비자들의 심리적 변화나 새로운 니즈는 무엇인가?

3. 🚀 보양대첩 마케팅 전략 (Action Plan)
   - 오늘 데이터를 바탕으로 우리는 무엇을 해야 하는가?
   - 어떻게 시장을 파고들어 성장을 만들어낼 것인가? (구체적이고 실현 가능한 제안)

[출력 형식]
## 📊 오늘의 전문가 분석 리포트

1. 🗣️ **소비자 반응**
(내용)

2. 🏭 **시장 트렌드**
(내용)

3. 🚀 **보양대첩 전략**
(내용)"""

    try:
        return call_ai_api(prompt, max_tokens=1000)
    except Exception as e:
        return f"통합 분석 생성 실패: {e}"


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
