#!/bin/bash

# 로그 파일 위치 설정
LOG_FILE="/Users/mac_roadmine/Documents/연구자동화에이전트들/bydc/viral_scout/daily_log.txt"

echo "========================================" >> $LOG_FILE
echo "Execution Time: $(date)" >> $LOG_FILE

# 프로젝트 디렉토리로 이동
cd /Users/mac_roadmine/Documents/연구자동화에이전트들

# Python 실행 (절대 경로 사용 권장 / gspread 등 라이브러리 인식 위해)
# 사용자 환경에 따라 python3 경로가 다를 수 있으므로 which python3로 확인된 경로 사용
# /Library/Frameworks/Python.framework/Versions/3.14/bin/python3
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 bydc/viral_scout/naver_scanner.py >> $LOG_FILE 2>&1

echo "Finished" >> $LOG_FILE
echo "========================================" >> $LOG_FILE
