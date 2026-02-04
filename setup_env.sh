#!/bin/bash
# 🔐 환경변수 설정 가이드 스크립트

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Viral Scout - 환경변수 설정"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "❌ .env 파일이 없습니다."
    echo ""
    echo "📝 .env 파일 생성 중..."
    
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ .env.example을 .env로 복사했습니다."
    else
        echo "❌ .env.example 파일도 없습니다."
        exit 1
    fi
    
    echo ""
    echo "⚠️  이제 .env 파일을 편집하여 실제 API 키를 입력하세요:"
    echo "   nano .env"
    echo "   또는"
    echo "   code .env"
    echo ""
    exit 0
fi

echo "✅ .env 파일을 찾았습니다."
echo ""

# 환경변수 로드 확인
echo "🔍 필수 환경변수 검증 중..."
echo ""

# .env 로드
export $(cat .env | grep -v '^#' | xargs)

# 필수 변수 체크
missing_vars=()

if [ -z "$NAVER_CLIENT_ID" ]; then
    missing_vars+=("NAVER_CLIENT_ID")
fi

if [ -z "$NAVER_CLIENT_SECRET" ]; then
    missing_vars+=("NAVER_CLIENT_SECRET")
fi

if [ -z "$GEMINI_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  AI API 키가 설정되지 않았습니다 (GEMINI 또는 OPENAI 중 하나 필요)"
fi

# 선택적 변수 체크
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "ℹ️  Telegram 알림이 비활성화됩니다 (선택사항)"
fi

# 결과 출력
if [ ${#missing_vars[@]} -gt 0 ]; then
    echo ""
    echo "❌ 필수 환경변수가 설정되지 않았습니다:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "📝 .env 파일을 편집하여 누락된 값을 입력하세요:"
    echo "   nano .env"
    exit 1
else
    echo ""
    echo "✅ 모든 필수 환경변수가 설정되었습니다!"
    echo ""
    echo "🚀 스크립트를 실행할 수 있습니다:"
    echo "   python viral_scout/naver_scanner.py"
    echo ""
    echo "💡 현재 쉘에서 환경변수를 로드하려면:"
    echo "   export \$(cat .env | xargs)"
fi
