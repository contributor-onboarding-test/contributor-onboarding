Contributor Onboarding
======================

.. image:: https://github.com/openwisp/contributor-onboarding/actions/workflows/ci.yml/badge.svg
    :target: https://github.com/openwisp/contributor-onboarding/actions/workflows/ci.yml
    :alt: CI build status

.. image:: https://img.shields.io/gitter/room/nwjs/nw.js.svg
    :target: https://gitter.im/openwisp/general
    :alt: chat

----

**Contributor Onboarding** checks applications submitted through the
`OpenWISP <https://openwisp.org/>`_ contributor Google Form.

Daily Validation
----------------

When a Form is submitted, the Apps Script of the Sheet
(``apps-script/Code.gs``) sets its ``Validation`` and its star column
("Have you started OpenWISP repositories") to ``Pending``, shows ``Terms
and policies`` as ✅ when every policy was accepted, and shows its pull
request and video links as labels, such as "Merged PR 1". The workflow
reads the links behind the labels, and writes ✅ or ❌ in the star column
once the stars are checked.

``.github/workflows/validate.yml`` runs every day and on demand. For each
``Pending`` row of the "Form Responses 1" tab, it checks the applicant's
GitHub account and pull requests, then writes the result to the Sheet:

- **Passed**: ``Validation`` is ✅, and ``Decision`` gets a Pending,
  Accept or Reject dropdown set to Pending, for a maintainer to decide.
- **Failed**: ``Validation`` is ❌ followed by the reasons, ``Decision``
  gets the same dropdown set to Reject, and the rejection email is queued.
- **GitHub unavailable**: the row is left unchanged and checked on the
  next run.

The checks:

- The applicant is not already a member of the organization, nor invited
  to it.
- The GitHub profile Name matches the Form's Full Name, ignoring case,
  spacing and accents.
- The GitHub bio or profile README contains "Contributing to OpenWISP".
- The profile is public and has starred at least 20 OpenWISP repositories,
  including the required ones.
- The three pull requests are different, merged and opened by the
  applicant in OpenWISP repositories. The third one is in a networking
  module, with a ``[fix]``, ``[change]`` or ``[feature]`` title.
- The two weekly meeting dates are different Wednesdays, not in the
  future. Attendance itself cannot be verified.

Logs only show counts, never applicant data.

Decisions and Emails
--------------------

``Email status`` is empty until a decision is made. On its next run, the
workflow handles each ``Accept`` or ``Reject`` chosen by a maintainer:

- **Reject**: the rejection email is queued.
- **Accept**: the applicant is invited to the organization's team (GitHub
  emails the invitation), then the welcome email is queued. Only an
  application with ``Validation`` ✅ is invited. A refused invite is shown
  as ❌ in ``Email status``.

To accept an application that failed a check which could not be verified,
such as the stars of a private profile, type ✅ in ``Validation``, clear
``Email status`` and select ``Accept``.

``Invite status`` is ``Invited`` until the applicant joins. Each run then
sets it to ``Joined``, and adds the member to the ``Members`` tab, or to
``Expired`` once GitHub drops the invitation, after 7 days or when it is
declined. An applicant whose invitation expired must apply again.

A queued email has ``Email status`` ``Pending``. On a time-driven trigger,
for example every 2 hours, ``sendPendingEmails()`` in the Apps Script
sends it from the account that owns the script, then sets ``Email status``
to ✅, or to ❌ with the error.

Weekly Inactivity Review
------------------------

``.github/workflows/inactivity.yml`` runs every Monday and on demand. It
checks the members of the ``Members`` tab, which keeps them after their
application is removed. Each member is followed by the ID of their GitHub
account, so a renamed account is still found.

Activity is counted in the ``openwisp`` repositories: opening a pull
request, an issue or a discussion, reviewing a pull request, commenting on
an issue, a pull request or a discussion, or adding a commit to one's open
pull request. Each action counts on its own date, never on the "updated"
date of an issue or pull request, which other people can change. A member
without activity is counted from the day they joined.

- **30 days without activity**: ``Warned on`` is set and the warning email
  is queued. Activity after the warning clears it.
- **90 days without activity, and at least 30 days after the warning**:
  the member is removed from the organization, ``Removed on`` is set and
  the removal email is queued.
- **Not removed automatically**: owners of the organization, members of
  other teams, and members with ``Exempt`` checked. ``Note`` explains why
  a member needs a maintainer's review.
- **Left the organization**: ``Removed on`` is set, without an email.
- **GitHub unavailable**: the member is checked again the next week.

Removals are a dry run until the ``REMOVE_INACTIVE`` variable is ``true``:
``Note`` shows "would be removed" instead. Review a few weeks of results
before enabling them.

Setup
-----

Create a ``onboarding`` environment in the repository settings, with these
secrets:

- ``GOOGLE_SERVICE_ACCOUNT``: the JSON key of a Google service account
  that can edit the Sheet.
- ``ONBOARDING_APP_ID`` and ``ONBOARDING_APP_PRIVATE_KEY``: a GitHub App
  installed on the organization with the Members read and write
  permission, used to check whether applicants are already members, to
  invite accepted ones and to remove inactive ones.

And these variables:

- ``SHEET_ID``: the ID in the Sheet's URL.
- ``ONBOARDING_TEAM`` (optional): the team accepted applicants are invited
  to, ``community`` by default. It must exist.
- ``SKIP_MEMBERSHIP_CHECK`` (optional): ``true`` skips the check that the
  applicant is not already a member, so an organization owner can test the
  whole flow. Do not set it in production.
- ``REMOVE_INACTIVE`` (optional): ``true`` lets the weekly review remove
  inactive members.

Applicants are checked against, and invited to, the organization that owns
the repository.

The workflows add the ``Validation``, ``Decision``, ``Email status`` and
``Invite status`` columns after the Form's columns of the ``Form Responses
1`` tab, and create the ``Members`` tab when the first applicant joins.
Paste ``apps-script/Code.gs`` into **Extensions > Apps Script**, then:

- In **Project Settings > Script Properties**, set ``ORGANIZATION`` to the
  GitHub organization, and optionally ``REPLY_TO`` to the reply address of
  the emails.
- In **Triggers**, add ``onFormSubmit`` (From spreadsheet, On form submit)
  and ``sendPendingEmails`` (Time-driven, for example every 2 hours).
- Run ``processExistingRows`` once if the Form already has responses.

Run the workflows manually with "dry run" enabled first: they check the
rows without writing to the Sheet, inviting or removing anyone.

Moving to Another Organization
------------------------------

No code changes are needed:

1. Push the repository to the new organization, and create the
   ``onboarding`` environment with the secrets and variables above.
2. Install the organization's GitHub App with the Members read and write
   permission, and create the team.
3. Have the Form and the Sheet owned by the organization's account, so the
   emails come from it: link the Form to a new Sheet and name its tab
   ``Form Responses 1``.
4. Paste the Apps Script, set its Script Properties and add its triggers.
5. Leave ``SKIP_MEMBERSHIP_CHECK`` and ``REMOVE_INACTIVE`` unset, then run
   the workflows with "dry run" enabled before the first real run.

Development
-----------

.. code-block:: shell

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-test.txt
    ./run-qa-checks
    ./runtests

Contributing
------------

Please refer to the `OpenWISP Contribution Guidelines
<https://openwisp.io/docs/dev/developer/contributing.html>`_.

License
-------

See `LICENSE
<https://github.com/openwisp/contributor-onboarding/blob/master/LICENSE>`_.
