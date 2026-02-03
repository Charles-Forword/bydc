import urllib.request
import urllib.parse
import json
import time
import ssl
import sys
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# macOS SSL 인증서 오류 해결을 위한 패치
ssl._create_default_https_context = ssl._create_unverified_context

from config import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, 
    SEARCH_KEYWORDS, DISPLAY_COUNT, SORT_MODE,
    GOOGLE_SHEET_URL, SERVICE_ACCOUNT_FILE,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    EXCLUDE_KEYWORDS, REQUIRED_KEYWORDS, USE_AI_FILTER, OPENAI_API_KEY,
    ENABLE_CONTENT_SCRAPING, ENABLE_AI_ANALYSIS, ANALYZE_ALL
)

def scrape_blog_content(url):
    """네이버 블로그 본문 크롤링"""
    if not ENABLE_CONTENT_SCRAPING:
        return ""
    
    try:
        from bs4 import BeautifulSoup
        import requests
        
        # User-Agent 설정 (봇 차단 방지)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 블로그 본문 추출 (iframe 내부 또는 직접 본문)
        # 방법 1: se-main-container (스마트에디터3)
        content = soup.select_one('.se-main-container')
        if content:
            return content.get_text(strip=True, separator=' ')[:2000]  # 2000자 제한
        
        # 방법 2: post-view (구형 블로그)
        content = soup.select_one('#postViewArea')
        if content:
            return content.get_text(strip=True, separator=' ')[:2000]
        
        # 방법 3: 일반 텍스트 추출
        paragraphs = soup.find_all(['p', 'div'], class_=lambda x: x and 'se-text' in x)
        if paragraphs:
            return ' '.join([p.get_text(strip=True) for p in paragraphs])[:2000]
        
        return "(본문 추출 실패)"
        
    except Exception as e:
        print(f"   ⚠️ 본문 크롤링 실패: {e}")
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
    """AI를 사용해 반려동물 사료 관련 글인지 판단 (True/False)"""
    if not USE_AI_FILTER or not OPENAI_API_KEY:
        return True  # AI 필터 비활성화시 모두 통과
    
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
            print(f"   ⚠️ AI 필터 호출 실패 (status: {response.status_code}), 통과 처리")
            return True
            
    except Exception as e:
        print(f"   ⚠️ AI 필터 오류: {e}, 통과 처리")
        return True


def analyze_content_with_ai(title, content):
    """AI로 블로그 본문 분석하여 구조화된 인사이트 추출"""
    if not ENABLE_AI_ANALYSIS or not OPENAI_API_KEY:
        return {
            "요약": "",
            "주요내용": "",
            "경쟁사언급": "",
            "감성": "",
            "액션포인트": ""
        }
    
    # 분석 범위 제한 (ANALYZE_ALL이 False면 "보양대첩" 언급 글만 분석)
    if not ANALYZE_ALL and "보양대첩" not in title and "보양대첩" not in content:
        return {
            "요약": "(간단 분석 생략)",
            "주요내용": "",
            "경쟁사언급": "",
            "감성": "",
            "액션포인트": ""
        }
    
    try:
        import requests
        import json as json_module
        
        prompt = f"""다음 블로그 글을 분석해주세요:

제목: {title}
본문: {content[:1500]}

아래 JSON 형식으로만 응답해주세요. 다른 설명 없이 JSON만:
{{
  "요약": "핵심 내용 3줄 요약",
  "주요내용": "고객이 언급한 제품 특징 (장점/단점)",
  "경쟁사언급": "언급된 경쟁 브랜드명 (예: 건강백서, 듀먼). 없으면 빈칸",
  "감성": "긍정 또는 중립 또는 부정",
  "액션포인트": "보양대첩 개선/마케팅에 참고할 만한 사항"
}}"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()
            
            # JSON 파싱 시도
            try:
                # 코드 블록 제거 (```json ... ``` 형식 대응)
                if "```" in ai_response:
                    ai_response = ai_response.split("```")[1]
                    if ai_response.startswith("json"):
                        ai_response = ai_response[4:]
                
                analysis = json_module.loads(ai_response)
                return analysis
            except:
                print(f"   ⚠️ AI 응답 JSON 파싱 실패")
                return {
                    "요약": ai_response[:100],
                    "주요내용": "",
                    "경쟁사언급": "",
                    "감성": "",
                    "액션포인트": ""
                }
        else:
            print(f"   ⚠️ AI 분석 실패 (status: {response.status_code})")
            return {
                "요약": "(분석 실패)",
                "주요내용": "",
                "경쟁사언급": "",
                "감성": "",
                "액션포인트": ""
            }
            
    except Exception as e:
        print(f"   ⚠️ AI 분석 오류: {e}")
        return {
            "요약": "(분석 오류)",
            "주요내용": "",
            "경쟁사언급": "",
            "감성": "",
            "액션포인트": ""
        }


def send_telegram_message(message):
    """텔레그램 메시지 발송"""
    try:
        # 메시지 길이 제한(4096자) 고려하여 너무 길면 잘라서 보내기 (간단 구현)
        if len(message) > 4000:
            message = message[:4000] + "...(생략)"
            
        encText = urllib.parse.quote(message)
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={encText}"
        
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            print("✅ 텔레그램 발송 성공")
        else:
            print(f"❌ 텔레그램 발송 실패: {response.getcode()}")
    except Exception as e:
        print(f"❌ 텔레그램 발송 오류: {e}")

def format_date(naver_date_str):
    """네이버 날짜 형식(YYYYMMDD)을 YYYY-MM-DD로 변환"""
    return f"{naver_date_str[:4]}-{naver_date_str[4:6]}-{naver_date_str[6:]}"

def init_google_sheet():
    """구글 시트 연결 및 초기화"""
    try:
        # GitHub Actions 환경: 환경변수에서 JSON 키 생성
        import os
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
             if "GOOGLE_SERVICE_ACCOUNT_JSON" in os.environ:
                 print("ℹ️ GitHub Env: Creating service_account.json from secret")
                 with open(SERVICE_ACCOUNT_FILE, "w") as f:
                     f.write(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
             else:
                 # 로컬인데 파일이 없고 환경변수도 없으면 에러 (경로 문제 가능성)
                 # 기존 절대 경로 처리
                 pass

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # 상대 경로 사용 (Git Repo 내부)
        json_path = SERVICE_ACCOUNT_FILE
        # 만약 로컬 절대경로가 필요하면 예외처리 (여기서는 생략하고 단순화)
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1 # 첫 번째 시트 사용
        
        # 헤더가 없으면 추가
        if not sheet.row_values(1):
            sheet.append_row(["수집일시", "키워드", "제목", "날짜", "링크", "상태", "요약", "주요내용", "경쟁사언급", "감성", "액션포인트"])
            print("✅ 시트 헤더 추가 완료 (Phase 2 컬럼 포함)")

            
        return sheet
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return None

def search_naver_blog(query):
    """네이버 블로그 검색 API 호출"""
    encText = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display={DISPLAY_COUNT}&sort={SORT_MODE}"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        res_code = response.getcode()
        
        if res_code == 200:
            response_body = response.read()
            return json.loads(response_body.decode('utf-8'))
        else:
            print(f"Error Code: {res_code}")
            return None
    except Exception as e:
        print(f"API Request Failed: {e}")
        return None

def main():
    print(f"🚀 Viral Scout: Naver & Google Sheet Scanning Started...")
    
    # 1. 구글 시트 연결
    sheet = init_google_sheet()
    if not sheet:
        print("시트 연결 실패로 프로그램을 종료합니다.")
        return

    today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_count = 0
    briefing_lines = []

    for keyword in SEARCH_KEYWORDS:
        print(f"\n🔎 검색어: '{keyword}'")
        result = search_naver_blog(keyword)
        
        keyword_count = 0
        if result and 'items' in result:
            items = result['items']
            if not items:
                print("   (검색 결과 없음)")
                continue

            for item in items:
                title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                link = item['link']
                postdate = format_date(item['postdate'])
                
                # 기존 데이터 중복 체크 (링크 기준) - 간단하게 메모리상에서 체크 비효율적일 수 있으나 일단 구현
                # (실제로는 시트의 모든 데이터를 가져와서 비교하거나 별도 DB 사용)
                # 여기서는 일단 무조건 추가하고 시트에서 중복제거 기능을 쓰는 것을 권장
                
                row_data = [today_str, keyword, title, postdate, link, "신규"]
                
                try:
                    sheet.append_row(row_data)
                    print(f"   ✅ 저장: {title}")
                    new_count += 1
                    keyword_count += 1
                    
                    # 브리핑용: 키워드별 상위 2개만 제목 수집
                    if keyword_count <= 2:
                        briefing_lines.append(f"- [{keyword}] {title}")
                        
                except Exception as e:
                    print(f"   ❌ 저장 실패: {e}")
                    time.sleep(1) # API 제한 등 방지

        else:
            print("   (API 호출 실패 또는 데이터 없음)")
        
        time.sleep(1) # 검색 API 호출 간격

    print(f"\n🎉 총 {new_count}건의 데이터를 시트에 저장했습니다!")
    
    # 2. 텔레그램 브리핑 발송
    if new_count > 0:
        briefing_msg = f"🌞 [Viral Scout 모닝 브리핑]\n\n총 {new_count}건의 새로운 글을 수집했습니다!\n({today_str} 기준)\n\n"
        if briefing_lines:
            briefing_msg += "📋 주요 수집 목록:\n" + "\n".join(briefing_lines) + "\n..."
        
        briefing_msg += f"\n\n👉 구글 시트 확인하기:\n{GOOGLE_SHEET_URL}"
        
        send_telegram_message(briefing_msg)
    else:
        print("신규 수집 데이터가 없어 알림을 보내지 않습니다.")

if __name__ == "__main__":
    main()
