const SHEET_NAME = "Form Responses 1";
// created by the daily workflow when the first applicant joins
const MEMBERS_SHEET_NAME = "Members";
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
  const org = organization();
  return {
    subject: "Welcome to the OpenWISP community",
    body: [
      `Hi ${name},`,
      "",
      `Your application has been accepted. We've invited your GitHub account ` +
        `${username} to the ${org} organization: please accept the ` +
        "invitation from GitHub's email or at " +
        `https://github.com/orgs/${org}/invitation within 7 days, ` +
        "after which it expires.",
      "",
      "The OpenWISP team",
    ].join("\n"),
  };
}

function organization() {
  const value = getProperty("ORGANIZATION");
  if (!value) {
    throw new Error("Set the ORGANIZATION Script Property");
  }
  return value;
}

function warningEmail(name, username, lastActivity) {
  return {
    subject: "Your OpenWISP membership",
    body: [
      `Hi ${name},`,
      "",
      `We haven't seen any activity from your GitHub account ${username} in ` +
        `OpenWISP repositories since ${lastActivity}. Members who are ` +
        `inactive for 90 days are removed from the ${organization()} ` +
        "organization.",
      "",
      "To stay a member, open or review a pull request, open or comment on " +
        "an issue, or take part in a discussion. If you are removed, you can " +
        "apply again with the form.",
      "",
      "The OpenWISP team",
    ].join("\n"),
  };
}

function removalEmail(name, username, lastActivity) {
  return {
    subject: "Your OpenWISP membership has ended",
    body: [
      `Hi ${name},`,
      "",
      `Your GitHub account ${username} was removed from the ` +
        `${organization()} organization, because it had no activity in ` +
        `OpenWISP repositories since ${lastActivity}.`,
      "",
      "Thank you for your contributions. You are welcome to apply again " +
        "with the form.",
      "",
      "The OpenWISP team",
    ].join("\n"),
  };
}

// Sends the email of each row whose Email status is Pending, then marks it as
// sent, or as failed with the error. buildEmail returns null for a row
// without an email to send.
function sendQueued(sheet, buildEmail) {
  if (!sheet || sheet.getLastRow() < 2) {
    return;
  }
  const header = getHeader(sheet);
  const status = getColumn(header, EMAIL_STATUS_COLUMN) - 1;
  const rows = sheet
    .getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn())
    .getDisplayValues();
  rows.forEach((values, index) => {
    if (values[status] !== PENDING) {
      return;
    }
    const value = (title) => values[getColumn(header, title) - 1];
    // Stop for today when the quota is used up; the rest stay pending.
    if (MailApp.getRemainingDailyQuota() < 1) {
      return;
    }
    const cell = sheet.getRange(index + 2, status + 1);
    try {
      const email = buildEmail(value);
      if (!email) {
        return;
      }
      const replyTo = getProperty("REPLY_TO");
      MailApp.sendEmail({
        to: value("Email"),
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

// Run by a time-driven trigger. Sends the emails queued by the daily
// workflow (decisions) and by the weekly review (inactivity).
function sendPendingEmails() {
  const spreadsheet = SpreadsheetApp.getActive();
  sendQueued(spreadsheet.getSheetByName(SHEET_NAME), (value) => {
    const decision = value("Decision").toLowerCase();
    if (decision === "accept") {
      return welcomeEmail(value("Full Name"), value("Github Username"));
    }
    if (decision === "reject") {
      return rejectionEmail(value("Full Name"), value("Validation"));
    }
    return null;
  });
  sendQueued(spreadsheet.getSheetByName(MEMBERS_SHEET_NAME), (value) => {
    const lastActivity = value("Last activity") || value("Joined on");
    if (value("Removed on")) {
      return removalEmail(value("Full Name"), value("Username"), lastActivity);
    }
    if (value("Warned on")) {
      return warningEmail(value("Full Name"), value("Username"), lastActivity);
    }
    return null;
  });
}
