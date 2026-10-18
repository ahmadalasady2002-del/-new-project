/**
 * يحفظ ردود تأكيد الحضور بـ Google Sheet ويرجع التهاني للدعوة.
 *
 * الخطوات:
 * 1. سوّي Google Sheet جديد ← Extensions ← Apps Script
 * 2. الصق هذا الكود واحفظ
 * 3. Deploy ← New deployment ← Web app
 *    Execute as: Me   |   Who has access: Anyone
 * 4. انسخ رابط الـ Web app وحطه بـ CONFIG.rsvpEndpoint بملف index.html
 */

function sheet_() {
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  if (sh.getLastRow() === 0) {
    sh.appendRow(["الوقت", "الاسم", "الحضور", "المرافقين", "التهنئة", "اسم الدعوة"]);
  }
  return sh;
}

function doPost(e) {
  const r = JSON.parse(e.postData.contents);
  const attend = { yes: "نعم", no: "لا", maybe: "ربما" }[r.attend] || r.attend;
  sheet_().appendRow([new Date(), r.name, attend, r.guests, r.message, r.invitedAs]);
  return ContentService.createTextOutput("ok");
}

function doGet() {
  const rows = sheet_().getDataRange().getValues().slice(1);
  const wishes = rows
    .filter(r => r[4])
    .reverse()
    .slice(0, 100)
    .map(r => ({ name: r[1], message: r[4] }));
  return ContentService.createTextOutput(JSON.stringify(wishes))
    .setMimeType(ContentService.MimeType.JSON);
}
