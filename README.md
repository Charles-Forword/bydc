# Viral Scout - 보안 업데이트 완료

## 📌 프로젝트 개요
네이버 블로그/카페 크롤링 및 AI 분석 자동화 시스템

## 🔐 보안 설정 (중요!)

### 초기 설정 - 로컬 개발

1. **환경변수 파일 생성**:
```bash
cp .env.example .env
# .env 파일을 열어서 실제 API 키 입력
```

2. **Python 환경 설정**:
```bash
pip install -r requirements.txt
pip install python-dotenv  # 환경변수 로더
```

3. **실행**:
```bash
export $(cat .env | xargs)
python3 viral_scout/naver_scanner.py
```

### GitHub Actions 설정

1. Repository → **Settings** → **Secrets and variables** → **Actions**
2. 다음 Secrets 추가:
   - `NAVER_CLIENT_ID`
   - `NAVER_CLIENT_SECRET`
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`

## ⚠️ 보안 주의사항

### 🔒 절대 Git에 올리면 안되는 파일
- `viral_scout/config.py` (실제 키 포함)
- `.env` (로컬 환경변수)
- `service_account.json` (Google 인증)

### ✅ Git에 올려도 되는 파일
- `viral_scout/config.py.example` (템플릿)
- `.env.example` (템플릿)
- `.gitignore` (보안 설정)

### 🛠️ 자동 환경변수 설정 스크립트

```bash
# 환경변수 자동 설정 및 검증
./setup_env.sh
```

이 스크립트는 자동으로:
- ✅ `.env` 파일 생성 (.env.example 복사)
- ✅ 필수 환경변수 검증
- ✅ 누락된 변수 안내

### 🔑 API 키 발급/재발급

**Naver API**
- 접속: https://developers.naver.com/apps/#/list
- Application 등록 → Client ID/Secret 발급

**Telegram Bot**
- BotFather (@BotFather) 대화
- `/newbot` 명령으로 새 봇 생성
- Bot Token 및 Chat ID 저장

**Google Gemini API**
- 접속: https://aistudio.google.com/app/apikey
- "Create API key" 클릭

**Google Service Account**
- Cloud Console: https://console.cloud.google.com/iam-admin/serviceaccounts
- Service Account 생성 → JSON 키 다운로드
- `service_account.json`으로 저장

### 🚨 API 키 노출 시 대응 방법

만약 실수로 API 키가 GitHub에 노출되었다면:

1. **즉시 모든 API 키 재발급** (위 가이드 참고)
2. **Git History에서 완전 삭제** (implementation_plan.md 참고)
3. **구 키 폐기 확인**


## 🚀 기능

### 카페 크롤링
- ✅ 네이버 카페 검색 및 본문 추출
- ✅ AI 요약 (Gemini/OpenAI)
- ✅ 하이브리드 키워드 추출 (정규식 + AI)
- ✅ 중복 체크 (링크 기반)
- ✅ 댓글 감성 분석

### 데이터 저장
- 구글 시트 자동 업로드
- 블로그 / 카페 시트 분리
- 텔레그램 알림

## 📊 시트 구조

### 카페 시트
| 컬럼 | 내용 |
|-----|------|
| D | 제목 |
| G | 본문내용요약 (AI 100자) |
| H | 댓글수 |
| I | 핵심연관키워드 (하이브리드) |
| J | 주요불만 |

## 🔧 트러블슈팅

### Gemini API 403 에러
→ 새 API 키 발급: https://aistudio.google.com/apikey

### 환경변수 인식 안됨
```bash
# 확인
echo $GEMINI_API_KEY

# 설정
export GEMINI_API_KEY="your_key"
```

## 📚 더 알아보기

- [보안 가이드](security_guide.md)
- [Implementation Plan](implementation_plan.md)
- [Walkthrough](walkthrough.md)
