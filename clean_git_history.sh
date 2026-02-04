#!/bin/bash
# 🔥 Git History에서 민감한 파일 완전 삭제 스크립트 (기본 Git 명령어 사용 버전)
# ⚠️ 이 작업은 되돌릴 수 없으며, 협업자가 있다면 모두에게 공지해야 합니다!

set -e  # 에러 발생 시 즉시 중단

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔥 Git History 완전 삭제 스크립트 (No-BFG 버전)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  경고: 이 작업은 되돌릴 수 없습니다!"
echo ""
echo "삭제할 파일:"
echo "  - viral_scout/config.py"
echo "  - service_account.json"
echo ""
echo "계속하시겠습니까? (yes/no): "
read -r response

if [[ "$response" != "yes" ]]; then
    echo "작업을 취소했습니다."
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: 백업 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BACKUP_DIR="../bydc-backup-$(date +%Y%m%d-%H%M%S)"
echo "백업 디렉토리: $BACKUP_DIR"

cp -r . "$BACKUP_DIR"
echo "✅ 백업 완료!"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Git Filter-Branch로 기록 삭제"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "이 작업은 수분 정도 소요될 수 있습니다..."
echo ""

# 기존 백업 기록 삭제 (있을 경우)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch viral_scout/config.py service_account.json" \
  --prune-empty --tag-name-filter cat -- --all

echo ""
echo "✅ Git history 정리 완료!"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: 용량 최적화 및 가비지 컬렉션"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ 최적화 완료!"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Remote에 Force Push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  마지막 경고: 이제 GitHub에 force push를 수행합니다!"
echo "   협업자가 있다면 모두에게 공지하셨나요?"
echo ""
echo "Force push를 실행하시겠습니까? (yes/no): "
read -r force_response

if [[ "$force_response" != "yes" ]]; then
    echo "Force push를 건너뜜. 나중에 'git push origin --force --all'을 수동으로 실행하세요."
    exit 0
fi

git push origin --force --all
git push origin --force --tags

echo ""
echo "✅ 모든 작업이 완료되었습니다!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "검증 명령어:"
echo "  git log --all --full-history -- viral_scout/config.py"
echo "  # → 아무것도 출력되지 않아야 함"
echo ""
