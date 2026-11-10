"""Render a themed contribution-activity card (SVG) from the GitHub GraphQL API.

Usage: GITHUB_TOKEN=... python activity_card.py <username> <output.svg>
Standard library only, so it runs on a bare GitHub Actions runner.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

QUERY = """query($login:String!){user(login:$login){contributionsCollection{
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-activity-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    return cal["totalContributions"], cal["weeks"], days


def streaks(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    current = 0
    seq = days[:]
    if seq and seq[-1]["contributionCount"] == 0:  # today not counted yet
        seq = seq[:-1]
    for d in reversed(seq):
        if d["contributionCount"] == 0:
            break
        current += 1
    return current, longest


LUCIDE = {
    "activity": '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "trophy": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/><path d="m9 16 2 2 4-4"/>',
}


def fmt(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 10000 else f"{n:,}"


def render(total, weeks, days):
    current, longest = streaks(days)
    active = sum(1 for d in days if d["contributionCount"] > 0)
    best = max(days, key=lambda d: d["contributionCount"])
    best_date = dt.date.fromisoformat(best["date"]).strftime("%b %d")
    updated = dt.datetime.now(dt.timezone.utc).strftime("%b %d, %Y")

    W, H = 1200, 440
    tiles = [
        ("activity", "#A78BFA", fmt(total), "CONTRIBUTIONS · 12 MO"),
        ("flame", "#F472B6", f"{current}", "CURRENT STREAK · DAYS"),
        ("trophy", "#FBBF24", f"{longest}", "LONGEST STREAK · DAYS"),
        ("calendar", "#22D3EE", f"{active}", "ACTIVE DAYS"),
    ]
    tile_svg = []
    tw, gap, x0 = 264, 16, 48
    for i, (ic, col, num, lab) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        tile_svg.append(
            f'<g class="rise" style="animation-delay:{0.1 + i*0.12:.2f}s">'
            f'<rect x="{x}" y="118" width="{tw}" height="84" rx="16" fill="#fff" fill-opacity=".03" stroke="#fff" stroke-opacity=".08"/>'
            f'<rect x="{x + 18}" y="138" width="44" height="44" rx="12" fill="{col}" fill-opacity=".12" stroke="{col}" stroke-opacity=".35"/>'
            f'<g transform="translate({x + 29} {149}) scale(.92)" fill="none" stroke="{col}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{LUCIDE[ic]}</g>'
            f'<text x="{x + 76}" y="163" font-size="28" font-weight="800" fill="#F8FAFC">{num}</text>'
            f'<text x="{x + 76}" y="184" font-size="10.5" font-weight="600" fill="#94A3B8" letter-spacing="1.1">{lab}</text>'
            f'</g>')

    # weekly area chart
    sums = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    cx0, cx1, base, top = 48, 852, 372, 252
    peak = max(sums) or 1
    step = (cx1 - cx0) / max(len(sums) - 1, 1)
    pts = [(cx0 + i * step, base - (v / peak) * (base - top)) for i, v in enumerate(sums)]

    def smooth(points):
        d = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
        for i in range(1, len(points)):
            (x1, y1), (x2, y2) = points[i - 1], points[i]
            mx = (x1 + x2) / 2
            d += f" C{mx:.1f},{y1:.1f} {mx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"
        return d

    line = smooth(pts)
    area = line + f" L{cx1:.1f},{base} L{cx0:.1f},{base} Z"
    pi = sums.index(max(sums))
    px, py = pts[pi]
    label = f"Peak week · {max(sums)}"
    lw = len(label) * 7 + 20
    lx = min(max(px - lw / 2, cx0), cx1 - lw)

    grid = "".join(
        f'<line x1="{cx0}" y1="{base - f*(base-top):.1f}" x2="{cx1}" y2="{base - f*(base-top):.1f}" stroke="#fff" stroke-opacity=".06" stroke-dasharray="3 6"/>'
        for f in (0.5, 1.0))

    months, last = [], None
    for i, w in enumerate(weeks):
        m = dt.date.fromisoformat(w["contributionDays"][0]["date"]).strftime("%b")
        if m != last and i < len(weeks) - 2:
            if i > 0:
                months.append(f'<text x="{cx0 + i*step:.1f}" y="398" font-size="11.5" fill="#64748B">{m}</text>')
            last = m

    # weekday bars (Mon..Sun)
    wd = [0] * 7
    for d in days:
        wd[(d["weekday"] + 6) % 7] += d["contributionCount"]
    wmax = max(wd) or 1
    bx0, bw, bgap, btop = 906, 24, 11.3, 262
    bars = []
    for i, v in enumerate(wd):
        h = max(4, (v / wmax) * (base - btop))
        x = bx0 + i * (bw + bgap)
        fill = "url(#barHi)" if v == wmax else "url(#bar)"
        bars.append(
            f'<rect class="grow" style="animation-delay:{0.6 + i*0.08:.2f}s" x="{x:.1f}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="6" fill="{fill}"/>'
            f'<text x="{x + bw/2:.1f}" y="398" text-anchor="middle" font-size="11.5" fill="{"#E2E8F0" if v == wmax else "#64748B"}">{"MTWTFSS"[i]}</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">GitHub contribution activity</title>
  <desc id="d">{total} contributions in the last 12 months. Current streak {current} days, longest streak {longest} days, {active} active days. Best day {best["contributionCount"]} on {best_date}.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0A0E1A"/><stop offset=".6" stop-color="#0D1117"/><stop offset="1" stop-color="#140B26"/></linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#A78BFA" stop-opacity=".5"/><stop offset=".5" stop-color="#fff" stop-opacity=".06"/><stop offset="1" stop-color="#22D3EE" stop-opacity=".45"/></linearGradient>
    <linearGradient id="stroke" x1="0" x2="1"><stop offset="0" stop-color="#22D3EE"/><stop offset=".5" stop-color="#A78BFA"/><stop offset="1" stop-color="#F472B6"/></linearGradient>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8B5CF6" stop-opacity=".38"/><stop offset="1" stop-color="#8B5CF6" stop-opacity="0"/></linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8B5CF6" stop-opacity=".7"/><stop offset="1" stop-color="#8B5CF6" stop-opacity=".18"/></linearGradient>
    <linearGradient id="barHi" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F472B6"/><stop offset="1" stop-color="#8B5CF6" stop-opacity=".5"/></linearGradient>
    <radialGradient id="o1"><stop offset="0" stop-color="#8B5CF6" stop-opacity=".22"/><stop offset="1" stop-color="#8B5CF6" stop-opacity="0"/></radialGradient>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="24"/></clipPath>
  </defs>
  <style>
    text{{font-family:{FONT}}} .m{{font-family:{MONO}}}
    .rise{{animation:rise .7s cubic-bezier(.2,.8,.2,1) backwards}}
    @keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
    .draw{{stroke-dasharray:1;stroke-dashoffset:0;animation:draw 2.4s cubic-bezier(.4,0,.2,1) .3s backwards}}
    @keyframes draw{{from{{stroke-dashoffset:1}}to{{stroke-dashoffset:0}}}}
    .area{{animation:fade 1.6s ease 1s backwards}}
    @keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
    .grow{{transform-box:fill-box;transform-origin:bottom;animation:grow .8s cubic-bezier(.2,.8,.2,1) backwards}}
    @keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
    .ping{{transform-box:fill-box;transform-origin:center;animation:ping 1.8s cubic-bezier(0,0,.2,1) infinite}}
    @keyframes ping{{0%{{transform:scale(1);opacity:.8}}100%{{transform:scale(3);opacity:0}}}}
    @media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
  </style>
  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <circle cx="1080" cy="40" r="320" fill="url(#o1)"/>
  </g>
  <rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="23.25" fill="none" stroke="url(#edge)" stroke-width="1.5"/>

  <text x="48" y="66" font-size="24" font-weight="700" fill="#F1F5F9" letter-spacing="-.3">Contribution Activity</text>
  <text x="48" y="90" font-size="13.5" fill="#64748B">Last 12 months · public + private work</text>
  <g>
    <rect x="{W - 248}" y="48" width="200" height="30" rx="15" fill="#fff" fill-opacity=".04" stroke="#fff" stroke-opacity=".1"/>
    <circle class="ping" cx="{W - 230}" cy="63" r="3.5" fill="#22C55E"/><circle cx="{W - 230}" cy="63" r="3.5" fill="#22C55E"/>
    <text x="{W - 218}" y="67.5" class="m" font-size="11.5" fill="#94A3B8">updated {updated}</text>
  </g>

  {"".join(tile_svg)}

  <text x="48" y="240" font-size="12" font-weight="600" fill="#94A3B8" letter-spacing="1.1">WEEKLY CONTRIBUTIONS</text>
  <text x="906" y="240" font-size="12" font-weight="600" fill="#94A3B8" letter-spacing="1.1">BY WEEKDAY</text>
  {grid}
  <line x1="{cx0}" y1="{base}" x2="{cx1}" y2="{base}" stroke="#fff" stroke-opacity=".12"/>
  <path class="area" d="{area}" fill="url(#fill)"/>
  <path class="draw" d="{line}" pathLength="1" fill="none" stroke="url(#stroke)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  <g class="rise" style="animation-delay:2.2s">
    <line x1="{px:.1f}" y1="{py - 8:.1f}" x2="{px:.1f}" y2="{top - 2}" stroke="#F472B6" stroke-opacity=".5" stroke-dasharray="2 3"/>
    <rect x="{lx:.1f}" y="{top - 26}" width="{lw}" height="22" rx="11" fill="#F472B6" fill-opacity=".14" stroke="#F472B6" stroke-opacity=".45"/>
    <text x="{lx + lw/2:.1f}" y="{top - 11}" text-anchor="middle" class="m" font-size="11" fill="#FBCFE8">{label}</text>
    <circle class="ping" cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#F472B6"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="#0D1117" stroke="#F472B6" stroke-width="2.5"/>
  </g>
  {"".join(months)}
  <line x1="{bx0 - 4}" y1="{base}" x2="{bx0 + 7*(bw+bgap) - bgap + 4:.1f}" y2="{base}" stroke="#fff" stroke-opacity=".12"/>
  {"".join(bars)}
</svg>
'''


if __name__ == "__main__":
    login, out = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
    total, weeks, days = fetch(login, token)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        f.write(render(total, weeks, days))
    print(f"wrote {out}: {total} contributions")
