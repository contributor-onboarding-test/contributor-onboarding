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

``.github/workflows/validate.yml`` runs every day and on demand. For each
new row of the "Form Responses 1" tab, it checks the applicant's GitHub
account and pull requests, then writes the result to the Sheet:

- **Passed**: ``Validation`` is ``Passed``, and ``Decision`` gets a
  Pending, Approved or Rejected dropdown set to Pending, for a maintainer
  to decide.
- **Failed**: ``Validation`` is ``Failed``, ``Validation details`` lists
  the reasons, and ``Decision`` is ``Rejected``.
- **GitHub unavailable**: the row is left unchanged and checked on the
  next run.

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

Logs only show counts, never applicant data.

Setup
-----

Create a ``onboarding`` environment in the repository settings, with these
secrets:

- ``GOOGLE_SERVICE_ACCOUNT``: the JSON key of a Google service account
  that can edit the Sheet.
- ``ONBOARDING_APP_ID`` and ``ONBOARDING_APP_PRIVATE_KEY``: a GitHub App
  installed on the organization with the Members read permission, used to
  check whether applicants are already members.

And the repository variable ``SHEET_ID``: the ID in the Sheet's URL.

Applicants are checked against the organization that owns the repository.

Run the workflow manually with "dry run" enabled first: it checks the rows
without writing to the Sheet.

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
