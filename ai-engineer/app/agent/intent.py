import re
from enum import Enum


class Intent(str, Enum):
    KNOWLEDGE = "knowledge"
    INVOICE = "invoice"
    CREDIT = "credit"


INVOICE_ID_RE = re.compile(r"\bINV-[A-Z0-9]+-\d{4}\b", re.IGNORECASE)
INVOICE_LOOKUP_RE = re.compile(
    r"\b(?:look\s*up|find|check|show|view|open)\b.{0,40}\b(?:my|the)?\s*"
    r"(?:(?:latest|last|current|specific)\s+)?invoice\b"
    r"|\bwhere\s+(?:is|are)\s+(?:my|the)\s+invoice\b"
    r"|\b(?:invoice)\b.{0,40}\b(?:status|details|total|amount|balance|due|charge|charges)\b"
    r"|\b(?:status|details|total|amount|balance|due|charge|charges)\b.{0,40}\binvoice\b",
    re.IGNORECASE,
)

CREDIT_ACTION_RE = re.compile(
    # Examples: "Please issue the credit", "Issue a $41 credit"
    r"\b(?:please\s+)?(?:issue|apply|add|process|grant|give|create)\s+"
    r"(?:me\s+)?(?:(?:a|the)\s+)?"
    r"(?:\$\s?\d+(?:\.\d{1,2})?\s+)?credit\b"

    # Examples: "Can you issue the credit?"
    r"|\b(?:can|could|would)\s+you\s+(?:please\s+)?"
    r"(?:issue|apply|add|process|grant|give|create)\s+"
    r"(?:me\s+)?(?:(?:a|the)\s+)?"
    r"(?:\$\s?\d+(?:\.\d{1,2})?\s+)?credit\b"

    # Examples: "I want you to issue the credit"
    r"|\bi\s+(?:want|need|request)\s+(?:you\s+to\s+)?"
    r"(?:issue|apply|add|process|grant|give|create)\s+"
    r"(?:me\s+)?(?:(?:a|the)\s+)?"
    r"(?:\$\s?\d+(?:\.\d{1,2})?\s+)?credit\b"

    # Examples: "I want a credit for my invoice"
    r"|\bi\s+(?:want|need|request)\s+"
    r"(?:to\s+get\s+)?(?:(?:a|the)\s+)?credit"
    r"(?:\s+(?:for|on|to|please)\b|[?.!]|$)"

    # Examples: "Credit my invoice"
    r"|\bcredit\s+(?:my|the)\s+(?:invoice|account)\b",
    re.IGNORECASE,
)


def classify_intent(question: str) -> Intent:
    """Classify actionable billing requests conservatively; other questions use knowledge."""
    if CREDIT_ACTION_RE.search(question):
        return Intent.CREDIT
    if INVOICE_ID_RE.search(question) or INVOICE_LOOKUP_RE.search(question):
        return Intent.INVOICE
    return Intent.KNOWLEDGE
