#!/usr/bin/env python3
"""Hent klubbens offentlige Google-kalender som ICS og skriv Hugo-data.

Kun stdlib — ingen pip-afhængigheder. Kalenderen er offentlig, så der
hentes via /public/basic.ics uden OAuth eller service account. Outputtet
(data/calendar.json) er byggeoutput: gitignored, genereret per build,
aldrig committet — sitet spejler kalenderen og gemmer begivenheder
ingen andre steder.
"""

import argparse
import calendar
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
_WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


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


def parse_rrule(value):
    """RRULE-værdi -> dict med store bogstaver, fx FREQ=WEEKLY;BYDAY=WE."""
    out = {}
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().upper()] = v.strip()
    return out


def _add_months(d, n):
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def _add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 29. feb i ikke-skudår
        return d.replace(year=d.year + n, month=2, day=28)


def _step(d, freq, interval):
    if freq == "DAILY":
        return d + timedelta(days=interval)
    if freq == "WEEKLY":
        return d + timedelta(weeks=interval)
    if freq == "MONTHLY":
        return _add_months(d, interval)
    if freq == "YEARLY":
        return _add_years(d, interval)
    return None


def _nth_weekday(year, month, token):
    """'2WE' -> dato for 2. onsdag; '-1SU' -> sidste søndag; None hvis mangler."""
    n = int(token[:-2])
    wd = _WEEKDAYS[token[-2:]]
    if n > 0:
        first = date(year, month, 1)
        day = 1 + (wd - first.weekday()) % 7 + (n - 1) * 7
        d = date(year, month, day)
    else:
        last = date(year, month, calendar.monthrange(year, month)[1])
        d = last - timedelta(days=(last.weekday() - wd) % 7 + (-n - 1) * 7)
    return d if d.month == month else None


def _occurrences(start, rrule, horizon):
    """Udvid en RRULE til konkrete datoer inden for horizon.

    Dækker FREQ=DAILY/WEEKLY/MONTHLY/YEARLY med INTERVAL, BYDAY (ugedage for
    WEEKLY, numerisk fx '2WE'/'-1SU' for MONTHLY), UNTIL og COUNT.

    ponytail: EXDATE/RDATE (aflyste/flyttede enkeltforekomster) udvides ikke,
    og MONTHLY på d. 29-31 klemmer til månedens sidste dag i stedet for at
    springe måneden over — tilføj når kalenderen faktisk bruger det.
    """
    freq = rrule.get("FREQ", "").upper()
    interval = max(1, int(rrule.get("INTERVAL", "1")))
    count = int(rrule["COUNT"]) if "COUNT" in rrule else None
    until = None
    if "UNTIL" in rrule:
        u, _ = parse_dt(rrule["UNTIL"])
        until = u.date() if isinstance(u, datetime) else u
    byday = [b.upper() for b in rrule.get("BYDAY", "").split(",") if b]
    wkst = _WEEKDAYS.get(rrule.get("WKST", "MO").upper(), 0)

    start_d = start.date() if isinstance(start, datetime) else start
    horizon_d = horizon.date() if isinstance(horizon, datetime) else horizon

    if freq == "WEEKLY" and byday and all(len(b) == 2 for b in byday):
        dates = _weekly_dates(start_d, byday, interval, wkst, horizon_d, count, until)
    elif freq == "MONTHLY" and byday and all(len(b) == 3 for b in byday):
        dates = _monthly_dates(start_d, byday, interval, horizon_d, count, until)
    elif freq in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        dates = _stepped_dates(start_d, freq, interval, horizon_d, count, until)
    else:
        print(f"advarsel: ikke-understøttet RRULE ({rrule}) — bruger kun DTSTART",
              file=sys.stderr)
        dates = [start_d]

    if isinstance(start, datetime):
        return [datetime.combine(d, start.time()) for d in dates]
    return dates


def _weekly_dates(start, byday, interval, wkst, horizon, count, until):
    wdays = sorted(_WEEKDAYS[b] for b in byday)
    anchor = start - timedelta(days=(start.weekday() - wkst) % 7)
    out, week = [], 0
    while True:
        base = anchor + timedelta(days=week * 7 * interval)
        for wd in wdays:
            d = base + timedelta(days=wd)
            if d < start:
                continue
            if d > horizon or (until is not None and d > until):
                return out
            out.append(d)
            if count is not None and len(out) >= count:
                return out
        week += 1


def _monthly_dates(start, byday, interval, horizon, count, until):
    out, m = [], 0
    while True:
        base = _add_months(start, m * interval)
        for token in byday:
            d = _nth_weekday(base.year, base.month, token)
            if d is None or d < start:
                continue
            if d > horizon or (until is not None and d > until):
                return out
            out.append(d)
            if count is not None and len(out) >= count:
                return out
        m += 1


def _stepped_dates(start, freq, interval, horizon, count, until):
    out = []
    cur = start
    while cur <= horizon:
        if until is not None and cur > until:
            break
        out.append(cur)
        if count is not None and len(out) >= count:
            break
        nxt = _step(cur, freq, interval)
        if nxt is None or nxt <= cur:
            break
        cur = nxt
    return out


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
        if name in ("SUMMARY", "DTSTART", "DTEND", "LOCATION", "RRULE"):
            current[name.lower()] = value

    parsed = []
    for ev in events:
        start, all_day = parse_dt(ev.get("dtstart", ""))
        if start is None:
            continue
        end = None
        duration = None
        if "dtend" in ev:
            end, _ = parse_dt(ev["dtend"])
            if isinstance(start, datetime) and isinstance(end, datetime):
                duration = end - start
        parsed.append({
            "title": unescape(ev.get("summary", "(uden titel)")),
            "start": start,
            "end": end,
            "all_day": all_day,
            "location": unescape(ev.get("location", "")),
            "rrule": ev.get("rrule", ""),
            "duration": duration,
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
        for start, end in _event_occurrences(ev, horizon):
            start_date = start.date() if isinstance(start, datetime) else start
            if not (today <= start_date <= horizon):
                continue
            if ev["all_day"]:
                time_dk = ""
            elif isinstance(start, datetime):
                time_dk = _dk_time(start)
                if isinstance(end, datetime) and end.date() == start_date:
                    time_dk += "–" + _dk_time(end).split("kl. ")[1]
            else:
                time_dk = ""
            out.append({
                "title": ev["title"],
                "date_dk": f"{DAYS_DK[start_date.weekday()]} d. {start_date.day}. {MONTHS_DK[start_date.month - 1]}",
                "time_dk": time_dk,
                "location": ev["location"],
                "start_iso": start.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(start, datetime)
                             else f"{start.isoformat()}T00:00:00",
            })
    out.sort(key=lambda e: e["start_iso"])
    return out[:cap]


def _event_occurrences(ev, horizon):
    """(start, end)-par for en begivenhed — udvider RRULE inden for horizon."""
    start = ev["start"]
    duration = ev.get("duration")
    if not ev.get("rrule"):
        yield start, ev["end"]
        return
    for occ in _occurrences(start, parse_rrule(ev["rrule"]), horizon):
        end = occ + duration if (duration is not None and isinstance(occ, datetime)) else None
        yield occ, end


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

    # 5. ugentlig RRULE udvides (bug: master-DTSTART i fortiden gav 0)
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Hygge og Pool\r\n"
           "DTSTART;TZID=Europe/Copenhagen:20260909T190000\r\n"
           "DTEND;TZID=Europe/Copenhagen:20260909T230000\r\n"
           "RRULE:FREQ=WEEKLY;BYDAY=WE\r\nEND:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2026, 9, 13), days=60)
    check("ugentlig antal", len(evs), 9)  # 16. sep .. 11. nov
    check("ugentlig første", evs[0]["date_dk"], "onsdag d. 16. september")
    check("ugentlig interval", evs[0]["time_dk"], "kl. 19.00–23.00")

    # 6. COUNT begrænser antal forekomster
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Kort serie\r\n"
           "DTSTART:20260916T190000\r\nRRULE:FREQ=WEEKLY;BYDAY=WE;COUNT=2\r\n"
           "END:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2026, 9, 1), days=60)
    check("COUNT=2 antal", len(evs), 2)

    # 7. månedlig numerisk BYDAY (2. onsdag)
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Brætspil\r\n"
           "DTSTART:20260909T180000\r\nRRULE:FREQ=MONTHLY;BYDAY=2WE\r\n"
           "END:VEVENT\r\nEND:VCALENDAR")
    evs = render_events(parse_ics(ics), today=date(2026, 9, 1), days=90)
    check("månedlig 2. onsdag", evs[0]["date_dk"], "onsdag d. 9. september")
    check("månedlig næste", evs[1]["date_dk"], "onsdag d. 14. oktober")

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
