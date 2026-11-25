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

Decisions and Emails
--------------------

``Email status`` is empty until a decision is made. On its next run, the
workflow handles each ``Accept`` or ``Reject`` chosen by a maintainer:

- **Reject**: the rejection email is queued.
- **Accept**: the applicant is invited to the organization's team (GitHub
  emails the invitation), then the welcome email is queued. Only an
  application with ``Validation`` ✅ is invited. A refused invite is shown
  as ❌ in ``Email status``.

A queued email has ``Email status`` ``Pending``. Every hour,
``sendPendingEmails()`` in the Apps Script sends it from the account that
owns the script, then sets ``Email status`` to ✅, or to ❌ with the
error.

The checks:

- The applicant is not already a member of the organization.
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

Setup
-----

Create a ``onboarding`` environment in the repository settings, with these
secrets:

- ``GOOGLE_SERVICE_ACCOUNT``: the JSON key of a Google service account
  that can edit the Sheet.
- ``ONBOARDING_APP_ID`` and ``ONBOARDING_APP_PRIVATE_KEY``: a GitHub App
  installed on the organization with the Members read and write
  permission, used to check whether applicants are already members and to
  invite accepted ones.

And these variables:

- ``SHEET_ID``: the ID in the Sheet's URL.
- ``ONBOARDING_TEAM`` (optional): the team accepted applicants are invited
  to, ``community`` by default. It must exist.
- ``SKIP_MEMBERSHIP_CHECK`` (optional): ``true`` skips the check that the
  applicant is not already a member, so an organization owner can test the
  whole flow. Do not set it in production.

Applicants are checked against, and invited to, the organization that owns
the repository.

In the Sheet, the ``Form Responses 1`` tab needs the ``Validation``,
``Decision`` and ``Email status`` columns after the Form's columns. Paste
``apps-script/Code.gs`` into **Extensions > Apps Script**, then:

- In **Project Settings > Script Properties**, set ``ORGANIZATION`` to the
  GitHub organization, and optionally ``REPLY_TO`` to the reply address of
  the emails.
- In **Triggers**, add ``onFormSubmit`` (From spreadsheet, On form submit)
  and ``sendPendingEmails`` (Time-driven, every hour).
- Run ``processExistingRows`` once if the Form already has responses.

Run the workflow manually with "dry run" enabled first: it checks the rows
without writing to the Sheet or inviting anyone.

Moving to Another Organization
------------------------------

No code changes are needed:

1. Push the repository to the new organization, and create the
   ``onboarding`` environment with the secrets and variables above.
2. Install the organization's GitHub App with the Members read and write
   permission, and create the team.
3. Have the Form and the Sheet owned by the organization's account, so the
   emails come from it: link the Form to a new Sheet, name its tab ``Form
   Responses 1`` and add the three result columns.
4. Paste the Apps Script, set its Script Properties and add its triggers.
5. Leave ``SKIP_MEMBERSHIP_CHECK`` unset, then run the workflow with "dry
   run" enabled before the first real run.

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
