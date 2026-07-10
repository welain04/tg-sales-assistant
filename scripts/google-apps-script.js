/**
 * Google Apps Script для приёма заявок из Telegram-бота.
 *
 * Настройка:
 * 1. Создайте Google Таблицу
 * 2. Расширения → Apps Script → вставьте этот код
 * 3. Запустите setupSheet() один раз (разрешите доступ)
 * 4. Развернуть → Новое развертывание → Веб-приложение
 *    - Запуск от: Я
 *    - Доступ: Все
 * 5. Скопируйте URL в GOOGLE_SHEETS_WEBHOOK_URL в .env
 */

const SHEET_NAME = "Заявки";

function setupSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  sheet.clear();
  sheet.appendRow([
    "Дата",
    "Имя",
    "Email",
    "Уровень",
    "Программа",
    "Ответ 1: Учёт финансов",
    "Ответ 2: Накопления",
    "Ответ 3: Инвестиционный опыт",
    "Ответ 4: Приоритетная задача",
    "Telegram ID",
    "Telegram username",
  ]);
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
    if (!sheet) {
      setupSheet();
    }

    const answers = data.qualification_answers || [];
    SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME).appendRow([
      new Date(),
      data.name || "",
      data.email || "",
      data.level || "",
      data.recommended_program || "",
      answers[0] || "",
      answers[1] || "",
      answers[2] || "",
      answers[3] || "",
      data.telegram_user_id || "",
      data.telegram_username || "",
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, message: "Webhook is active" }))
    .setMimeType(ContentService.MimeType.JSON);
}
