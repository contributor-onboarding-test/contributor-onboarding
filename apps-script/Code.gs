const SHEET_NAME = "Form Responses 1";
const PENDING = "Pending";
const PASSED = "✅";
const FAILED = "❌";
// the daily workflow replaces Pending with the result of the star check
const STARS_COLUMN = "Have you started OpenWISP repositories";
const TERMS_COLUMN = "Terms and policies";
const CONTACT_COLUMN = "Other contact (Optional)";
// the options of the Terms question, all of them must be checked
const TERMS = [
  "I have read and accept the Contributing Guidelines",
  "I have read and accept the Code of Conduct",
  "I have read and accept the Anti AI Spam Policy",
];
// links of a submission shown as a label; only a single link of the
// expected site becomes clickable, anything else stays as it was typed
const LINKS = [
  {
    column: "Merged PR Link 1",
    label: "Merged PR 1",
    prefix: "https://github.com/",
  },
  {
    column: "Merged PR Link 2",
    label: "Merged PR 2",
    prefix: "https://github.com/",
  },
  {
    column: "Merged PR Link 3 (Networking module)",
    label: "Merged PR 3",
    prefix: "https://github.com/",
  },
  {
    column: "Introduction video",
    label: "Introduction video",
    prefix: "https://drive.google.com/",
  },
  {
    column: "Recording of testing your Networking module PR",
    label: "PR test recording",
    prefix: "https://drive.google.com/",
  },
];

function getHeader(sheet) {
  return sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
}

function getColumn(header, title) {
  const column = header.indexOf(title) + 1;
  if (!column) {
    throw new Error(`The "${title}" column is missing.`);
  }
  return column;
}

// A rich text link is used instead of a HYPERLINK formula, so that
// nothing typed in the Form can end up inside a formula.
function labelLinks(sheet, header, row) {
  for (const link of LINKS) {
    const column = header.indexOf(link.column) + 1;
    if (!column) {
      continue;
    }
    const cell = sheet.getRange(row, column);
    const url = String(cell.getValue()).trim();
    if (!url.startsWith(link.prefix) || /[\s,]/.test(url)) {
      continue;
    }
    cell.setRichTextValue(
      SpreadsheetApp.newRichTextValue()
        .setText(link.label)
        .setLinkUrl(url)
        .build(),
    );
  }
}

// Sheets turns a typed phone number into a number, which drops its "+" and
// aligns it to the right. Keep the contact as it was typed in the Form; the
// leading apostrophe stores it as text, so it can never become a formula.
function keepContactAsText(sheet, header, row, answers) {
  const column = header.indexOf(CONTACT_COLUMN) + 1;
  if (!column) {
    return;
  }
  const cell = sheet.getRange(row, column);
  const typed =
    answers && answers[CONTACT_COLUMN]
      ? answers[CONTACT_COLUMN][0]
      : cell.getDisplayValue();
  if (typed) {
    cell.setValue(`'${typed}`);
  }
}

// Prepares a submission for the daily workflow. answers are the values typed
// in the Form, which are only available when the Form is submitted.
function prepareRow(sheet, header, row, answers) {
  // the Form adds each response as a new row, without the formatting of
  // the rows above
  sheet
    .getRange(row, 1, 1, sheet.getLastColumn())
    .setVerticalAlignment("middle");
  labelLinks(sheet, header, row);
  keepContactAsText(sheet, header, row, answers);
  const terms = sheet.getRange(row, getColumn(header, TERMS_COLUMN));
  const accepted = String(terms.getValue());
  terms.setValue(
    TERMS.every((term) => accepted.includes(term)) ? PASSED : FAILED,
  );
  sheet.getRange(row, getColumn(header, STARS_COLUMN)).setValue(PENDING);
  sheet.getRange(row, getColumn(header, "Validation")).setValue(PENDING);
  sheet
    .getRange(row, getColumn(header, "Decision"))
    .clearContent()
    .clearDataValidations();
}

function onFormSubmit(e) {
  const sheet = e.range.getSheet();
  if (sheet.getName() !== SHEET_NAME) {
    return;
  }
  prepareRow(sheet, getHeader(sheet), e.range.getRow(), e.namedValues);
}

// Run once by hand from the editor for the rows submitted before the
// script was added. Rows already pending or validated are left as they are.
function processExistingRows() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  const header = getHeader(sheet);
  const validation = getColumn(header, "Validation");
  for (let row = 2; row <= sheet.getLastRow(); row++) {
    if (
      sheet.getRange(row, 1).getValue() &&
      !sheet.getRange(row, validation).getValue()
    ) {
      prepareRow(sheet, header, row, null);
    }
  }
}
