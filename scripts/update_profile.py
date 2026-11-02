#!/usr/bin/env python3
"""Generate repository-hosted GitHub profile activity SVGs."""
import json, os, sys, urllib.error, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "shivangsagar")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path("assets")
OUT.mkdir(exist_ok=True)
BG, PANEL, BORDER, TEXT, MUTED = "#0D1117", "#171C23", "#303846", "#F0F6FC", "#929AA8"
PURPLE, BLUE, TEAL, GREEN, ORANGE = "#A78BFA", "#60B9FF", "#2DD4BF", "#4ADE80", "#FB8B65"

def api(url, method="GET", payload=None):
    headers = {"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"shivangsagar-profile-readme"}
    if TOKEN: headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode() if payload is not None else None
    if data is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def repositories():
    out, page = [], 1
    while True:
        batch = api(f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}&sort=updated")
        if not isinstance(batch, list): raise RuntimeError("Unexpected repositories API response")
        out.extend(batch)
        if len(batch) < 100: return out
        page += 1

def language_totals(repos):
    totals = Counter()
    for repo in repos:
        if repo.get("fork") or repo.get("archived"): continue
        try:
            for lang, size in api(repo["languages_url"]).items(): totals[lang] += int(size)
        except Exception as exc:
            print(f"Skipped language data for {repo.get('name')}: {exc}", file=sys.stderr)
    return totals

def contributions():
    now = datetime.now(timezone.utc)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalRepositoryContributions
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    result = api("https://api.github.com/graphql", "POST", {
        "query": query,
        "variables": {"login": USERNAME, "from": (now-timedelta(days=365)).isoformat(), "to": now.isoformat()}
    })
    if result.get("errors"): raise RuntimeError("; ".join(e.get("message","GraphQL error") for e in result["errors"]))
    user = result.get("data", {}).get("user")
    if not user: raise RuntimeError("GitHub GraphQL returned no public user")
    return user["contributionsCollection"]

def header(w,h,title,desc):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#29303B" stroke-width="1" opacity=".34"/></pattern>
<style>
.bg{{fill:{BG}}}.panel{{fill:{PANEL};stroke:{BORDER};stroke-width:1.2}}
.heading{{fill:{TEXT};font:700 17px Arial,Helvetica,sans-serif}}
.value{{fill:{TEXT};font:700 29px Arial,Helvetica,sans-serif}}
.label{{fill:{MUTED};font:12px Arial,Helvetica,sans-serif;letter-spacing:1.1px}}
.small{{fill:{MUTED};font:11px Arial,Helvetica,sans-serif}}
</style></defs>
<rect class="bg" width="{w}" height="{h}"/><rect width="{w}" height="{h}" fill="url(#grid)"/>
"""

def save(name, body):
    (OUT/name).write_text(body+"</svg>\n", encoding="utf-8")

def metrics(followers, stars, repo_count, forks):
    w,h=930,112
    s=header(w,h,"GitHub profile metrics","Public GitHub followers, stars, repositories and forks.")
    entries=[("FOLLOWERS",followers,PURPLE),("TOTAL STARS",stars,ORANGE),("PUBLIC REPOSITORIES",repo_count,BLUE),("FORKS",forks,TEAL)]
    for i,(label,value,color) in enumerate(entries):
        x=16+i*232
        s+=f'<rect x="{x}" y="12" width="216" height="88" rx="13" class="panel"/><rect x="{x}" y="12" width="4" height="88" rx="2" fill="{color}"/>'
        s+=f'<text x="{x+19}" y="40" class="label">{label}</text><text x="{x+19}" y="78" class="value">{int(value):,}</text><circle cx="{x+196}" cy="30" r="4" fill="{color}"/>'
    save("activity-metrics.svg",s)

def stats(c):
    s=header(495,190,"GitHub statistics","Public contribution counts for the last 365 days.")
    s+='<rect x="8" y="8" width="479" height="174" rx="14" class="panel"/>'
    s+='<text x="29" y="39" class="heading">GitHub statistics</text>'
    if not c:
        s+=f'<text x="29" y="91" class="value" fill="{PURPLE}">—</text><text x="29" y="119" class="label">CONTRIBUTION DATA TEMPORARILY UNAVAILABLE</text>'
    else:
        vals=[("COMMITS",c.get("totalCommitContributions",0)),("PULL REQUESTS",c.get("totalPullRequestContributions",0)),("ISSUES",c.get("totalIssueContributions",0)),("REPOS",c.get("totalRepositoryContributions",0))]
        total=c.get("contributionCalendar",{}).get("totalContributions",0)
        s+=f'<text x="29" y="91" class="value" fill="{PURPLE}">{total:,}</text><text x="29" y="113" class="label">CONTRIBUTIONS · LAST 365 DAYS</text>'
        for i,(label,value) in enumerate(vals):
            x=29+i*113
            s+=f'<text x="{x}" y="151" class="heading">{int(value):,}</text><text x="{x}" y="169" class="small">{label}</text>'
    save("github-stats.svg",s)

def langs(totals):
    s=header(495,190,"Most used programming languages","Language byte totals from non-fork, non-archived public repositories.")
    s+='<rect x="8" y="8" width="479" height="174" rx="14" class="panel"/><text x="29" y="39" class="heading">Most used languages</text>'
    top=totals.most_common(6)
    if not top: s+='<text x="29" y="91" class="label">NO PUBLIC LANGUAGE DATA AVAILABLE</text>'
    else:
        total=sum(v for _,v in top) or 1
        colors=["#A78BFA","#60A5FA","#2DD4BF","#F59E0B","#FB7185","#4ADE80"]
        x,y,bw=29,57,437
        s+=f'<rect x="{x}" y="{y}" width="{bw}" height="10" rx="5" fill="#252D38"/>'
        cursor=x
        for i,(_,count) in enumerate(top):
            seg=bw*count/total
            s+=f'<rect x="{cursor:.2f}" y="{y}" width="{seg:.2f}" height="10" fill="{colors[i]}"/>'
            cursor+=seg
        for i,(lang,count) in enumerate(top):
            lx=29+(i%2)*225; ly=91+(i//2)*28
            s+=f'<circle cx="{lx+4}" cy="{ly-4}" r="4" fill="{colors[i]}"/><text x="{lx+15}" y="{ly}" class="small" fill="{TEXT}">{escape(lang)}</text><text x="{lx+205}" y="{ly}" class="small" text-anchor="end">{count/total*100:.1f}%</text>'
    save("top-languages.svg",s)

def calendar(c):
    cal=(c or {}).get("contributionCalendar",{}); weeks=cal.get("weeks",[])
    s=header(1000,205,"GitHub contribution activity","GitHub contribution calendar for the last year.")
    total=cal.get("totalContributions")
    s+='<rect x="8" y="8" width="984" height="189" rx="14" class="panel"/>'
    if total is None:
        s+='<text x="29" y="37" class="heading">Contribution activity</text><text x="968" y="37" class="label" text-anchor="end">DATA TEMPORARILY UNAVAILABLE</text>'
    else:
        s+=f'<text x="29" y="37" class="heading">Contribution activity</text><text x="968" y="37" class="label" text-anchor="end">{total:,} CONTRIBUTIONS IN THE LAST YEAR</text>'
    colors=["#202631","#243B35","#1F6B50","#238B63","#4ADE80"]
    cell,gap,sx,sy=10,4,85,62
    for label,day in [("Mon",1),("Wed",3),("Fri",5)]:
        s+=f'<text x="29" y="{sy+day*(cell+gap)+9}" class="small">{label}</text>'
    for wi,week in enumerate(weeks[-53:]):
        for day in week.get("contributionDays",[]):
            from datetime import date
            dt=date.fromisoformat(day["date"]); dow=(dt.weekday()+1)%7
            count=int(day.get("contributionCount",0))
            level=0 if count==0 else 1 if count<=3 else 2 if count<=6 else 3 if count<=9 else 4
            x=sx+wi*(cell+gap); y=sy+dow*(cell+gap)
            s+=f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{colors[level]}"><title>{dt.isoformat()}: {count} contributions</title></rect>'
    s+='<text x="85" y="169" class="small">Less</text>'
    for i,color in enumerate(colors): s+=f'<rect x="{125+i*18}" y="160" width="11" height="11" rx="2" fill="{color}"/>'
    s+='<text x="225" y="169" class="small">More</text><text x="968" y="169" class="small" text-anchor="end">Updated by GitHub Actions</text>'
    save("contribution-activity.svg",s)

def main():
    user=api(f"https://api.github.com/users/{urllib.parse.quote(USERNAME)}")
    repos=repositories()
    stars=sum(int(r.get("stargazers_count",0)) for r in repos)
    forks=sum(int(r.get("forks_count",0)) for r in repos)
    language_data=language_totals(repos)
    try:
        contribution_data=contributions()
    except Exception as exc:
        print(f"Contribution GraphQL unavailable; continuing with REST metrics: {exc}", file=sys.stderr)
        contribution_data=None
    metrics(user.get("followers",0),stars,user.get("public_repos",len(repos)),forks)
    stats(contribution_data); langs(language_data); calendar(contribution_data)
    print(f"Updated {USERNAME}: {user.get('followers',0)} followers, {stars} stars, {len(repos)} repos")

if __name__=="__main__": main()
