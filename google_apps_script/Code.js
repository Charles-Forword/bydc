function onOpen() {
    const ui = SpreadsheetApp.getUi();
    ui.createMenu('Viral Scout 메뉴')
        .addItem('데이터 정렬 마법사 🧙‍♂️', 'showSortingWizard')
        .addToUi();
}

function showSortingWizard() {
    const ui = SpreadsheetApp.getUi();
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // 1. 시트 선택
    const sheetResponse = ui.prompt(
        '1단계: 대상 시트 선택',
        '숫자를 입력하세요:\n[1] 블로그\n[2] 카페',
        ui.ButtonSet.OK_CANCEL
    );

    if (sheetResponse.getSelectedButton() !== ui.Button.OK) return;

    let sheetName = "";
    let dateCol = 0; // 1-based index

    const sheetChoice = sheetResponse.getResponseText().trim();

    if (sheetChoice === "1") {
        sheetName = "블로그";
        dateCol = 4; // D열: 작성일자
    } else if (sheetChoice === "2") {
        sheetName = "카페";
        dateCol = 5; // E열: 작성일자
    } else {
        ui.alert('잘못된 입력입니다. 1 또는 2를 입력해주세요.');
        return;
    }

    const sheet = ss.getSheetByName(sheetName);
    if (!sheet) {
        ui.alert(`'${sheetName}' 시트를 찾을 수 없습니다.`);
        return;
    }

    // 2. 작업 선택
    const taskResponse = ui.prompt(
        '2단계: 정렬 기준 선택',
        '숫자를 입력하세요:\n[0] 수집 순서대로 (A열 기준)\n[1] 작성 일자별 (최신/과거)',
        ui.ButtonSet.OK_CANCEL
    );

    if (taskResponse.getSelectedButton() !== ui.Button.OK) return;

    const taskChoice = taskResponse.getResponseText().trim();

    // 데이터 범위 (헤더 제외)
    // 헤더가 1행이라고 가정
    if (sheet.getLastRow() < 2) {
        ui.alert("데이터가 없습니다.");
        return;
    }

    const range = sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn());

    if (taskChoice === "0") {
        // 수집 순서대로 (A열: 수집일시 오름차순)
        range.sort({ column: 1, ascending: true });
        ss.toast(`${sheetName} 시트 정렬 완료! (기준: 수집순서)`, "✅ 처리 완료", 5);

    } else if (taskChoice === "1") {
        // 작성 일자별
        const orderResponse = ui.prompt(
            '3단계: 날짜 정렬 순서',
            '숫자를 입력하세요:\n[1] 최신순 (내림차순)\n[2] 오래된순 (오름차순)',
            ui.ButtonSet.OK_CANCEL
        );

        if (orderResponse.getSelectedButton() !== ui.Button.OK) return;

        const orderChoice = orderResponse.getResponseText().trim();
        let ascending = true;

        if (orderChoice === "1") {
            ascending = false; // 최신순 (내림차순)
        } else if (orderChoice === "2") {
            ascending = true;  // 오래된순 (오름차순)
        } else {
            ui.alert('잘못된 입력입니다.');
            return;
        }

        range.sort({ column: dateCol, ascending: ascending });
        const orderText = ascending ? "오래된순" : "최신순";
        ss.toast(`${sheetName} 시트 정렬 완료! (기준: 작성일자 ${orderText})`, "✅ 처리 완료", 5);

    } else {
        ui.alert('잘못된 입력입니다.');
    }
}
