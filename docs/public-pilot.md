# Public evidence explorer pilot

## First users

Recruit five researchers or graduate students working on antimicrobial evidence.
Use their own current research question and compounds, with permission. This is a
research workflow study, not validation of a drug or model. No invitations are sent
automatically by the application.

## A 20-minute session

1. Ask how they currently find and compare evidence and how long it usually takes.
2. Ask them to find a compound report without instructions.
3. Ask them to explain which results are measured, which are predictions, and what
   information is missing. Record any confusion.
4. Have them upload a small compound list, inspect unmatched rows, and compare two
   compounds. Can they identify when the assay conditions are not comparable?
5. Have them export a cited report, share its link, and follow a compound.
6. Ask which result they would use in their current work and what they would verify
   in the original publication before using it.

## Record for each session

Use a participant code, not a name: task, completion time, previous workflow time,
task completed without help, incorrect interpretation, missing source information,
export useful (yes/no), requested improvement, and voluntary follow-up date.
Do not collect private compound lists without explicit permission.

## Initial success criteria

Three participants return for a real project. At least four of five distinguish
predictions from measurements and identify missing assay conditions. Fix any
interpretation errors before broader promotion. Track useful exports and observed
time savings; page views alone do not establish research impact.

## Public release checklist

- Configure the public frontend API URL, HTTPS, CORS origin and server write key.
- Run migrations and bootstrap source data before inviting users.
- Run one evidence worker against the same database as the API.
- Test a shared report link in a fresh browser, an upload with unmatched compounds,
  a cited export, and a failed source refresh.
- Confirm source licenses and attribution are preserved in published exports.
- Document the bounded ChEMBL sample, archival CO-ADD release, and missing metadata.
- Provide a maintainer contact on the hosted site's surrounding project page.

Email delivery, user accounts, cross-device watches, hosting, and researcher
recruitment require deployment/account choices. The implemented watches work in
the current browser without collecting contact information.
