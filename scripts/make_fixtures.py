"""Generate synthetic platform exports so the system runs on a clean checkout.

The copy below is placeholder text for a fictional scheduling product. It exists
to exercise the parser, the ranking rules, and the character-limit gate — it is
not a voice reference and should not be treated as one. Replace these fixtures
with a real export from the account as soon as one is available.

Seeded, so the fixtures are stable across regeneration.
"""
from __future__ import annotations
import csv, datetime as dt, random, pathlib

random.seed(20260909)
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)
TODAY = dt.date(2026, 9, 9)

HEADLINES = [
    "every call answered", "one tool, not five tabs", "book more, chase less",
    "your schedule fills itself", "stop juggling logins", "never miss a booking",
    "front desk, handled", "see it in 20 minutes", "built for small teams",
    "one login, whole business", "no-shows, handled", "calm operations",
    "your evenings back", "voicemail is not a system", "answer every call",
    "scheduling that just works", "less admin, more clients", "set up in a day",
    "the phone stops winning", "made for teams of 2-10", "your calendar, sorted",
    "cancel the spreadsheet", "one place for everything", "quiet, reliable booking",
]
DESCRIPTIONS = [
    "your bookings confirm and follow up automatically, without anyone chasing them.",
    "one platform for scheduling, notes, calls, and client messages.",
    "see how a fully booked week actually runs. book a walkthrough.",
    "replace the stack of tools that never quite talk to each other.",
    "your clients get answered. you get your afternoons back.",
    "set up in an afternoon, with your existing calendar and phone number.",
    "built for teams of 2-10 who are doing this by hand today.",
    "stop paying for five tools that each do a third of the job.",
]
PATHS = [("product", "scheduling"), ("product", "demo"), ("product", "teams")]
CAMPAIGNS = [
    ("search - brand", "brand exact"), ("search - competitor", "competitor a alt"),
    ("search - competitor", "competitor b alt"), ("search - problem", "missed calls"),
    ("search - problem", "scheduling software"), ("search - category", "practice management"),
]

def rsa_rows(n=45):
    rows = []
    for i in range(n):
        camp, group = CAMPAIGNS[i % len(CAMPAIGNS)]
        heads = random.sample(HEADLINES, 6)
        descs = random.sample(DESCRIPTIONS, 2)
        p1, p2 = random.choice(PATHS)
        start = TODAY - dt.timedelta(days=random.choice([4, 9, 15, 22, 30, 45, 60, 95, 130, 180]))
        days = (TODAY - start).days
        # a realistic long tail: most ads mediocre, a few strong, a few dead weight
        tier = random.choices(["winner", "mid", "loser", "dud"], weights=[3, 9, 5, 3])[0]
        impr = random.randint(300, 24000) if tier != "dud" else random.randint(1200, 9000)
        base_ctr = {"winner": random.uniform(6.5, 11.0), "mid": random.uniform(2.4, 4.5),
                    "loser": random.uniform(0.7, 1.7), "dud": random.uniform(0.4, 1.2)}[tier]
        clicks = max(0, round(impr * base_ctr / 100))
        cvr = {"winner": random.uniform(9, 16), "mid": random.uniform(3, 7),
               "loser": random.uniform(0.5, 3), "dud": 0.0}[tier]
        conv = round(clicks * cvr / 100)
        cost = round(clicks * random.uniform(4.2, 13.5), 2)
        rows.append({
            "Campaign": camp, "Ad group": group, "Ad ID": f"rsa-{2100+i}",
            "Ad state": "enabled",
            **{f"Headline {j+1}": h for j, h in enumerate(heads)},
            **{f"Description {j+1}": d for j, d in enumerate(descs)},
            "Path 1": p1, "Path 2": p2,
            "Final URL": "https://example.com/product",
            "Impressions": f"{impr:,}", "Clicks": f"{clicks:,}",
            "CTR": f"{base_ctr:.2f}%", "Conversions": str(conv),
            "Cost": f"${cost:,.2f}", "Start date": start.strftime("%Y-%m-%d"),
        })
    return rows

rows = rsa_rows()
cols = ["Campaign", "Ad group", "Ad ID", "Ad state"] + \
       [f"Headline {i}" for i in range(1, 7)] + [f"Description {i}" for i in range(1, 3)] + \
       ["Path 1", "Path 2", "Final URL", "Impressions", "Clicks", "CTR", "Conversions", "Cost", "Start date"]
path = OUT / "google_rsa_sample.csv"
with path.open("w", newline="", encoding="utf-8") as fh:
    # Google Ads reports really do prepend title rows before the header.
    fh.write("Ad performance report\n")
    fh.write(f"Aug 10, 2026 - Sep 9, 2026\n")
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    fh.write("Total,,,,,,,,,,,,,,,\n")
print(f"wrote {path} ({len(rows)} ads)")

# --- Meta -------------------------------------------------------------------
META_PRIMARY = [
    "you did not start this business to answer phones. the system picks up every call, books the appointment, and sends the confirmation while you stay with the client in front of you.",
    "your scheduling tool, your notes, your texts, and your phone do not talk to each other. that is the actual problem, and it is the one this fixes.",
    "every call that goes to voicemail is a client deciding whether to try someone else. this answers, books, and confirms, day or night.",
    "the spreadsheet worked when there were three of you. it is now the reason two people spend their mornings on admin.",
]
META_HEADLINES = ["every call answered", "one tool, not five", "calls answered, always",
                  "your schedule, sorted", "less admin, more clients", "see it in 20 minutes"]
META_DESCS = ["book a walkthrough", "built for small teams", "for teams of 2-10", "set up in a day"]
mrows = []
for i in range(28):
    start = TODAY - dt.timedelta(days=random.choice([6, 12, 20, 35, 55, 88, 120]))
    tier = random.choices(["winner", "mid", "loser"], weights=[3, 7, 5])[0]
    impr = random.randint(4000, 90000)
    ctr = {"winner": random.uniform(2.2, 3.8), "mid": random.uniform(0.9, 1.8), "loser": random.uniform(0.3, 0.8)}[tier]
    clicks = round(impr * ctr / 100)
    conv = round(clicks * {"winner": random.uniform(6, 12), "mid": random.uniform(2, 5), "loser": random.uniform(0, 1.5)}[tier] / 100)
    mrows.append({
        "Campaign name": random.choice(["prospecting - owners", "retargeting - site visitors", "lookalike - customers"]),
        "Ad Set Name": random.choice(["segment a", "segment b", "segment c", "broad"]),
        "Ad ID": f"meta-{9300+i}", "Delivery status": "active",
        "Primary text": random.choice(META_PRIMARY),
        "Headline": random.choice(META_HEADLINES),
        "Link Description": random.choice(META_DESCS),
        "Link URL": "https://example.com/product",
        "Impressions": str(impr), "Link clicks": str(clicks), "Results": str(conv),
        "Amount spent (USD)": f"{clicks * random.uniform(3.0, 9.0):.2f}",
        "Reporting starts": start.strftime("%Y-%m-%d"), "Reporting ends": TODAY.strftime("%Y-%m-%d"),
    })
mpath = OUT / "meta_sample.csv"
with mpath.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(mrows[0]))
    w.writeheader(); w.writerows(mrows)
print(f"wrote {mpath} ({len(mrows)} ads)")
