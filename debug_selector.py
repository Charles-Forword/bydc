"""
테스트용 간단한 크롤러 - HTML 구조 확인
"""

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # 1. 검색
    url = "https://search.naver.com/search.naver?query=보양대첩"
    page.goto(url, wait_until="networkidle")
    
    # 2. 카페 탭 클릭
    cafe_tab = page.locator("a.tab:has-text('카페')").first
    cafe_tab.click()
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    
    # 3. 스크린샷
    page.screenshot(path="debug2.png")
    
    # 4. HTML 저장
    html = page.content()
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("✅ HTML 저장 완료: debug_page.html")
    print("✅ 스크린샷 저장: debug2.png")
    
    # 5. 여러 선택자 테스트
    selectors_to_test = [
        ".total_wrap",
        ".api_subject_bx",
        ".news_area",
        "li.bx",
        ".lst_total li",
        "div[class*='api']",
        "a.api_txt_lines",
    ]
    
    for sel in selectors_to_test:
        items = page.locator(sel).all()
        print(f"{sel}: {len(items)}개")
    
    browser.close()
