import sys
import os

# 현재 스크립트 폴더를 Python 경로에 추가 (GitHub Actions 호환)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import ssl
import datetime
import json
import urllib.request
import urllib.parse
from urllib.parse import urlparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def normalize_cafe_url(url):
    """
    네이버 카페 URL 정규화 (파라미터 제거)
    예: https://cafe.naver.com/cafe_name/1234?art=... -> https://cafe.naver.com/cafe_name/1234
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        # 네이버 카페 도메인인지 확인
        if "cafe.naver.com" in parsed.netloc:
            # path가 있으면 쿼리 파라미터 제거하고 반환
            if parsed.path and parsed.path != "/":
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        return url
    except:
        return url

# .env 파일 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv 없으면 환경변수 직접 사용

# macOS SSL 인증서 오류 해결을 위한 패치
ssl._create_default_https_context = ssl._create_unverified_context

from config import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, 
    SEARCH_KEYWORDS, DISPLAY_COUNT, SORT_MODE,
    GOOGLE_SHEET_URL, SERVICE_ACCOUNT_FILE,
    BLOG_SHEET_NAME, CAFE_SHEET_NAME,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    EXCLUDE_KEYWORDS, REQUIRED_KEYWORDS, USE_AI_FILTER, OPENAI_API_KEY,
    ENABLE_CONTENT_SCRAPING, ENABLE_AI_ANALYSIS, ANALYZE_ALL,
    ENABLE_CAFE_CRAWLING, CAFE_MAX_POSTS, PRIORITIZE_QUESTIONS, FILTER_SPONSORED, ANALYZE_COMMENTS,
    AI_PROVIDER, GEMINI_API_KEY
)


def scrape_blog_content(url):
    """네이버 블로그 본문 크롤링 (재시도 포함)"""
    if not ENABLE_CONTENT_SCRAPING:
        return ""
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            from bs4 import BeautifulSoup
            import requests
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content = soup.select_one('.se-main-container')
            if content:
                text = content.get_text(strip=True, separator=' ')[:2000]
                if len(text) > 100:
                    return text
            
            content = soup.select_one('#postViewArea')
            if content:
                text = content.get_text(strip=True, separator=' ')[:2000]
                if len(text) > 100:
                    return text
            
            paragraphs = soup.find_all(['p', 'div'], class_=lambda x: x and 'se-text' in x)
            if paragraphs:
                text = ' '.join([p.get_text(strip=True) for p in paragraphs])[:2000]
                if len(text) > 100:
                    return text
            
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return "(본문 추출 실패)"
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            print(f"      ⚠️ 크롤링 실패: {str(e)[:50]}")
            return "(본문 없음)"
    
    return "(본문 없음)"


def is_blacklisted(title):
    """제외 키워드가 제목에 있는지 확인"""
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in title:
            return True
    return False

def has_required_keyword(title):
    """필수 키워드 중 하나라도 제목에 있는지 확인"""
    for keyword in REQUIRED_KEYWORDS:
        if keyword in title:
            return True
    return False

def check_relevance_with_ai(title, description):
    """AI를 사용해 반려동물 사료 관련 글인지 판단"""
    if not USE_AI_FILTER or not OPENAI_API_KEY:
        return True
    
    try:
        import requests
        
        prompt = f"""다음 블로그 글이 "반려동물(강아지/고양이) 사료, 간식, 영양제" 관련 내용인지 판단해주세요.
사람이 먹는 음식, 한식 레시피, 맛집, 인테리어 등은 관련 없습니다.

제목: {title}
요약: {description}

답변은 "YES" 또는 "NO"로만 해주세요."""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 10
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
        else:
            return True
            
    except Exception as e:
        return True


def clean_ai_text(text):
    """AI 응답에서 마크다운/이모지 제거"""
    import re
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


def analyze_content_with_ai(title, content):
    """AI로 블로그 본문 분석하여 구조화된 인사이트 추출"""
    if not ENABLE_AI_ANALYSIS:
        return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
    
    if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
        return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
    elif AI_PROVIDER == "openai" and not OPENAI_API_KEY:
        return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
    
    if not ANALYZE_ALL and "보양대첩" not in title and "보양대첩" not in content:
        return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
    
    try:
        import requests
        import json as json_module
        
        prompt = f"""반려동물 사료 관련 블로그 글을 분석해주세요.

제목: {title}
본문: {content[:1500]}

규칙:
1. 이 글이 "강아지" 또는 "고양이"와 직접적으로 관련된 글인지 판단하세요. (소라게, 햄스터, 사람 음식 등은 False)
2. 마크다운(**), 이모지, 해시태그 사용 금지
3. 각 필드는 간결하게 작성하되, 문장이 중간에 끊기지 않도록 '다'로 끝나는 완전한 문장으로 작성하세요. (권장 100자, 최대 150자)
4. 해당 내용이 없으면 빈 문자열로 작성

아래 JSON 형식으로만 응답 (다른 말 없이 JSON만):
{{
  "반려동물관련": true 또는 false,
  "요약": "핵심 내용 3-4문장 요약 (100~150자 내외 자연스러운 매듭짓기)",
  "주요내용": "언급된 제품 특징이나 효과",
  "경쟁사언급": "언급된 경쟁 브랜드명만 (없으면 빈칸)",
  "감성": "긍정/중립/부정 중 하나",
  "액션포인트": "개선 제안사항"
}}"""

        if AI_PROVIDER == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
            }
            response = requests.post(url, json=data, timeout=15)

            if response.status_code == 200:
                result = response.json()
                ai_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"      ⚠️ Gemini 실패 ({response.status_code})")
                return {"반려동물관련": True, "요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
        
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
            data = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 600
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
            else:
                print(f"      ⚠️ OpenAI 실패 ({response.status_code})")
                return {"반려동물관련": True, "요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
        
        # JSON 파싱
        try:
            # 디버깅: AI 원본 응답 출력 (처음 200자)
            print(f"      📝 AI 원본 응답: {ai_response[:200]}...")
            
            if "```" in ai_response:
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
            
            analysis = json_module.loads(ai_response)
            # 각 필드에서 마크다운/이모지 제거
            for key in analysis:
                if isinstance(analysis[key], str):
                    analysis[key] = clean_ai_text(analysis[key])
            
            # 기본값 True 처리 (필드가 없을 경우)
            if "반려동물관련" not in analysis:
                analysis["반려동물관련"] = True
                
            return analysis
        except Exception as parse_err:
            print(f"      ⚠️ JSON 파싱 실패: {parse_err}")
            # JSON 파싱 실패 시 빈 값 반환 (이상한 텍스트 저장 방지)
            return {"반려동물관련": True, "요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
            
    except Exception as e:
        print(f"      ⚠️ AI 오류: {str(e)[:50]}")
        return {"반려동물관련": True, "요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}


def send_telegram_message(message):
    """텔레그램 메시지 발송"""
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("✅ 텔레그램 발송 성공")
        else:
            print(f"❌ 텔레그램 발송 실패: {response.status_code}")
    except Exception as e:
        print(f"❌ 텔레그램 발송 오류: {e}")

def format_date(date_str):
    """날짜 형식 변환"""
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except:
        return date_str

def get_existing_links(sheet, link_column_index):
    """
    구글 시트에서 기존 링크 목록 추출 (중복 체크용)
    
    Args:
        sheet: gspread 시트 객체
        link_column_index: 링크가 있는 열 인덱스 (0-based)
    
    Returns:
        set: 기존 링크 집합 (정규화됨)
    """
    try:
        all_values = sheet.get_all_values()
        if len(all_values) <= 1:
            return set()
        
        links = set()
        for row in all_values[1:]:
            if len(row) > link_column_index and row[link_column_index]:
                # URL 정규화하여 저장 (비교 정확도 향상)
                links.add(normalize_cafe_url(row[link_column_index]))
        return links
    except Exception as e:
        print(f"      ⚠️ 기존 링크 조회 실패: {e}")
        return set()


def load_keywords_from_sheet(spreadsheet):
    """
    [검색설정] 탭에서 검색 키워드 로드
    
    시트 구조: 
    - A1: 헤더 (예: "검색키워드") - 스킵됨
    - A2부터: 실제 키워드 나열
    
    Returns:
        list: 키워드 리스트
    """
    try:
        settings_sheet = spreadsheet.worksheet("검색설정")
        # A열 전체 읽기
        all_keywords = settings_sheet.col_values(1)
        # 1행(헤더) 제외하고 빈 값 제거
        keywords = [k.strip() for k in all_keywords[1:] if k.strip()]
        
        if keywords:
            print(f"📝 [검색설정] 탭에서 {len(keywords)}개 키워드 로드")
            for i, kw in enumerate(keywords[:5]):
                print(f"   {i+1}. {kw}")
            if len(keywords) > 5:
                print(f"   ... 외 {len(keywords)-5}개")
            return keywords
        else:
            print("⚠️ [검색설정] 탭에 키워드 없음, config.py 기본값 사용")
            return None
    except Exception as e:
        print(f"⚠️ [검색설정] 탭 불러오기 실패: {e}")
        print("   config.py 기본값 사용")
        return None

def filter_new_posts(posts, existing_links, source_type="카페"):
    """
    신규 게시글만 필터링 (중복 제외)
    
    Args:
        posts: 게시글 리스트
        existing_links: 기존 링크 집합
        source_type: "블로그" 또는 "카페"
    
    Returns:
        list: 중복 제외된 신규 게시글
    """
    new_posts = []
    for p in posts:
        raw_link = p.get('link')
        # 링크 정규화 (파라미터 제거 등)
        normalized_link = normalize_cafe_url(raw_link)
        
        if normalized_link not in existing_links:
            # 저장될 데이터도 정규화된 링크로 업데이트
            p['link'] = normalized_link
            new_posts.append(p)
            
    duplicates = len(posts) - len(new_posts)
    
    if duplicates > 0:
        print(f"   🔄 [{source_type}] 중복 {duplicates}건 제외, 신규 {len(new_posts)}건")
    
    return new_posts

def init_google_sheets():
    """구글 시트 초기화 (블로그 + 카페 별도 시트)
    
    Returns:
        tuple: (blog_sheet, cafe_sheet, spreadsheet)
    """
    try:
        if os.environ.get("GITHUB_ACTIONS"):
            print("ℹ️ GitHub Env: Creating service_account.json from secret")
            json_content = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
            
            if not json_content:
                print("❌ Error: GOOGLE_SERVICE_ACCOUNT_JSON secret is empty!")
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON secret is missing")
            
            # Base64 디코딩 시도 (JSON이 아니거나 '{'로 시작하지 않으면 Base64로 간주)
            if not json_content.strip().startswith("{"):
                try:
                    import base64
                    decoded_bytes = base64.b64decode(json_content)
                    json_content = decoded_bytes.decode('utf-8')
                    print("ℹ️ Base64 encoded secret detected and decoded.")
                except Exception as e:
                    print(f"⚠️ Base64 decode failed, using raw content: {e}")
            
            with open("service_account.json", "w") as f:
                f.write(json_content)
            
            if os.path.exists("service_account.json"):
                file_size = os.path.getsize('service_account.json')
                print(f"✅ service_account.json created (size: {file_size} bytes)")
                
                # JSON 유효성 검사 및 필수 키 체크
                try:
                    import json as json_module
                    with open("service_account.json", "r") as check_file:
                        sa_data = json_module.load(check_file)
                    
                    required_keys = ["type", "project_id", "private_key", "client_email", "client_id"]
                    missing_keys = [k for k in required_keys if k not in sa_data]
                    
                    if missing_keys:
                        print(f"❌ service_account.json에 필수 키 누락: {missing_keys}")
                        print(f"   현재 키: {list(sa_data.keys())}")
                    else:
                        print(f"✅ service_account.json 필수 키 확인 완료")
                        print(f"   client_email: {sa_data.get('client_email', 'N/A')}")
                except Exception as json_err:
                    print(f"❌ service_account.json JSON 파싱 실패: {json_err}")
            else:
                print("❌ Failed to create service_account.json")

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(GOOGLE_SHEET_URL)
        
        # 블로그 시트 (기존)
        try:
            blog_sheet = spreadsheet.worksheet(BLOG_SHEET_NAME)
        except:
            blog_sheet = spreadsheet.sheet1
        
        if not blog_sheet.row_values(1):
            blog_sheet.append_row(["수집일시", "키워드", "제목", "날짜", "링크", "상태", "요약", "주요내용", "경쟁사언급", "감성", "액션포인트"])
            print(f"✅ 블로그 시트 '{BLOG_SHEET_NAME}' 헤더 추가")
        
        # 카페 시트 (신규)
        try:
            cafe_sheet = spreadsheet.worksheet(CAFE_SHEET_NAME)
        except:
            print(f"📋 '{CAFE_SHEET_NAME}' 시트 생성 중...")
            cafe_sheet = spreadsheet.add_worksheet(title=CAFE_SHEET_NAME, rows=1000, cols=20)
        
        if not cafe_sheet.row_values(1):
            cafe_sheet.append_row([
                "수집일시", "키워드", "카페명", "제목", "날짜", "링크",
                "본문내용요약", "댓글수", "핵심연관키워드", "경쟁사언급"
            ])
            print(f"✅ 카페 시트 '{CAFE_SHEET_NAME}' 헤더 추가")
            
        return blog_sheet, cafe_sheet, spreadsheet
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return None, None, None

def search_naver_blog(query):
    """네이버 블로그 검색"""
    encText = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display={DISPLAY_COUNT}&sort={SORT_MODE}"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"   ❌ API 오류: {e}")
    return None

def main():
    print("🚀 Viral Scout: Naver & Google Sheet Scanning Started...")
    
    # API 키 체크
    if ENABLE_AI_ANALYSIS:
        if AI_PROVIDER == "gemini":
            print(f"✅ AI Provider: Gemini" + (" (API 키 확인됨)" if GEMINI_API_KEY else " ⚠️ API 키 없음"))
        elif AI_PROVIDER == "openai":
            print(f"✅ AI Provider: OpenAI" + (" (API 키 확인됨)" if OPENAI_API_KEY else " ⚠️ API 키 없음"))
    
    blog_sheet, cafe_sheet, spreadsheet = init_google_sheets()
    if not blog_sheet:
        print("❌ 시트 연결 실패로 프로그램을 종료합니다.")
        sys.exit(1)  # GitHub Actions에서 실패로 처리되도록 Exit Code 1 반환

    print("✅ 시트 연결 성공!")

    # [검색설정] 탭에서 키워드 로드 (없으면 config.py 기본값)
    search_keywords = load_keywords_from_sheet(spreadsheet) or SEARCH_KEYWORDS
    
    if not search_keywords:
        print("❌ 검색 키워드가 없습니다. 프로그램을 종료합니다.")
        sys.exit(1)
        
    print(f"🔎 검색 키워드: {search_keywords}")

    # KST (UTC+9) 설정
    kst = datetime.timezone(datetime.timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    blog_rows = []  # 블로그 데이터
    cafe_rows = []  # 카페 데이터
    briefing_lines = []

    # Phase 2: 블로그 검색 (활성화)
    # 중복 체크를 위해 기존 링크 로드 (E열=링크, 인덱스 4)
    existing_blog_links = get_existing_links(blog_sheet, 4)
    print(f"\n📝 Phase 2: 블로그 검색 시작...")
    print(f"   📋 기존 블로그 글: {len(existing_blog_links)}건")
    
    for keyword in search_keywords:
        print(f"\n🔎 검색어: '{keyword}'")
        result = search_naver_blog(keyword)
        
        keyword_count = 0
        if result and 'items' in result:
            items = result['items']
            if not items:
                print("   (결과 없음)")
                continue

            for item in items:
                title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                link = item['link']
                postdate = format_date(item['postdate'])
                description = item.get('description', '').replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                
                # 중복 체크
                if link in existing_blog_links:
                    continue
                
                if is_blacklisted(title):
                    print(f"   🚫 제외(블랙리스트): {title[:40]}")
                    continue
                
                if not has_required_keyword(title):
                    print(f"   🚫 제외(필수키워드): {title[:40]}")
                    continue
                
                # description을 본문으로 사용 (150자 미리보기, 크롤링보다 안정적)
                content = description
                
                print(f"   🧠 AI 분석 ({len(content)}자)...")
                analysis = analyze_content_with_ai(title, content)
                
                # AI가 반려동물 관련 없다고 판단하면 제외
                if not analysis.get("반려동물관련", True):
                    print(f"   🚫 제외(AI판단): {title[:40]}")
                    continue

                # 블로그 데이터 (간결 형식)
                row_data = [
                    today_str, keyword, title, postdate, link, "신규",
                    analysis.get("요약", ""),
                    analysis.get("주요내용", ""),
                    analysis.get("경쟁사언급", ""),
                    analysis.get("감성", ""),
                    analysis.get("액션포인트", "")
                ]
                
                blog_rows.append(row_data)
                print(f"   ✅ 준비: {title[:40]}")
                if analysis.get("요약"):
                    print(f"      💡 {analysis['요약'][:50]}...")
                
                keyword_count += 1
                if keyword_count <= 2:
                    briefing_lines.append(f"- [{keyword}] {title}")
                
                time.sleep(0.5)

        else:
            print("   (API 실패)")
        
        time.sleep(1)
    
    # Phase 3: 카페 크롤링
    if ENABLE_CAFE_CRAWLING:
        try:
            from cafe_scanner import search_cafe_posts
            from content_filters import (
                detect_sponsored_content,
                is_genuine_question,
                analyze_comments_batch,
                extract_keywords_hybrid,
                extract_competitors
            )
            
            print(f"\n\n🏢 Phase 3: 카페 검색 시작...")
            cafe_briefing = []
            
            # 중복 체크를 위해 기존 링크 로드 (F열=링크, 인덱스 5)
            existing_cafe_links = get_existing_links(cafe_sheet, 5)
            print(f"   📋 기존 카페 글: {len(existing_cafe_links)}건")
            
            for keyword in search_keywords:
                print(f"\n🔍 [카페] '{keyword}'")
                cafe_posts = search_cafe_posts(keyword, max_posts=CAFE_MAX_POSTS)
                
                # 중복 제외
                new_posts = filter_new_posts(cafe_posts, existing_cafe_links, "카페")
                
                for post in new_posts:
                    # 1. 댓글 수 확인
                    comment_count = post.get('comment_count', 0)
                    is_question = is_genuine_question(post['title'], post['content'])
                    
                    # 댓글 0개인 글은 질문형태가 아니면 제외
                    if comment_count == 0 and not is_question:
                        print(f"   🚫 댓글없음(비질문): {post['title'][:40]}")
                        continue
                    
                    # 2. 협찬 필터링 (선택)
                    if FILTER_SPONSORED:
                        if detect_sponsored_content(post['title'], post['content']):
                            print(f"   🚫 협찬글 제외: {post['title'][:40]}")
                            continue
                    
                    # 3. AI 요약
                    print(f"   🧠 AI 요약 중...")
                    from content_filters import analyze_cafe_content
                    ai_analysis = analyze_cafe_content(post['title'], post['content'])
                    
                    # AI가 반려동물 관련 없다고 판단하면 제외
                    if not ai_analysis.get("반려동물관련", True):
                        print(f"   🚫 제외(AI판단): {post['title'][:40]}")
                        continue
                    
                    # 4. 핵심 키워드 추출 (I열: 지정 키워드만)
                    keywords_str = extract_keywords_hybrid(post['title'], post['content'])
                    
                    # 5. 경쟁사 언급 추출 (J열: 지정 경쟁사만)
                    competitors_str = extract_competitors(post['title'], post['content'])
                    
                    # 카페 데이터 (이미지 열 제거)
                    # A: 수집일시, B: 키워드, C: 카페명
                    # D: 제목, E: 날짜, F: 링크
                    # G: 본문내용요약 (AI 요약, 100자)
                    # H: 댓글수
                    # I: 핵심연관키워드 (지정 키워드에서 매칭)
                    # J: 경쟁사언급 (지정 경쟁사에서 매칭)
                    
                    row_data = [
                        today_str,                                  # A: 수집일시
                        keyword,                                    # B: 키워드
                        post['cafe_name'],                          # C: 카페명
                        post['title'],                              # D: 제목
                        post['date'],                               # E: 날짜
                        post['link'],                               # F: 링크
                        ai_analysis.get("요약", "")[:100],          # G: 본문내용요약 (100자)
                        comment_count,                              # H: 댓글수
                        keywords_str,                               # I: 핵심연관키워드
                        competitors_str                             # J: 경쟁사언급
                    ]
                    
                    cafe_rows.append(row_data)
                    print(f"   ✅ 준비: {post['title'][:40]}")
                    if competitors_str:
                        print(f"      🏆 경쟁사 언급: {competitors_str}")
                    
                    if is_question:
                        cafe_briefing.append(f"- [질문/{post['cafe_name']}] {post['title'][:40]}")
                    
                    time.sleep(0.5)
                
                time.sleep(2)  # 카페 간 delay
            
            if cafe_briefing:
                briefing_lines.extend(cafe_briefing[:5])
        
        except Exception as e:
            print(f"\n⚠️ 카페 크롤링 실패: {e}")

    # 분리 저장
    total_count = 0
    
    # 블로그 데이터 저장
    if blog_rows:
        print(f"\n📚 블로그 {len(blog_rows)}건 저장 중...")
        try:
            blog_sheet.append_rows(blog_rows, value_input_option='RAW')
            print(f"✅ 블로그 {len(blog_rows)}건 저장 완료!")
            total_count += len(blog_rows)
        except Exception as e:
            print(f"❌ 블로그 배치 실패: {e}")
    
    # 카페 데이터 저장
    if cafe_rows:
        print(f"\n🏪 카페 {len(cafe_rows)}건 저장 중...")
        try:
            # USER_ENTERED로 변경하여 IMAGE 함수가 작동하도록 함
            cafe_sheet.append_rows(cafe_rows, value_input_option='USER_ENTERED')
            print(f"✅ 카페 {len(cafe_rows)}건 저장 완료!")
            total_count += len(cafe_rows)
        except Exception as e:
            print(f"❌ 카페 배치 실패: {e}")
    print(f"\n🎉 총 {total_count}건 저장 완료!")
    
    # 텔레그램 보고 메시지 생성
    blog_new_count = len(blog_rows)
    cafe_new_count = len(cafe_rows)
    
    # 누적 개수 계산 (기존 + 신규)
    blog_total = len(existing_blog_links) + blog_new_count
    cafe_total = len(existing_cafe_links) + cafe_new_count if ENABLE_CAFE_CRAWLING else 0
    
    if total_count > 0:
        # 제목 30자 자르기 함수
        def truncate_title(title, max_len=30):
            return title[:max_len] + "..." if len(title) > max_len else title
        
        msg = f"오늘 총 {total_count}개의 글이 수집되었습니다!\n\n"
        msg += f"블로그 : +{blog_new_count}/{blog_total}\n"
        msg += f"카페 : +{cafe_new_count}/{cafe_total}\n\n"
        
        # 블로그 목록 (최대 5개)
        if blog_rows:
            msg += "【블로그】\n"
            for row in blog_rows[:5]:
                keyword = row[1]  # B열: 키워드
                title = row[2]    # C열: 제목
                msg += f" - [{keyword}] {truncate_title(title)}\n"
            if len(blog_rows) > 5:
                msg += f" ... 외 {len(blog_rows) - 5}개\n"
            msg += "\n"
        
        # 카페 목록 (최대 5개)
        if cafe_rows:
            msg += "【카페】\n"
            for row in cafe_rows[:5]:
                keyword = row[1]  # B열: 키워드
                title = row[3]    # D열: 제목
                msg += f" - [{keyword}] {truncate_title(title)}\n"
            if len(cafe_rows) > 5:
                msg += f" ... 외 {len(cafe_rows) - 5}개\n"
            msg += "\n"
        
        msg += f"👉 {GOOGLE_SHEET_URL}"
        send_telegram_message(msg)
    else:
        print("신규 데이터 없음")

if __name__ == "__main__":
    main()
