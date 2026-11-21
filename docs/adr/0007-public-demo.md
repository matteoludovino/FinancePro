# 7. A public demo nobody can put real data into

## Context

A portfolio project needs a demo that works with one click. A finance app has a problem the usual shared demo account doesn't: a visitor may upload a real bank statement, and the next visitor would see it. The demo also runs on free plans: a 0.1-CPU API that sleeps when idle, a 0.5 GB database, no always-on worker.

## Decision

- **A sandbox per visitor.** "Experimentar a demo" creates a user of its own, with no e-mail or password, and signs the visitor in. Visitors never share data. The sandbox is built **through the real import pipeline** from the same deterministic generator the tests use, so the demo exercises presets, deduplication, installment groups, linked bill payments and cached AI answers, and nothing in the demo is hand-made. Dates are relative to today, so the current month is never empty. The checking account stops two weeks back, so importing the "more recent statement" sample shows deduplication at work: a month already there, two weeks new.
- **Only the site's own files.** In demo mode an upload must be byte-identical to one of the sample statements the API generates for today (or yesterday, for a download just before midnight). Signing up with a password is closed. Real statements never reach the demo, so there is nothing to protect there under the LGPD.
- **AI without a live call.** The model's answers for the generator's merchants are written into the shared cache when a sandbox is created; the demo shows suggestions with or without an API key.
- **Bounded.** A sandbox's session lasts 3 idle hours. At most 100 sandboxes are alive at once, counted in the database, and creation is rate-limited globally (behind the proxy every visitor shares an address). Idle sandboxes are deleted, cascading to everything they hold, each time a sandbox is created, and daily by a GitHub Actions job against the database, because the API sleeps.
- **Cold starts are told, not hidden.** After 4 seconds the button says the server is waking up and preparing the data. On the free plan that takes up to a minute: about 85 s to boot and 9 s to build a sandbox at 0.1 CPU, measured.

## Consequences

The demo can't show a visitor's own bank's layout being detected (the samples are Nubank); the tests and the mapping editor cover that. A burst of visitors beyond 100 gets "a demonstração está cheia" rather than a slow database. GitHub disables scheduled workflows after 60 days without commits, so the daily cleanup can stop; sandbox creation still cleans up, and the cap still holds.
