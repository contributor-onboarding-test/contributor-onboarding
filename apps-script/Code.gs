const SHEET_NAME = "Form Responses 1";
const PENDING = "Pending";
const PASSED = "✅";
const FAILED = "❌";
// the daily workflow replaces Pending with the result of the star check
const STARS_COLUMN = "Have you started OpenWISP repositories";
const TERMS_COLUMN = "Terms and policies";
const CONTACT_COLUMN = "Other contact (Optional)";
// set once the email about the decision is sent
const EMAIL_STATUS_COLUMN = "Email status";
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
  sheet.getRange(row, getColumn(header, EMAIL_STATUS_COLUMN)).clearContent();
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

// Settings of the emails, in Project Settings > Script Properties, so another
// organization needs no code change: ORGANIZATION, the GitHub organization of
// the invitation (required to send welcome emails), and REPLY_TO (optional).
function getProperty(name) {
  return PropertiesService.getScriptProperties().getProperty(name) || "";
}

function rejectionEmail(name, validation) {
  const reasons = validation.startsWith(FAILED)
    ? validation.slice(FAILED.length).trim().split("; ")
    : [];
  const lines = [
    `Hi ${name},`,
    "",
    "Thank you for applying to become an OpenWISP contributor. " +
      "Unfortunately, your application could not be accepted" +
      (reasons.length ? ":" : " this time."),
  ];
  if (reasons.length) {
    lines.push("", ...reasons.map((reason) => `- ${reason}`));
    lines.push("", "You can fix these and apply again with the form.");
  } else {
    lines.push("", "You can apply again with the form.");
  }
  lines.push("", "The OpenWISP team");
  return {
    subject: "Your OpenWISP contributor application",
    body: lines.join("\n"),
  };
}

function welcomeEmail(name, username) {
  const organization = getProperty("ORGANIZATION");
  if (!organization) {
    throw new Error("Set the ORGANIZATION Script Property");
  }
  return {
    subject: "Welcome to the OpenWISP community",
    body: [
      `Hi ${name},`,
      "",
      `Your application has been accepted. We've invited your GitHub account ` +
        `${username} to the ${organization} organization: please accept the ` +
        "invitation from GitHub's email or at " +
        `https://github.com/orgs/${organization}/invitation within 7 days, ` +
        "after which it expires.",
      "",
      "The OpenWISP team",
    ].join("\n"),
  };
}

// Run by a time-driven trigger. Sends the email of each decision queued by the
// daily workflow, then marks it as sent, or as failed with the error.
function sendPendingEmails() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  const header = getHeader(sheet);
  const column = (title) => getColumn(header, title) - 1;
  const status = column(EMAIL_STATUS_COLUMN);
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return;
  }
  const rows = sheet
    .getRange(2, 1, lastRow - 1, sheet.getLastColumn())
    .getDisplayValues();
  rows.forEach((values, index) => {
    const decision = values[column("Decision")].toLowerCase();
    if (
      values[status] !== PENDING ||
      !["accept", "reject"].includes(decision)
    ) {
      return;
    }
    // Stop for today when the quota is used up; the rest stay pending.
    if (MailApp.getRemainingDailyQuota() < 1) {
      return;
    }
    const cell = sheet.getRange(index + 2, status + 1);
    const name = values[column("Full Name")];
    try {
      const email =
        decision === "accept"
          ? welcomeEmail(name, values[column("Github Username")])
          : rejectionEmail(name, values[column("Validation")]);
      const replyTo = getProperty("REPLY_TO");
      MailApp.sendEmail({
        to: values[column("Email")],
        subject: email.subject,
        body: email.body,
        name: "OpenWISP",
        ...(replyTo ? { replyTo } : {}),
      });
      cell.setValue(PASSED);
    } catch (error) {
      cell.setValue(`${FAILED} ${error.message}`);
    }
  });
}
