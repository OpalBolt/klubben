# Klubben website

The public website for "klubben", a basement social club. Its audience is
newcomers; its job is to make them show up on a Wednesday.

## Language

**klubben**:
The club's name. Always lowercase, no logo, no tagline.
_Avoid_: Klubben, the Club

**Newcomer (ny/gæst)**:
A person who has not joined. The website's whole answer to them is "come by
any Wednesday at 19:00" — welcome as a guest. Becoming part of the club
requires a membership, paid in the room; there is no digital signup path.
_Avoid_: guest user, visitor, prospective member

**Member (medlem)**:
A person who pays 40 DKK/month in person. Joins by showing up; there is no
digital signup path.

**Calendar (kalenderen)**:
The single public Google Calendar. The only source of truth for what happens
in the club; the website only ever mirrors it. The maintainer updates events
here and nowhere else.
_Avoid_: event list, schedule, CMS

**Event (begivenhed)**:
Anything scheduled in the Calendar — including new activities (board games,
exercise room, PC café). New activities exist on the website only as events,
never as standing promises on other pages.

## Site

**The five pages**:
Forside, Det koster, Events, Find os, Historie — the complete page list.
Nothing is added until a real need appears.

**Forside**:
Carries the newcomer message: "just walk in", the fixed Wednesday programme,
and this week's calendar events in two side-by-side boxes. Links out to
prices and directions; it is the site's front door and only conversion path.

**Det koster**:
The prices (40 kr/md, 10 kr/drikke) on their own page, in the menu right
after Forside, so they do not crowd the front door.

**Events**:
Mirrors the Calendar. Rebuilt once daily; staleness up to 24h is accepted.

**Find os**:
Directions to the hidden staircase. Text info now; map image with arrows
replaces the vagueness later.

**Historie**:
The club's story since the 1960s. Ships as a framework; content comes from
the maintainer interviewing members.

**Theme**:
hugo-PaperMod, customised until it becomes something we like. PaperMod is the
base, not the look — the vintage/accessible styling is ours, layered on top.
