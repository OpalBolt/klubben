# Klubben website — handoff

A website for "Klubben", a local hygge social club. Built and run by a single
maintainer (the user). This doc hands a fresh agent the current state of the
concept so it can continue shaping or start building.

## The club (facts)

- Located in a basement, down a nearly hidden staircase. **Address: use a
  placeholder** until the user supplies the real one.
- Opened ~1960s, when the apartment complexes were built.
- Most current members joined 1980s/1990s (many are 60+).
- Weekly event: **Wednesday 19:00**, a small pool tournament, plus beer/social.
- A new member (the user) wants to add: board games, use of the exercise room,
  and a "PC café" (help desk for residents' PC issues).
- Prices: membership **40 DKK/month**; soda/beer/wine **10 DKK each**.
  Newcomers should see these prices clearly.
- Newcomers can just walk in — no signup required first.
- Everyone calls it **"klubben"** (lowercase, humble, no logo needed).

## What the website is for

- Primary audience: **new and potential members** — people who don't know the
  club exists.
- Three Forside jobs:
  1. **"This exists"** — who we are, one warm line.
  2. **"You're welcome"** — just walk in; the hidden staircase; prices.
  3. **"What's on"** — current events.
- All content in **Danish**.
- Must be **very easy to read and interact with** (60+ accessibility), even
  though existing members aren't expected to use it.

## Decisions made

- **Stack**: Hugo + hugo-PaperMod as base, customised toward the vintage
  look. Hosted on GitHub Pages (free github.io subdomain); custom domain
  later. See `docs/adr/0001`.
- **Calendar-driven**: a daily GitHub Action rebuilds the site from the
  single public Google Calendar. The calendar does not exist yet — we prepare
  the piping; the site launches with an empty Events page. Events are only
  ever edited in the calendar, nowhere else.
- **Multi-page**: Forside / Events / Find os / Historie — the complete list.
  Forside carries prices (40 kr/md, 10 kr/drikke) and the "just walk in"
  message. Find os gets text directions (complex + neighbourhood, staircase
  description) now; a map image with arrows comes later. Historie ships as a
  framework — the maintainer interviews members for content.
- **New activities** (board games, exercise room, PC café) appear only as
  calendar events, never as standing promises elsewhere.
- **Old-timey aesthetic**: warm cream paper, chunky serif, high contrast —
  same choice as 60+ readability. PaperMod's dark-mode toggle, JS search,
  share buttons get stripped back.
- **No contact info, no tagline, no logo.** Lowercase "klubben".
- **Copy**: agent drafts all Danish strings, maintainer reviews and corrects.

## Pending inputs (facts, not decisions)

- Create the public Google Calendar ("Klubben" on the maintainer's account),
  add Wednesday 19:00 as weekly recurring, supply its ID as the repo secret.
- Complex + neighbourhood names for Find os text.
- Real address (placeholder until then).
- Historie content and old photos (room/interior over member faces).
- Map image with arrows, posters/QR codes, custom domain — all later.

## Suggested next-session focus

- Run `to-spec` (maintainer launches it) to synthesize this session into a
  spec. Read `CONTEXT.md`, `docs/adr/0001`, and this file.

## Suggested skills

- `to-spec` — turn the concept into a spec.
- `to-tickets` — break the spec into tickets.

## Notes

- No secrets or PII captured. Keep the address as a placeholder.
- Session history: grilled to an empty frontier — decisions above are
  confirmed shared understanding; domain terms live in `CONTEXT.md`.
