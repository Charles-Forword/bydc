"""
네이버 카페 크롤러
통합검색 카페 탭에서 게시글 + 댓글 수집
"""

import time
import hashlib
from playwright.sync_api import sync_playwright
from config import SEARCH_KEYWORDS, CAFE_MAX_POSTS

def generate_post_hash(author, title, content):
    """중복 제거용 해시 생성"""
    unique_str = f"{author}{title}{content[:100]}"
    return hashlib.md5(unique_str.encode()).hexdigest()



def improve_cafe_name_extraction(page, initial_cafe_name):
    """
    카페명 추출 개선 (여러 방법 시도)
    
    Args:
        page: Playwright page 객체
        initial_cafe_name: 검색 결과에서 가져온 초기 카페명
    
    Returns:
        str: 개선된 카페명
    """
    # 초기 카페명이 있고 유효하면 그대로 사용
    if initial_cafe_name and initial_cafe_name.strip() and initial_cafe_name != "(없음)":
        return initial_cafe_name
    
    # 상세 페이지에서 다시 추출 시도
    try:
        iframe = page.frame_locator("iframe#cafe_main")
        
        cafe_name_selectors = [
            'h1.tit',  # 카페 타이틀
            '.cafe_name',
            'a.cafe_name',
            '.gnb_cafe_title a',
            'h1.title_text'
        ]
        
        for selector in cafe_name_selectors:
            try:
                elem = iframe.locator(selector).first
                if elem.count() > 0:
                    cafe_name = elem.inner_text().strip()
                    if cafe_name:
                        # "카페명 - 부제" 형태면 첫 부분만
                        cafe_name = cafe_name.split('-')[0].split('|')[0].strip()
                        return cafe_name
            except:
                continue
        
        # 메타 태그에서 추출 시도
        try:
            meta_cafe = page.locator('meta[property="og:site_name"]').first
            if meta_cafe.count() > 0:
                cafe_name = meta_cafe.get_attribute('content')
                if cafe_name:
                    return cafe_name
        except:
            pass
    
    except Exception as e:
        pass
    
    # 모든 시도 실패 시 기본값
    return initial_cafe_name if initial_cafe_name else "(카페명 미확인)"


def search_cafe_posts(keyword, max_posts=20):
    """
    네이버 통합검색 카페 탭에서 게시글 수집
    
    Args:
        keyword: 검색 키워드
        max_posts: 최대 수집 개수
    
    Returns:
        list: 게시글 정보 딕셔너리 리스트
    """
    results = []
    
    with sync_playwright() as p:
        # 브라우저 실행 (headless mode)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # 1. 네이버 통합검색
            print(f"   🔍 카페 검색: '{keyword}'")
            search_url = f"https://search.naver.com/search.naver?query={keyword}"
            page.goto(search_url, wait_until="networkidle")
            
            # 2. 카페 탭 클릭
            try:
                cafe_tab = page.locator("a.tab:has-text('카페')").first
                if cafe_tab.count() > 0:
                    cafe_tab.click()
                    page.wait_for_load_state("networkidle")
                else:
                    print(f"   ⚠️ 카페 탭 없음")
                    return results
            except Exception as e:
                print(f"   ⚠️ 카페 탭 클릭 실패: {e}")
                return results
            
            
            # 3. 게시글 리스트 수집 (광고 제외, 실제 카페 게시글만)
            # title_area 클래스를 가진 a 태그 = 실제 제목 링크
            title_links = page.locator("a[href*='cafe.naver.com'][class*='title']").all()
            
            print(f"   ✅ 실제 카페 게시글: {len(title_links)}개 발견")
            print(f"   📋 수집 시작: {min(len(title_links), max_posts)}개")
            
            for idx, link_elem in enumerate(title_links[:max_posts]):
                try:
                    # 제목 & 링크 (직접 추출)
                    title = link_elem.inner_text().strip()
                    link = link_elem.get_attribute("href") or ""
                    
                    if not title or not link:
                        continue
                    
                    # 부모 요소 찾기
                    parent = link_elem.locator('xpath=ancestor::li | ancestor::div[contains(@class,"api")]').first
                    
                    # 카페명 찾기 (카페 링크에서)
                    cafe_link = parent.locator("a[href*='cafe.naver.com']:not([class*='title'])").first
                    cafe_name = ""
                    if cafe_link.count() > 0:
                        cafe_name_text = cafe_link.inner_text().strip()
                        # "강사모-반려견..." 형태면 첫 부분만
                        cafe_name = cafe_name_text.split('-')[0].split('|')[0].strip()
                    
                    # 작성자
                    author = "카페회원"
                    
                    # 날짜 찾기
                    date_elem = parent.locator(".sub_time, span:has-text('.')").first
                    post_date = date_elem.inner_text().strip() if date_elem.count() > 0 else ""
                    
                    # 미리보기 텍스트
                    desc_elem = parent.locator(".dsc_area, .dsc_txt").first
                    description = desc_elem.inner_text().strip() if desc_elem.count() > 0 else ""
                    
                    print(f"   📄 [{idx+1}] {title[:40]}... ({cafe_name})")
                    
                    # 4. 게시글 상세 페이지 접속 (새 탭)
                    post_data = scrape_cafe_post_detail(p, link, title, author, cafe_name, post_date, description)
                    
                    if post_data:
                        results.append(post_data)
                    
                    time.sleep(1)  # 부하 방지
                    
                except Exception as e:
                    print(f"   ⚠️ 게시글 파싱 실패: {e}")
                    continue
            
        finally:
            browser.close()
    
    return results


def scrape_cafe_post_detail(playwright_instance, url, title, author, cafe_name, post_date, description):
    """
    카페 게시글 상세 페이지 크롤링
    
    Returns:
        dict: 게시글 데이터 (본문, 댓글 포함)
    """
    browser = playwright_instance.chromium.launch(headless=True)
    page = browser.new_page()
    
    try:
        page.goto(url, wait_until="networkidle", timeout=15000)
        time.sleep(2)  # 동적 로딩 대기
        
        # iframe 확인 (카페는 보통 iframe 사용)
        iframe = page.frame_locator("iframe#cafe_main")
        
        # 카페명 개선 (상세 페이지에서 재확인)
        improved_cafe_name = improve_cafe_name_extraction(page, cafe_name)
        

        
        # 본문 추출
        content = ""
        try:
            # 본문 선택자 (카페마다 다를 수 있음)
            content_selectors = [
                ".ContentRenderer",
                ".se-main-container",
                "#postContent",
                ".post-content"
            ]
            
            for selector in content_selectors:
                content_elem = iframe.locator(selector).first
                if content_elem.count() > 0:
                    content = content_elem.inner_text().strip()
                    break
            
            if not content:
                content = description  # 폴백: 미리보기 사용
        
        except Exception as e:
            print(f"      ⚠️ 본문 추출 실패: {e}")
            content = description
        
        # 댓글 수집
        comments = []
        try:
            comment_items = iframe.locator(".CommentItem").all()
            
            for comment_elem in comment_items[:20]:  # 최대 20개
                try:
                    comment_author = comment_elem.locator(".comment_nickname").inner_text().strip()
                    comment_text = comment_elem.locator(".comment_text_view").inner_text().strip()
                    
                    comments.append({
                        "author": comment_author,
                        "content": comment_text
                    })
                except:
                    continue
        
        except Exception as e:
            print(f"      ⚠️ 댓글 수집 실패: {e}")
        
        # 해시 생성
        post_hash = generate_post_hash(author, title, content)
        
        return {
            "source": "카페",
            "cafe_name": improved_cafe_name,
            "title": title,
            "link": url,
            "author": author,
            "date": post_date,
            "content": content[:2000],  # 2000자 제한
            "description": description,

            "comments": comments,
            "comment_count": len(comments),  # 댓글 수 추가
            "hash": post_hash
        }
    
    except Exception as e:
        print(f"      ⚠️ 상세 페이지 로딩 실패: {e}")
        return None
    
    finally:
        browser.close()


if __name__ == "__main__":
    # 테스트
    results = search_cafe_posts("보양대첩", max_posts=5)
    print(f"\n✅ 수집 완료: {len(results)}건")
    
    for r in results:
        print(f"\n제목: {r['title']}")
        print(f"카페: {r['cafe_name']}")
        print(f"본문: {r['content'][:100]}...")
        print(f"댓글: {len(r['comments'])}개")
