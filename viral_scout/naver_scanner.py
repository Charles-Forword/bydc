import urllib.request
print("DEBUG: Script started")
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
print("DEBUG: SSL patch applied")

from config import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, 
    SEARCH_KEYWORDS, DISPLAY_COUNT, SORT_MODE,
    GOOGLE_SHEET_URL, SERVICE_ACCOUNT_FILE,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
print("DEBUG: Config imported")

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
            sheet.append_row(["수집일시", "키워드", "제목", "날짜", "링크", "상태"])
            print("✅ 시트 헤더 추가 완료")
            
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
