"""Deterministic synthetic corpus for the three demo tenants.

Everything is generated locally from fixed seeds: no network, same output on every run.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from app.rag.ingest import DocumentIn


@dataclass(frozen=True)
class TenantSpec:
    id: str
    name: str
    currency: str
    payment_terms_days: int


TENANTS = [
    TenantSpec("acme", "Acme Logistics", "USD", 30),
    TenantSpec("globex", "Globex Retail", "EUR", 45),
    TenantSpec("initech", "Initech Software", "GBP", 15),
]

# Documents per tenant and kind. acme has one extra policy so the total is 400.
DOCS_PER_KIND = {"policy": 28, "tariff": 25, "faq": 30, "pricing_table": 25, "attachment": 25}
EXTRA_POLICY_TENANT = "acme"

POLICY_ASPECTS = {
    "refund policy": [
        "Refunds are returned to the original payment method within {d2} business days of approval.",
        "Goodwill refunds are capped at {cur} {a2} per customer per year.",
        "A refund request must include the original receipt and the reason for cancelling.",
    ],
    "late payment policy": [
        "A late fee of {a3} percent is added once an invoice is {d1} days past due.",
        "Accounts more than {d6} days overdue move to restricted mode and lose access to new exports.",
        "The late fee is waived once if the customer pays within {d2} days of the first reminder.",
    ],
    "proration rules": [
        "Mid-cycle upgrades are prorated to the day using a {d1}-day billing month.",
        "Downgrades take effect at renewal and never generate a partial refund.",
        "Seat additions are charged from the day they are provisioned.",
    ],
    "dunning schedule": [
        "The first dunning email goes out {d2} days after a failed charge, then every {d5} days.",
        "After the final notice the subscription is suspended and the card on file is flagged.",
        "Dunning messages are paused while a payment dispute is open.",
    ],
    "credit note policy": [
        "Credit notes are numbered sequentially and can only be voided, never deleted.",
        "A credit note can never exceed the invoice total it refers to.",
        "Unused credit balances expire after {d1} months and are reported to finance.",
    ],
    "tax and VAT handling": [
        "VAT is calculated from the billing country on file, not from the card issuer country.",
        "Customers with a valid tax registration number are invoiced under reverse charge.",
        "Statutory tax rates are refreshed on the first day of every month.",
    ],
    "chargeback handling": [
        "When a chargeback arrives, the evidence pack must be submitted within {d5} days.",
        "Chargeback fees of {cur} {a2} are passed on only when the customer lost the dispute.",
        "Accounts with {d5} chargebacks in a year are reviewed by the risk team.",
    ],
}
POLICY_SEGMENTS = {
    "annual plans": [
        "Yearly subscriptions are invoiced upfront and renew unless cancelled {d1} days before the anniversary.",
        "Annual subscribers receive {a3} percent off compared with month-to-month pricing.",
        "A prepaid year cannot be paused, only transferred to another workspace.",
    ],
    "monthly plans": [
        "Month-to-month subscriptions renew on the same calendar day and can be cancelled at any time.",
        "Metered usage on a monthly subscription is billed in arrears.",
        "Moving the billing day requires approval and applies from the next cycle.",
    ],
    "enterprise contracts": [
        "The signed order form overrides the standard terms for negotiated accounts.",
        "Purchase order numbers must be quoted on every invoice for these customers.",
        "Negotiated accounts have a named finance contact and a quarterly business review.",
    ],
    "usage-based plans": [
        "Consumption is metered hourly and rolled up into one line item per billing period.",
        "Customers can set a spending alert at any threshold they choose.",
        "Metered overages are invoiced after the cycle closes, never in advance.",
    ],
    "resellers": [
        "Partners invoice their own end customers and keep a wholesale margin of {a3} percent.",
        "Commission is clawed back when an end customer cancels within {d1} days.",
        "Partner statements are issued monthly with one line per managed workspace.",
    ],
}
POLICY_TOPICS = [(a, s) for a in POLICY_ASPECTS for s in POLICY_SEGMENTS]

TARIFF_ITEMS = {
    "payment processing fees": [
        "Card payments carry a fixed fee of {a2} cents plus a percentage of the amount.",
        "Fees for failed payment attempts are not refunded.",
        "Bank transfers are cheaper than cards but take {d2} business days to settle.",
    ],
    "invoice delivery fees": [
        "Invoices sent by post are charged per page and per recipient.",
        "Email delivery is free for the first {a1} invoices each month.",
        "Delivery through a customer procurement portal needs a one-time setup.",
    ],
    "API overage rates": [
        "Requests beyond the monthly quota are billed per thousand calls.",
        "Bursts above {a1} requests per minute are throttled before they are billed.",
        "Read and write calls share the same overage rate.",
    ],
    "extra seat rates": [
        "Additional users are billed per month and prorated when added.",
        "Inactive users are reclaimed after {d1} days without a login.",
        "Packs of ten users receive a bulk discount.",
    ],
    "storage rates": [
        "Stored documents are billed per gigabyte per month after the free allowance.",
        "Files move to cold storage after {d1} days at a lower rate.",
        "Deleting files stops storage charges from the next day.",
    ],
}
TARIFF_REGIONS = {
    "EU": [
        "Frankfurt hosting adds a data residency surcharge to every rate on this sheet.",
        "Customers in this area are billed in euros and pay through SEPA.",
    ],
    "US": [
        "Rates are invoiced in dollars and exclude state sales tax.",
        "Customers in this area can pay by ACH debit.",
    ],
    "APAC": [
        "Singapore hosting is reflected in these rates, which are invoiced in local currency.",
        "Payments from this area often clear through regional wallets.",
    ],
    "LATAM": [
        "Rates are quoted in dollars and settle through local acquirers.",
        "Withholding taxes are deducted at source before funds arrive.",
    ],
    "UK": [
        "Rates are billed in pounds with VAT shown separately.",
        "Payments from this area clear through Faster Payments.",
    ],
}
TARIFF_TOPICS = [(i, r) for i in TARIFF_ITEMS for r in TARIFF_REGIONS]

PRICING_PRODUCTS = {
    "core billing": [
        "The module covers invoicing, subscriptions and payment collection.",
        "Each workspace includes one sandbox environment at no charge.",
    ],
    "revenue recognition": [
        "Schedules follow ASC 606 and IFRS 15 rules.",
        "Deferred revenue reports are included with every plan.",
    ],
    "dunning automation": [
        "Failed cards are retried on a smart schedule.",
        "Recovered payments are tracked in the recovery dashboard.",
    ],
    "tax engine": [
        "Rates are determined for more than {a1} jurisdictions.",
        "Exemption certificates are stored and validated automatically.",
    ],
    "reporting suite": [
        "Scheduled exports and a SQL warehouse connector are included.",
        "Dashboards can be shared read-only with auditors.",
    ],
}
PRICING_CADENCES = {
    "monthly": [
        "Customers are billed on the first of the month and can cancel at any time.",
        "Unused seats are not credited back mid-month.",
    ],
    "annual": [
        "Two months are free when the year is paid upfront.",
        "Renewal notices go out {d1} days before the anniversary.",
    ],
    "multi-year": [
        "The price is locked for {d6} months regardless of list price changes.",
        "Early termination requires payment of the remaining commitment.",
    ],
    "pilot": [
        "The pilot is limited to {d1} days and converts automatically unless cancelled.",
        "Pilot accounts cannot exceed {a1} records.",
    ],
    "nonprofit": [
        "Proof of nonprofit status must be renewed every year.",
        "Eligible organisations receive {a3} percent off list prices.",
    ],
}
PRICING_TOPICS = [(p, c) for p in PRICING_PRODUCTS for c in PRICING_CADENCES]

FAQ_ACTIONS = {
    "download": [
        "Downloads are generated as a ZIP bundle and the link expires after {d2} hours.",
        "Large downloads are split into parts of {a1} items.",
    ],
    "dispute": [
        "Opening a dispute pauses reminders and needs a short written reason.",
        "Disputes are answered by finance within {d2} business days.",
    ],
    "schedule": [
        "Scheduled runs execute at 02:00 UTC and send a confirmation email.",
        "A schedule can be paused for up to {d1} days without losing its settings.",
    ],
    "export": [
        "Files use UTF-8 CSV with a comma delimiter and a header row.",
        "Exports include a checksum so the file can be verified after transfer.",
    ],
    "reconcile": [
        "Bank lines are matched by amount and payment reference.",
        "Unmatched lines stay in a review queue for {d1} days.",
    ],
    "archive": [
        "Archived records stay searchable for {d1} months but become read-only.",
        "Restoring an archived record needs approval from a billing admin.",
    ],
}
FAQ_OBJECTS = {
    "invoices": [
        "Invoice numbers are sequential per workspace and never reused.",
        "Each invoice keeps a PDF copy of the exact layout it was sent with.",
    ],
    "credit notes": [
        "A credit note always shows the reference of the original invoice.",
        "Credit notes cannot be edited once they have been sent.",
    ],
    "payment receipts": [
        "Receipts list the card brand and the last four digits.",
        "Receipts are emailed automatically {d2} minutes after payment.",
    ],
    "tax statements": [
        "Tax statements are grouped by jurisdiction and by quarter.",
        "Statements show the tax registration number of the seller.",
    ],
    "usage reports": [
        "Usage reports break consumption down by meter and by day.",
        "Reports cover at most {d1} days per request.",
    ],
}
FAQ_TOPICS = [(a, o) for a in FAQ_ACTIONS for o in FAQ_OBJECTS]

ATTACHMENT_ISSUES = {
    "duplicate invoice": [
        "Two invoices with the same number were generated after the billing job was retried.",
        "The second copy was voided by finance before it was sent.",
    ],
    "wrong tax rate": [
        "The standard rate was applied instead of the reduced rate for the customer.",
        "The customer holds an exemption certificate that was not linked to the account.",
    ],
    "failed payment retry": [
        "The retry hit the gateway while the card was under a fraud hold.",
        "The customer was charged once but the invoice stayed open.",
    ],
    "missing credit note": [
        "The credit was approved by support but never posted to the ledger.",
        "The customer balance still shows the full amount as due.",
    ],
    "currency mismatch": [
        "The invoice was issued in a different currency than the customer contract.",
        "Exchange rate differences were applied twice on the same line.",
    ],
}
ATTACHMENT_KINDS = {
    "customer email thread": [
        "The thread has {d2} messages and ends with the customer waiting for a reply.",
        "The customer copied their accounting department on the last message.",
    ],
    "payment gateway log": [
        "The log shows status code 402 and a decline reason from the issuing bank.",
        "Each entry carries a request id that engineering can trace.",
    ],
    "exported CSV": [
        "The export has {a1} rows and the amount column uses a comma as decimal separator.",
        "The file was truncated at the last full row before it was attached.",
    ],
    "chat transcript": [
        "The chat lasted {d5} minutes and was handled by tier one support.",
        "The customer was transferred once between two agents.",
    ],
    "contract excerpt": [
        "Clause {d2} of the contract sets payment terms of net {d1}.",
        "The excerpt is a scan and some figures are hard to read.",
    ],
}
ATTACHMENT_TOPICS = [(i, k) for i in ATTACHMENT_ISSUES for k in ATTACHMENT_KINDS]

POLICY_GENERIC = [
    "This policy applies to every {tenant} account created after {year}.",
    "Requests must be submitted through the support portal within {d1} days.",
    "Finance reviews each case and replies within {d2} business days.",
    "Amounts above {cur} {a1} need written approval from a billing manager.",
    "Exceptions are recorded in the account timeline together with the ticket number.",
    "Customers receive a reminder {d3} days before any change takes effect.",
    "Taxes already remitted to the authorities are handled separately.",
    "When a payment fails, automatic retries pause for {d4} hours so the card can be updated.",
    "Support agents must verify the invoice number and the customer identity before acting.",
    "Disputes are escalated to the finance team after {d5} unanswered contacts.",
    "All adjustments are rounded to two decimals and logged for audit.",
    "Changes take effect on the first day of the next billing cycle.",
    "A customer who disagrees with the outcome can request a second review within {d6} days.",
    "This policy was last revised in {month} and replaces all earlier internal guidance.",
]
TARIFF_GENERIC = [
    "All rates are published in {cur} and exclude any applicable taxes.",
    "Rates are reviewed every {d1} months and announced {d2} days in advance.",
    "Volume discounts start at {a1} units per month and stack with annual commitments.",
    "{tenant} bills these charges at the end of each cycle, together with the subscription.",
    "Charges apply from the first billable event and are prorated to the day.",
    "Customers can estimate their charges with the calculator in the billing settings page.",
    "Waivers require approval from the account owner and are valid for {d3} days.",
    "Minimum monthly commitments are {cur} {a2} unless the contract states otherwise.",
    "Charges appear as a separate line item on every invoice.",
    "If a rate changes during a billing cycle, the new rate only applies to later usage.",
]
PRICING_GENERIC = [
    "Prices are expressed in {cur} per month unless noted and exclude taxes.",
    "The table is valid for contracts signed in {year}.",
    "It is updated on the first business day of each quarter.",
    "Seats above the included amount are billed at the overage rate shown.",
    "Custom quotes override the table when a signed order form exists.",
    "Support should quote only the plan names listed in the table.",
    "Nonprofit and education discounts are not combined with other offers.",
    "Annual prepayment lowers the price by {a3} percent compared with the monthly column.",
]
ATTACHMENT_LINES = [
    "[{ts}] customer: We noticed a problem on invoice {inv} and need it corrected before month end.",
    "[{ts}] agent: Thanks for reaching out. I am checking invoice {inv} and what you describe.",
    "[{ts}] customer: The attachment on ticket {ticket} shows the problem from {d1} days ago.",
    "[{ts}] agent: I confirmed the problem. Finance will review it and reply within {d2} days.",
    "[{ts}] internal note: reproduced from the attachment; amount involved is {cur} {a1}.",
    "[{ts}] customer: Please confirm whether this affects the {cur} {a2} charged last cycle.",
    "[{ts}] agent: The attachment is clear. No further action is needed on the customer side.",
    "[{ts}] internal note: linked to ticket {ticket}; follow the runbook before closing.",
    "[{ts}] customer: Thanks. Could you also resend the corrected invoice {inv} by email?",
]
FAQ_GENERIC = [
    "Open Billing, choose the period, and select the action. The option appears once the period is finalized.",
    "Billing admins can do this for up to {d1} months back; older periods require a support request.",
    "Only users with the billing admin role can do this. Other roles can view the records but not change them.",
    "You can handle up to {a1} items at a time. Larger batches should be split or requested through support.",
    "There is no fee, but API usage still counts toward your quota.",
    "It usually takes less than {d2} minutes. Large accounts may need up to {d3} hours to complete.",
    "Support can do it for you after verifying your identity. Please include the record numbers in the ticket.",
    "Results are provided as PDF and CSV. Amounts use {cur} and the dates follow your account time zone.",
]
FAQ_QUESTION_STEMS = [
    "How do I {action} {obj}?",
    "Can I {action} {obj} after the billing period has closed?",
    "Who in my team is allowed to {action} {obj}?",
    "Is there a limit on how many {obj} I can {action} at once?",
    "Why can I not {action} {obj} for an older period?",
    "Does it cost anything to {action} {obj}?",
    "How long does it take to {action} {obj}?",
    "Can support {action} {obj} on my behalf?",
    "What format do I get when I {action} {obj}?",
    "Where do I find the option to {action} {obj}?",
]

MONTHS = ["January", "March", "May", "July", "September", "November"]
CUSTOMERS = [
    "Northwind Traders",
    "Blue Harbor Ltd",
    "Summit Foods",
    "Pioneer Labs",
    "Cedar & Pine",
    "Lumen Works",
    "Atlas Freight",
    "Orchid Health",
    "Falcon Media",
    "Granite Partners",
]
ITEM_NAMES = [
    "Card payment",
    "Bank transfer",
    "Direct debit",
    "Invoice email",
    "Invoice print",
    "API call batch",
    "Extra seat",
    "Archive storage",
    "Webhook delivery",
    "Priority support",
    "Data export",
    "Audit log retention",
    "Custom branding",
    "Tax report",
]
PLAN_NAMES = [
    "Starter 5",
    "Starter 10",
    "Growth 25",
    "Growth 50",
    "Scale 100",
    "Scale 250",
    "Scale 500",
    "Enterprise 1k",
    "Enterprise 5k",
    "Reseller basic",
    "Reseller plus",
    "Partner",
    "Education",
    "Nonprofit",
]


def _numbers(rng: random.Random) -> dict[str, int]:
    return {
        "year": rng.choice([2025, 2026]),
        "d1": rng.randint(7, 90),
        "d2": rng.randint(2, 15),
        "d3": rng.randint(3, 45),
        "d4": rng.randrange(6, 97, 6),
        "d5": rng.randint(2, 9),
        "d6": rng.randint(5, 60),
        "a1": rng.randrange(100, 5001, 25),
        "a2": rng.randint(20, 400),
        "a3": rng.randint(5, 30),
    }


def _paragraph(
    rng: random.Random,
    generic: list[str],
    primary: list[str],
    secondary: list[str],
    slots: dict,
    generic_count: int = 2,
) -> str:
    """Generic sentences plus sentences specific to the document's two topic dimensions."""
    sentences = rng.sample(generic, generic_count)
    sentences += rng.sample(primary, min(2, len(primary)))
    sentences += rng.sample(secondary, min(2, len(secondary)))
    rng.shuffle(sentences)
    return " ".join(s.format(**slots) for s in sentences)


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _policy(tenant: TenantSpec, topic: tuple[str, str], rng: random.Random) -> tuple[str, str]:
    aspect, segment = topic
    slots = {"tenant": tenant.name, "cur": tenant.currency, "month": rng.choice(MONTHS)}
    slots |= _numbers(rng)
    title = f"{tenant.name} {aspect} for {segment}"
    paragraphs = [
        f"{title}. "
        + _paragraph(rng, POLICY_GENERIC, POLICY_ASPECTS[aspect], POLICY_SEGMENTS[segment], slots)
    ]
    for _ in range(rng.randint(6, 8)):
        paragraphs.append(
            _paragraph(rng, POLICY_GENERIC, POLICY_ASPECTS[aspect], POLICY_SEGMENTS[segment], slots)
        )
    return title, "\n\n".join(paragraphs)


def _tariff(tenant: TenantSpec, topic: tuple[str, str], rng: random.Random) -> tuple[str, str]:
    item, region = topic
    slots = {"tenant": tenant.name, "cur": tenant.currency} | _numbers(rng)
    title = f"{tenant.name} tariff sheet: {item} in the {region} region"
    rows = [
        [
            name,
            rng.choice(["per event", "per month", "per seat", "per GB"]),
            f"{rng.uniform(0.05, 25):.2f}",
            rng.choice(["standard", "volume tier", "negotiable"]),
        ]
        for name in rng.sample(ITEM_NAMES, 9)
    ]
    paragraphs = [
        f"{title}. "
        + _paragraph(rng, TARIFF_GENERIC, TARIFF_ITEMS[item], TARIFF_REGIONS[region], slots)
    ]
    paragraphs += [
        _paragraph(rng, TARIFF_GENERIC, TARIFF_ITEMS[item], TARIFF_REGIONS[region], slots)
        for _ in range(rng.randint(3, 5))
    ]
    paragraphs.insert(2, _table(["Item", "Unit", f"Rate ({tenant.currency})", "Notes"], rows))
    paragraphs += [
        _paragraph(rng, TARIFF_GENERIC, TARIFF_ITEMS[item], TARIFF_REGIONS[region], slots)
        for _ in range(2)
    ]
    return title, "\n\n".join(paragraphs)


def _faq(tenant: TenantSpec, topic: tuple[str, str], rng: random.Random) -> tuple[str, str]:
    action, obj = topic
    slots = {"action": action, "obj": obj, "tenant": tenant.name, "cur": tenant.currency}
    slots |= _numbers(rng)
    title = f"{tenant.name} FAQ: how to {action} {obj}"
    paragraphs = []
    for stem in rng.sample(FAQ_QUESTION_STEMS, rng.randint(7, 9)):
        answer = _paragraph(
            rng, FAQ_GENERIC, FAQ_ACTIONS[action], FAQ_OBJECTS[obj], slots, generic_count=2
        )
        paragraphs.append(f"Q: {stem.format(**slots)}\nA: {answer}")
    return title, "\n\n".join(paragraphs)


def _pricing(tenant: TenantSpec, topic: tuple[str, str], rng: random.Random) -> tuple[str, str]:
    product_name, cadence = topic
    slots = {"tenant": tenant.name, "cur": tenant.currency} | _numbers(rng)
    title = f"{tenant.name} price table: {product_name} {cadence} pricing"
    rows = []
    for plan in PLAN_NAMES:
        monthly = rng.randint(20, 900)
        rows.append(
            [
                plan,
                str(rng.choice([1, 5, 10, 25, 50])),
                f"{monthly}.00",
                f"{monthly * 10}.00",
                f"{rng.uniform(1, 12):.2f}",
            ]
        )
    header = [
        "Plan",
        "Seats included",
        f"Monthly ({tenant.currency})",
        f"Annual ({tenant.currency})",
        "Overage per seat",
    ]
    primary, secondary = PRICING_PRODUCTS[product_name], PRICING_CADENCES[cadence]
    paragraphs = [f"{title}. " + _paragraph(rng, PRICING_GENERIC, primary, secondary, slots)]
    paragraphs.append(_table(header, rows))
    paragraphs += [
        _paragraph(rng, PRICING_GENERIC, primary, secondary, slots)
        for _ in range(rng.randint(3, 5))
    ]
    return title, "\n\n".join(paragraphs)


def _attachment(
    tenant: TenantSpec, topic: tuple[str, str], index: int, rng: random.Random
) -> tuple[str, str]:
    issue, kind = topic
    ticket = f"SUP-{4000 + index * 7 + rng.randint(0, 6)}"
    title = f"{tenant.name} ticket {ticket} attachment: {kind} about {issue}"
    slots = {"ticket": ticket, "cur": tenant.currency} | _numbers(rng)
    day = date(2026, 1, 5) + timedelta(days=rng.randint(0, 120))
    paragraphs = [f"{title}. Attachment captured on {day.isoformat()} for ticket {ticket}."]
    for block in range(rng.randint(6, 8)):
        lines = []
        for line in rng.sample(ATTACHMENT_LINES, 3):
            slots["ts"] = f"{day.isoformat()} {rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}"
            slots["inv"] = f"INV-{tenant.id.upper()}-{rng.randint(1, 40):04d}"
            lines.append(line.format(**slots))
        notes = rng.sample(ATTACHMENT_ISSUES[issue], 1) + rng.sample(ATTACHMENT_KINDS[kind], 1)
        lines.append("[note] " + " ".join(n.format(**slots) for n in notes))
        paragraphs.append(" ".join(lines))
        day += timedelta(days=rng.randint(0, 2) if block else 0)
    return title, "\n\n".join(paragraphs)


def build_documents() -> list[DocumentIn]:
    documents: list[DocumentIn] = []
    for tenant in TENANTS:
        topic_rng = random.Random(f"topics-{tenant.id}")
        counts = dict(DOCS_PER_KIND)
        if tenant.id == EXTRA_POLICY_TENANT:
            counts["policy"] += 1
        pools = {
            "policy": POLICY_TOPICS,
            "tariff": TARIFF_TOPICS,
            "faq": FAQ_TOPICS,
            "pricing_table": PRICING_TOPICS,
            "attachment": ATTACHMENT_TOPICS,
        }
        for kind, count in counts.items():
            for number, topic in enumerate(topic_rng.sample(pools[kind], count), start=1):
                doc_id = f"{tenant.id}-{kind.replace('_', '-')}-{number:03d}"
                rng = random.Random(doc_id)
                if kind == "policy":
                    title, body = _policy(tenant, topic, rng)
                elif kind == "tariff":
                    title, body = _tariff(tenant, topic, rng)
                elif kind == "faq":
                    title, body = _faq(tenant, topic, rng)
                elif kind == "pricing_table":
                    title, body = _pricing(tenant, topic, rng)
                else:
                    title, body = _attachment(tenant, topic, number, rng)
                documents.append(DocumentIn(doc_id, tenant.id, kind, title, body))
    return documents


def build_invoices(per_tenant: int = 40) -> list[dict]:
    invoices: list[dict] = []
    for tenant in TENANTS:
        rng = random.Random(f"invoices-{tenant.id}")
        for number in range(1, per_tenant + 1):
            issued = date(2026, 1, 1) + timedelta(days=rng.randint(0, 150))
            invoices.append(
                {
                    "id": f"INV-{tenant.id.upper()}-{number:04d}",
                    "tenant_id": tenant.id,
                    "customer_name": rng.choice(CUSTOMERS),
                    "amount_cents": rng.randint(20, 3000) * 100,
                    "currency": tenant.currency,
                    "status": rng.choices(
                        ["paid", "open", "overdue", "void", "draft"], [10, 4, 3, 1, 1]
                    )[0],
                    "issued_date": issued,
                    "due_date": issued + timedelta(days=tenant.payment_terms_days),
                }
            )
    return invoices
