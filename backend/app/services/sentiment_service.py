"""
services/sentiment_service.py

WHAT THIS FILE DOES:
Lightweight, free, keyword-based detection run on each caller
transcript chunk as it arrives — two signals detected:

  1. FRUSTRATION — existing feature, flags a live call for the
     dashboard so the business owner can see it in real time.

  2. OPT-OUT REQUEST — NEW. Detects when a caller explicitly asks to
     stop being contacted ("don't call me again", "take me off your
     list", "stop calling", etc). This is what makes outbound calling
     compliant in practice, not just in theory — a do-not-call list is
     only real if numbers actually get added to it the moment someone
     asks, not only when a business owner manually manages the list.

Both are intentionally simple keyword matching (not a model call) so
they add zero latency/cost to the live transcript pipeline, which runs
on every single chunk of every call.
"""

FRUSTRATION_SIGNALS = [
    "speak to a human", "speak to someone", "talk to a person", "real person",
    "this is ridiculous", "this is stupid", "waste of time", "not helpful",
    "you don't understand", "i already told you", "i said that already",
    "forget it", "never mind", "this isn't working", "i'm frustrated",
    "i'm annoyed", "terrible service", "cancel my", "i want a refund",
    "let me speak to", "get me a manager", "this is useless",
]

OPT_OUT_SIGNALS = [
    "don't call me again", "do not call me again", "stop calling", "stop calling me",
    "take me off your list", "remove me from your list", "unsubscribe",
    "don't contact me", "do not contact me", "no more calls", "put me on your do not call list",
    "i want to opt out", "opt me out",
]


def is_frustrated(text: str) -> bool:
    """Returns True if the given caller utterance matches a known frustration signal."""
    if not text:
        return False
    lowered = text.lower()
    return any(signal in lowered for signal in FRUSTRATION_SIGNALS)


def is_opt_out_request(text: str) -> bool:
    """Returns True if the given caller utterance is an explicit request to stop being contacted."""
    if not text:
        return False
    lowered = text.lower()
    return any(signal in lowered for signal in OPT_OUT_SIGNALS)