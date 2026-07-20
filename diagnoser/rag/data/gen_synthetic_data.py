"""
Generates a synthetic Gmail inbox and Calendar so the Gmail/Calendar tools
have real volume to be wasteful with, without touching a real Google
account (see hackathon submission notes for why: matches the lecture's own
substitution of Open-Meteo for OpenWeatherMap to avoid auth friction).

Spans 2 years. Deliberately mixes a lot of noise (other projects, AI
newsletters, unrelated meetings) with one real "needle" thread - the
"Q3 reporting automation" project - so retrieval actually has to
discriminate, the same way the lecture's weather data needed a "month"
key before filtering worked.

Run: python -m diagnoser.rag.data.gen_synthetic_data
Writes gmail_inbox_raw.json and calendar_events_raw.json next to this file.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

HERE = Path(__file__).parent
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2026, 7, 20)
TOTAL_DAYS = (END_DATE - START_DATE).days

SENDERS_NOISE = [
    ("newsletter@aiweekly.dev", "AI Weekly"),
    ("updates@n8n.io", "n8n Updates"),
    ("no-reply@zapier.com", "Zapier"),
    ("hello@makerpad.co", "Makerpad"),
    ("priya.sharma@company.com", "Priya Sharma"),
    ("rahul.mehta@company.com", "Rahul Mehta"),
    ("hr@company.com", "HR Team"),
    ("it-support@company.com", "IT Support"),
    ("no-reply@linkedin.com", "LinkedIn"),
    ("digest@substack.com", "Substack Digest"),
]

SENDERS_PROJECT = [
    ("manager.singh@company.com", "Manager Singh"),
    ("priya.sharma@company.com", "Priya Sharma"),
    ("client.contact@bigclient.com", "Client Contact"),
]

NOISE_SUBJECTS = [
    "5 AI agent frameworks you haven't tried yet",
    "Your weekly automation digest",
    "New course: Prompt Engineering Masterclass",
    "Reminder: submit your timesheet",
    "IT maintenance window this weekend",
    "Someone viewed your profile",
    "This week in no-code: top 10 tools",
    "Team lunch RSVP",
    "Company all-hands next Friday",
    "New Zapier integration: connect 500+ apps",
    "Your subscription renews soon",
    "Weekend reading: the future of AI agents",
]

NOISE_BODIES = [
    "Check out this week's roundup of new AI tools and frameworks that "
    "shipped this week. From autonomous agents to new fine-tuning "
    "techniques, there's a lot to explore. Click through for the full "
    "breakdown and links to get started with each one.",
    "Just a friendly reminder that timesheets for this period are due by "
    "end of day Friday. Please make sure all your hours are logged "
    "correctly in the portal before the deadline.",
    "We're rolling out a new integration this week that connects your "
    "favorite apps in just a few clicks. No code required - just "
    "authenticate and start building your first automation.",
    "IT will be performing scheduled maintenance on the internal network "
    "this weekend. Some services may be intermittently unavailable "
    "between Saturday 10pm and Sunday 6am.",
]

PROJECT_SUBJECTS = [
    "Q3 reporting automation - kickoff notes",
    "Re: Q3 reporting automation - current process walkthrough",
    "Q3 reporting automation - bottleneck identified",
    "Re: Q3 reporting automation - client feedback",
    "Q3 reporting automation - build brief draft",
    "Re: Q3 reporting automation - timeline check",
    "Q3 reporting automation - demo scheduling",
    "Re: Q3 reporting automation - final review",
]

PROJECT_BODIES = [
    "Following up on our discussion - the weekly reporting process "
    "currently takes about 5 hours because the data has to be pulled "
    "manually from three different systems and reconciled by hand before "
    "the report can go out. That manual reconciliation step is the real "
    "bottleneck we should focus on automating first.",
    "Here's the current process end to end: export from the CRM every "
    "Monday, cross-reference against the finance sheet, flag "
    "discrepancies, then format into the client-facing template. Any "
    "automation needs to preserve the discrepancy-flagging step since "
    "that's what the client actually cares about.",
    "The client mentioned on the call that they mostly care about "
    "catching discrepancies early, not the formatting. That's useful - "
    "it means the AI-assisted version can prioritize the flagging logic "
    "over polishing the final document layout.",
    "Attaching the first draft of the build brief: input is the raw CRM "
    "export, the AI task is discrepancy detection against the finance "
    "sheet, human review step is a quick sign-off before sending, and "
    "output format matches the existing template so nothing downstream "
    "breaks.",
    "Can we push the demo to next Thursday instead? I want one more "
    "round of testing against last month's real data before we show it "
    "to the client, given how central that discrepancy check is.",
]

EVENT_TITLES_NOISE = [
    "Weekly team standup",
    "1:1 with manager",
    "Company all-hands",
    "AI tools demo webinar",
    "Sprint planning",
    "IT maintenance window",
    "Coffee chat with new hire",
    "Quarterly review",
]

EVENT_TITLES_PROJECT = [
    "Q3 reporting automation - kickoff",
    "Q3 reporting automation - process walkthrough with Priya",
    "Q3 reporting automation - client check-in",
    "Q3 reporting automation - build review",
    "Q3 reporting automation - demo prep",
    "Q3 reporting automation - demo day",
]


def random_date():
    return START_DATE + timedelta(days=random.randint(0, TOTAL_DAYS))


def gen_emails(n_noise=220, n_project=28):
    emails = []
    idx = 0
    for _ in range(n_noise):
        sender_email, sender_name = random.choice(SENDERS_NOISE)
        date = random_date()
        emails.append(
            {
                "id": f"email_{idx:04d}",
                "date": date.strftime("%Y-%m-%d"),
                "from": sender_email,
                "from_name": sender_name,
                "subject": random.choice(NOISE_SUBJECTS),
                "body": random.choice(NOISE_BODIES),
                "labels": ["noise"],
            }
        )
        idx += 1

    # the "needle": a real thread clustered in a ~3 month window, last year
    project_window_start = datetime(2025, 4, 1)
    for i in range(n_project):
        sender_email, sender_name = random.choice(SENDERS_PROJECT)
        date = project_window_start + timedelta(days=random.randint(0, 85))
        emails.append(
            {
                "id": f"email_{idx:04d}",
                "date": date.strftime("%Y-%m-%d"),
                "from": sender_email,
                "from_name": sender_name,
                "subject": random.choice(PROJECT_SUBJECTS),
                "body": random.choice(PROJECT_BODIES),
                "labels": ["project:q3-reporting-automation"],
            }
        )
        idx += 1

    emails.sort(key=lambda e: e["date"])
    return emails


def gen_events(n_noise=180, n_project=10):
    events = []
    idx = 0
    for _ in range(n_noise):
        date = random_date()
        events.append(
            {
                "id": f"event_{idx:04d}",
                "date": date.strftime("%Y-%m-%d"),
                "title": random.choice(EVENT_TITLES_NOISE),
                "attendees": ["aarav@company.com", "manager.singh@company.com"],
                "description": "Recurring internal meeting.",
                "labels": ["noise"],
            }
        )
        idx += 1

    project_window_start = datetime(2025, 4, 1)
    for i in range(n_project):
        date = project_window_start + timedelta(days=random.randint(0, 85))
        events.append(
            {
                "id": f"event_{idx:04d}",
                "date": date.strftime("%Y-%m-%d"),
                "title": random.choice(EVENT_TITLES_PROJECT),
                "attendees": ["aarav@company.com", "priya.sharma@company.com", "manager.singh@company.com"],
                "description": "Discussion of the Q3 reporting automation workflow, current bottlenecks, and build progress.",
                "labels": ["project:q3-reporting-automation"],
            }
        )
        idx += 1

    events.sort(key=lambda e: e["date"])
    return events


def main():
    emails = gen_emails()
    events = gen_events()

    (HERE / "gmail_inbox_raw.json").write_text(json.dumps(emails, indent=2), encoding="utf-8")
    (HERE / "calendar_events_raw.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

    print(f"Wrote {len(emails)} emails ({sum(1 for e in emails if e['labels'] != ['noise'])} project-related)")
    print(f"Wrote {len(events)} events ({sum(1 for e in events if e['labels'] != ['noise'])} project-related)")


if __name__ == "__main__":
    main()
