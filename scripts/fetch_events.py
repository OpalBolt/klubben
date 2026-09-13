#!/usr/bin/env python3
"""Hent klubbens offentlige Google-kalender som ICS og skriv Hugo-data.

Kun stdlib — ingen pip-afhængigheder. Kalenderen er offentlig, så der
hentes via /public/basic.ics uden OAuth eller service account. Outputtet
(data/calendar.json) er byggeoutput: gitignored, genereret per build,
aldrig committet — sitet spejler kalenderen og gemmer begivenheder
ingen andre steder.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

ICS_URL = "https://calendar.google.com/calendar/ical/{cid}/public/basic.ics"

try:
    from zoneinfo import ZoneInfo
    CPH = ZoneInfo("Europe/Copenhagen")
except Exception:
    CPH = None

DAYS_DK = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
MONTHS_DK = ["januar", "februar", "marts", "april", "maj", "juni",
             "juli", "august", "september", "oktober", "november", "december"]


def unfold(text):
    """RFC 5545 3.1: fortsættelseslinjer starter med mellemrum/tab."""
    lines = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def unescape(text):
    return (text.replace("\\,", ",").replace("\\;", ";")
                .replace("\\n", "\n").replace("\\N", "\n"))


def parse_dt(value):
    """ICS-dato/tid -> (date eller datetime, all_day)."""
    v = value.strip()
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", v)
    if m:
        return date(*map(int, m.groups())), True
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)", v)
    if not m:
        return None, False
    y, mo, d, h, mi, s = map(int, m.groups()[:6])
    if m.group(7) == "Z":
        dt = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
        if CPH is not None:
            return dt.astimezone(CPH), False
        print("advarsel: tzdata mangler — UTC-tid bruges ukonverteret",
              file=sys.stderr)
        return dt, False
    # naiv tid = lokal vægtid i klubben (Europe/Copenhagen), konverteres ikke
    return datetime(y, mo, d, h, mi, s), False


def parse_ics(text):
    """Træk SUMMARY/DTSTART/DTEND/LOCATION ud af hver VEVENT."""
    events = []
    current = None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None and "dtstart" in current:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        head, _, value = line.partition(":")
        name = head.split(";", 1)[0].upper()
        if name in ("SUMMARY", "DTSTART", "DTEND", "LOCATION"):
            current[name.lower()] = value

    parsed = []
    for ev in events:
        start, all_day = parse_dt(ev.get("dtstart", ""))
        if start is None:
            continue
        end = None
        if "dtend" in ev:
            end, _ = parse_dt(ev["dtend"])
        parsed.append({
            "title": unescape(ev.get("summary", "(uden titel)")),
            "start": start,
            "end": end,
            "all_day": all_day,
            "location": unescape(ev.get("location", "")),
        })
    return parsed


def _dk_time(dtm):
    return f"kl. {dtm.hour:02d}.{dtm.minute:02d}"


def render_events(raw, today=None, days=60, cap=25):
    """Filtrér kommende begivenheder og gør dem klar til Hugo/sitet."""
    today = today or date.today()
    horizon = today + timedelta(days=days)
    out = []
    for ev in raw:
        start = ev["start"]
        if isinstance(start, datetime):
            start_date, start_time = start.date(), start
        else:
            start_date, start_time = start, None
        if not (today <= start_date <= horizon):
            continue
        if ev["all_day"]:
            time_dk = ""
        elif start_time is not None:
            time_dk = _dk_time(start_time)
            end = ev["end"]
            if (isinstance(end, datetime) and end.date() == start_date):
                time_dk += "–" + _dk_time(end).split("kl. ")[1]
        else:
            time_dk = ""
        day = start_date
        out.append({
            "title": ev["title"],
            "date_dk": f"{DAYS_DK[day.weekday()]} d. {day.day}. {MONTHS_DK[day.month - 1]}",
            "time_dk": time_dk,
            "location": ev["location"],
            "start_iso": start_time.strftime("%Y-%m-%dT%H:%M:%S") if start_time
                         else f"{day.isoformat()}T00:00:00",
        })
    out.sort(key=lambda e: e["start_iso"])
    return out[:cap]


def fetch(calendar_id):
    url = ICS_URL.format(cid=urllib.parse.quote(calendar_id, safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "klubben-site/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        sys.exit(f"fejl: kunne ikke hente kalenderen (HTTP {e.code}) — "
                 "tjek at kalenderen er offentlig og id'et er rigtigt")
    except urllib.error.URLError as e:
        sys.exit(f"fejl: netværksproblem ved hentning af kalenderen: {e.reason}")


def self_test():
    """Kør parseren over indlejrede mini-fixtures — den ene tjek for slizen."""
    ok = True

    def check(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print(f"FAIL {name}: {got!r} != {want!r}")
        else:
            print(f"ok   {name}")

    # 1. foldet SUMMARY + naiv datetime + unescaping
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
           "SUMMARY:Lille\n  poolturnering\\, kold\\; hygge\r\n"
           "DTSTART:20260916T190000\r\nDTEND:20260916T220000\r\n"
           "LOCATION:Kælderen\r\nEND:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2026, 9, 1))
    check("foldet+unescape titel", evs[0]["title"], "Lille poolturnering, kold; hygge")
    check("dato_dk onsdag", evs[0]["date_dk"], "onsdag d. 16. september")
    check("tidsinterval", evs[0]["time_dk"], "kl. 19.00–22.00")
    check("location", evs[0]["location"], "Kælderen")
    check("start_iso", evs[0]["start_iso"], "2026-09-16T19:00:00")

    # 2. heldagsbegivenhed (VALUE=DATE-form, dato uden tid)
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Traditionsdag\r\n"
           "DTSTART;VALUE=DATE:20210404\r\nEND:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2021, 4, 1))
    check("heldags time_dk tom", evs[0]["time_dk"], "")
    check("heldags dato", evs[0]["date_dk"], "søndag d. 4. april")
    check("heldags start_iso", evs[0]["start_iso"], "2021-04-04T00:00:00")

    # 3. UTC-tid konverteres til København (16. sept 2026 = CEST, +2)
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Z-tid\r\n"
           "DTSTART:20260916T170000Z\r\nEND:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2026, 9, 1))
    if CPH is not None:
        check("Z->CPH kl. 19.00", evs[0]["time_dk"], "kl. 19.00")
    else:
        check("uden tzdata: UTC vægtid", evs[0]["time_dk"], "kl. 17.00")

    # 4. gamle begivenheder filtreres fra, tomme lister er gyldige
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Gamle nyheder\r\n"
           "DTSTART:20200101T190000\r\nEND:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2026, 9, 1))
    check("fortid filtreret", evs, [])

    print("self-test", "OK" if ok else "FEJLEDE")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calendar-id", help="offentligt kalender-id, fx ...@group.calendar.google.com")
    ap.add_argument("--out", default="data/calendar.json")
    ap.add_argument("--days", type=int, default=60, help="horisont i dage (standard 60)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    if not args.calendar_id:
        ap.error("--calendar-id er påkrævet (eller --self-test)")

    text = fetch(args.calendar_id)
    if "BEGIN:VCALENDAR" not in text:
        sys.exit("fejl: svaret er ikke gyldig ICS — tjek kalender-id'et")
    events = render_events(parse_ics(text), days=args.days)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(events)} kommende begivenheder skrevet til {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
