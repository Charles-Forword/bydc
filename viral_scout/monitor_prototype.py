import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ------------------------------------------------------
# 🕵️‍♂️ Viral Scout: Community Monitor (MVP)
# 목표: 특정 커뮤니티에서 키워드가 포함된 새 글을 발견하면 알림(출력)
# ------------------------------------------------------

# 설정: 모니터링할 키워드와 대상 URL
# 예시로 네이버 카페는 접근 제어가 까다로우므로, 
# 테스트를 위해 접근이 쉬운 공개 커뮤니티(예: 디시인사이드 멍멍이 갤러리 등)나
# 혹은 가상의 테스트 타겟을 상정하고 작성합니다.
# 실제 네이버 카페 크롤링은 로그인 세션 등 추가 작업이 필요합니다.

TARGET_URL = "https://gall.dcinside.com/board/lists/?id=dog" # 예시: 멍멍이 갤러리
SEARCH_KEYWORDS = ["사료", "밥", "추천", "안먹어", "보양대첩"] 
CHECK_INTERVAL_SECONDS = 60 # 1분마다 확인

def fetch_latest_posts():
    """커뮤니티의 최신 글 목록을 가져옵니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(TARGET_URL, headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

def parse_posts(html):
    """HTML에서 글 제목과 링크를 추출합니다. (디시인사이드 예시)"""
    soup = BeautifulSoup(html, 'html.parser')
    posts = []
    
    # 디시인사이드 갤러리 리스트 구조에 맞춘 파싱 (사이트마다 다름)
    # 실제 구현 시에는 대상 사이트의 HTML 구조 분석이 선행되어야 함
    rows = soup.select('tr.ub-content')
    
    for row in rows:
        try:
            title_tag = row.select_one('.gall_tit a')
            if title_tag:
                title = title_tag.text.strip()
                link = "https://gall.dcinside.com" + title_tag['href']
                posts.append({'title': title, 'link': link})
        except AttributeError:
            continue
            
    return posts

def monitor():
    print(f"🕵️‍♂️ Viral Scout 가동 시작... (타겟: {TARGET_URL})")
    print(f"🔎 감시 키워드: {SEARCH_KEYWORDS}")
    
    seen_posts = set() # 이미 본 글 중복 방지

    while True:
        html = fetch_latest_posts()
        if html:
            posts = parse_posts(html)
            new_sightings = 0
            
            for post in posts:
                post_id = post['link'] # 링크를 고유 ID로 사용
                
                if post_id not in seen_posts:
                    seen_posts.add(post_id)
                    
                    # 키워드 매칭 확인
                    for keyword in SEARCH_KEYWORDS:
                        if keyword in post['title']:
                            print(f"\n[🚨 포착됨!] 키워드 '{keyword}' 발견")
                            print(f"제목: {post['title']}")
                            print(f"링크: {post['link']}")
                            print("-" * 30)
                            new_sightings += 1
                            break # 한 글에 여러 키워드가 있어도 한 번만 알림
            
            if new_sightings == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 특이사항 없음...", end='\r')
        
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor()
