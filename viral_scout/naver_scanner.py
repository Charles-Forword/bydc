import urllib.request
import urllib.parse
import json
import time
import ssl
import datetime
import os
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
    ENABLE_CONTENT_SCRAPING, ENABLE_AI_ANALYSIS, ANALYZE_ALL,
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
        
        prompt = f"""다음 블로그 글을 분석해주세요:

제목: {title}
본문: {content[:1500]}

아래 JSON 형식으로만 응답해주세요:
{{
  "요약": "핵심 내용 3줄 요약",
  "주요내용": "고객이 언급한 제품 특징",
  "경쟁사언급": "언급된 경쟁 브랜드명 (없으면 빈칸)",
  "감성": "긍정 또는 중립 또는 부정",
  "액션포인트": "보양대첩 개선사항"
}}"""

        if AI_PROVIDER == "gemini":
            # Use gemini-2.0-flash (verified via ListModels API)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"


            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}
            }
            response = requests.post(url, json=data, timeout=15)

            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"      ⚠️ Gemini 실패 ({response.status_code})")
                return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
        
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
            data = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
            else:
                print(f"      ⚠️ OpenAI 실패 ({response.status_code})")
                return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
        
        # JSON 파싱
        try:
            if "```" in ai_response:
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
            
            analysis = json_module.loads(ai_response)
            return analysis
        except:
            return {"요약": ai_response[:100], "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}
            
    except Exception as e:
        print(f"      ⚠️ AI 오류: {str(e)[:50]}")
        return {"요약": "", "주요내용": "", "경쟁사언급": "", "감성": "", "액션포인트": ""}


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

def init_google_sheet():
    """구글 시트 초기화"""
    try:
        if os.environ.get("GITHUB_ACTIONS"):
            print("ℹ️ GitHub Env: Creating service_account.json from secret")
            json_content = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
            if json_content:
                with open("service_account.json", "w") as f:
                    f.write(json_content)

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1
        
        if not sheet.row_values(1):
            sheet.append_row(["수집일시", "키워드", "제목", "날짜", "링크", "상태", "요약", "주요내용", "경쟁사언급", "감성", "액션포인트"])
            print("✅ 시트 헤더 추가 (Phase 2 포함)")
            
        return sheet
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return None

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
    
    sheet = init_google_sheet()
    if not sheet:
        print("시트 연결 실패")
        return

    today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows = []
    briefing_lines = []

    for keyword in SEARCH_KEYWORDS:
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
                
                if is_blacklisted(title):
                    print(f"   🚫 제외(블랙리스트): {title[:40]}")
                    continue
                
                if not has_required_keyword(title):
                    print(f"   🚫 제외(필수키워드): {title[:40]}")
                    continue
                
                if not check_relevance_with_ai(title, description):
                    print(f"   🚫 제외(AI판단): {title[:40]}")
                    continue
                
                print(f"   📖 크롤링: {title[:40]}...")
                content = scrape_blog_content(link)
                
                print(f"   🧠 AI 분석...")
                analysis = analyze_content_with_ai(title, content)
                
                row_data = [
                    today_str, keyword, title, postdate, link, "신규",
                    analysis.get("요약", ""),
                    analysis.get("주요내용", ""),
                    analysis.get("경쟁사언급", ""),
                    analysis.get("감성", ""),
                    analysis.get("액션포인트", "")
                ]
                
                all_rows.append(row_data)
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

    # 배치 저장
    if all_rows:
        print(f"\n💾 {len(all_rows)}건 일괄 저장 중...")
        try:
            sheet.append_rows(all_rows, value_input_option='RAW')
            print(f"✅ {len(all_rows)}건 저장 완료!")
        except Exception as e:
            print(f"❌ 배치 실패: {e}")
            print("⚠️ 개별 저장 재시도...")
            success = 0
            for row in all_rows:
                try:
                    sheet.append_row(row)
                    success += 1
                    time.sleep(2)
                except:
                    pass
            print(f"✅ 개별 저장: {success}/{len(all_rows)}건")
    
    new_count = len(all_rows)
    print(f"\n🎉 총 {new_count}건 저장 완료!")
    
    if new_count > 0:
        msg = f"🌞 [Viral Scout 모닝 브리핑]\n\n총 {new_count}건 수집!\n({today_str})\n\n"
        if briefing_lines:
            msg += "📋 수집 목록:\n" + "\n".join(briefing_lines[:10]) + "\n..."
        msg += f"\n\n👉 {GOOGLE_SHEET_URL}"
        send_telegram_message(msg)
    else:
        print("신규 데이터 없음")

if __name__ == "__main__":
    main()
