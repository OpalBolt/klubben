# Calendar-driven static site

The website is a Hugo static site (hugo-PaperMod base, customised) hosted free
on GitHub Pages under a github.io subdomain. A scheduled GitHub Action
rebuilds it once daily from the club's single public Google Calendar and
renders upcoming events; the calendar is the only place events are ever
edited. Chosen over a CMS or manual edits so the sole maintainer updates
events exactly one way — a custom domain can be layered on later without
touching this pipeline.

## Consequences

- The Calendar does not exist yet; the site ships with the pipeline ready and
  an empty Events page until it is created and made public (accepted).
- Same-day event changes can be up to 24h stale; no manual dispatch (accepted).
- Member-only events are visible on the public calendar (accepted — they
  double as an enticement to join).
