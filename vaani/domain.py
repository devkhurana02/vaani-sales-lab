"""Deterministic campaign policy. No provider, HTTP, or database dependencies."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

IST = ZoneInfo("Asia/Kolkata")
CITIES = {"delhi": "Delhi", "दिल्ली": "Delhi", "bengaluru": "Bengaluru", "bangalore": "Bengaluru", "बेंगलुरु": "Bengaluru"}
INTENTS = {"affirm", "deny", "provide", "opt_out", "human", "price", "range", "discount", "unknown", "switch_language"}
TERMINAL = {"booked", "opted_out", "declined", "handoff", "not_serviceable"}
PRODUCT = {"name": "Aster One", "price_inr": 95000, "range_km": 90, "cities": ["Delhi", "Bengaluru"]}


@dataclass
class Decision:
    intent: str = "unknown"
    city: str | None = None
    budget: int | None = None
    timeline: str | None = None
    slot_choice: int | None = None
    language: str | None = None

    @classmethod
    def validated(cls, raw):
        if not isinstance(raw, dict) or set(raw) - set(cls.__dataclass_fields__):
            raise ValueError("Invalid decision shape")
        d = cls(**raw)
        if d.intent not in INTENTS or d.language not in (None, "en", "hi"):
            raise ValueError("Invalid intent or language")
        if d.city is not None and (not isinstance(d.city, str) or not 1 <= len(d.city) <= 60):
            raise ValueError("Invalid city")
        if d.budget is not None and (type(d.budget) is not int or not 1 <= d.budget <= 10000000):
            raise ValueError("Invalid budget")
        if d.timeline not in (None, "this_week", "this_month", "later"):
            raise ValueError("Invalid timeline")
        if d.slot_choice is not None and (type(d.slot_choice) is not int or d.slot_choice not in (1, 2)):
            raise ValueError("Invalid slot")
        return d


def fresh_state(language):
    return {"stage": "consent", "consent": False, "language": language,
            "city": None, "budget": None, "timeline": None, "slots": [],
            "selected_slot": None, "booking_id": None, "clarifications": 0}


def choose(s, en, hi):
    return hi if s["language"] == "hi" else en


def greeting(s):
    return choose(s,
        "Hi, I’m Vaani, an AI assistant for the fictional Aster scooter demo. May I ask a few questions to help arrange a test ride? This sandbox stores the conversation locally.",
        "नमस्ते, मैं वाणी हूँ, काल्पनिक Aster स्कूटर डेमो की AI सहायक। टेस्ट राइड के लिए क्या मैं कुछ सवाल पूछ सकती हूँ? यह डेमो बातचीत आपके कंप्यूटर पर सेव करता है।")


def slot_label(slot):
    return datetime.fromisoformat(slot).strftime("%d %b, %I:%M %p") + " IST"


def new_slots(now=None):
    now = now or datetime.now(IST)
    tomorrow = (now.astimezone(IST) + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
    return [tomorrow.isoformat(), tomorrow.replace(hour=16).isoformat()]


def question(s):
    stage = s["stage"]
    if stage == "consent":
        return choose(s, "May I continue with a few test-ride questions?", "क्या मैं टेस्ट राइड के लिए कुछ सवाल पूछ सकती हूँ?")
    if stage == "city":
        return choose(s, "Which city are you in? We offer demo rides in Delhi and Bengaluru.", "आप किस शहर में हैं? डेमो राइड दिल्ली और बेंगलुरु में उपलब्ध हैं।")
    if stage == "budget":
        return choose(s, "What is your approximate scooter budget in rupees?", "स्कूटर के लिए आपका लगभग कितना बजट है, रुपये में?")
    if stage == "timeline":
        return choose(s, "When are you considering buying: this week, this month, or later?", "आप कब खरीदना चाहेंगे: इसी हफ़्ते, इस महीने, या बाद में?")
    if stage == "slot":
        labels = [slot_label(v) for v in s["slots"]]
        if len(labels) < 2:
            return choose(s, "No demo slots remain. I’ve marked this for human follow-up; no appointment was booked.", "डेमो स्लॉट उपलब्ध नहीं हैं। मानव सहायता के लिए दर्ज किया है; कोई बुकिंग नहीं हुई।")
        return choose(s, f"Choose a demo slot: 1 — {labels[0]}, or 2 — {labels[1]}. Which works?", f"डेमो स्लॉट चुनें: 1 — {labels[0]}, या 2 — {labels[1]}। कौन सा ठीक रहेगा?")
    if stage == "confirm":
        label = slot_label(s["selected_slot"])
        return choose(s, f"Please confirm: a demo test ride in {s['city']} on {label}. Shall I book it?", f"कृपया पुष्टि करें: {s['city']} में {label} पर डेमो टेस्ट राइड। क्या मैं बुक कर दूँ?")
    return ""


def advance(s, d, now=None):
    """Mutate state; return reply and requested effect. Booking commits elsewhere."""
    if s["stage"] in TERMINAL:
        return choose(s, "This conversation has ended. Start a new session for another request.", "यह बातचीत समाप्त हो चुकी है। नए अनुरोध के लिए नया सत्र शुरू करें।"), None
    if d.language:
        s["language"] = d.language
    if d.intent == "opt_out":
        s["stage"] = "opted_out"
        return choose(s, "Understood. I’ll stop this demo conversation. No further outreach is initiated by this app.", "समझ गई। यह डेमो बातचीत यहीं बंद करती हूँ। यह ऐप आगे कोई कॉल शुरू नहीं करेगा।"), None
    if d.intent == "human":
        s["stage"] = "handoff"
        return choose(s, "I’ve marked this session for human follow-up in the demo. No real transfer or call has been made.", "डेमो में मानव सहायता के लिए दर्ज कर दिया है। कोई असली कॉल या ट्रांसफ़र नहीं हुआ है।"), None
    if d.intent in {"price", "range", "discount"}:
        facts = {
            "price": ("The fictional Aster One is ₹95,000 in this demo.", "इस डेमो में काल्पनिक Aster One की कीमत 95,000 रुपये है।"),
            "range": ("The demo catalog lists 90 km; real-world range varies. These are fictional product details.", "डेमो कैटलॉग में 90 किलोमीटर रेंज है; वास्तविक रेंज अलग हो सकती है। ये काल्पनिक विवरण हैं।"),
            "discount": ("There is no approved discount in the demo catalog, so I can’t promise one.", "डेमो कैटलॉग में कोई मंज़ूर छूट नहीं है, इसलिए मैं छूट का वादा नहीं कर सकती।")}
        return choose(s, *facts[d.intent]) + " " + question(s), None
    if d.intent == "switch_language":
        return question(s), None
    if s["stage"] == "consent":
        if d.intent == "deny":
            s["stage"] = "declined"
            return choose(s, "No problem. I’ll end the demo here.", "कोई बात नहीं। डेमो यहीं समाप्त करती हूँ।"), None
        if d.intent != "affirm":
            return question(s), None
        s["consent"] = True
        s["stage"] = "city"
        # Consent and profile capture are intentionally separate turns.
        return question(s), None
    changed = False
    for field in ("city", "budget", "timeline"):
        value = getattr(d, field)
        if value is not None:
            if field == "city":
                value = CITIES.get(value.lower(), value.strip().title())
            if s[field] != value:
                s[field] = value
                changed = True
    if changed:
        s["clarifications"] = 0
        s["selected_slot"] = None
        s["slots"] = []
        if s["city"] and s["city"] not in PRODUCT["cities"]:
            s["stage"] = "not_serviceable"
            return choose(s, "We don’t offer demo rides in that city. No booking was made.", "उस शहर में डेमो राइड उपलब्ध नहीं है। कोई बुकिंग नहीं हुई।"), None
        for field in ("city", "budget", "timeline"):
            if s[field] is None:
                s["stage"] = field
                return question(s), None
        s["stage"] = "slot"
        s["slots"] = new_slots(now)
        prefix = ""
        if s["budget"] < PRODUCT["price_inr"]:
            prefix = choose(s, "The demo price is above your budget; a test ride is still available without a purchase commitment. ", "डेमो की कीमत आपके बजट से ज़्यादा है; बिना खरीदने की बाध्यता के टेस्ट राइड ले सकते हैं। ")
        return prefix + question(s), None
    if s["stage"] == "slot" and d.slot_choice:
        s["selected_slot"] = s["slots"][d.slot_choice - 1]
        s["stage"] = "confirm"
        s["clarifications"] = 0
        return question(s), None
    if s["stage"] == "confirm":
        if d.intent == "affirm":
            return "", "book"
        if d.intent == "deny":
            s["selected_slot"] = None
            s["stage"] = "slot"
            return question(s), None
    s["clarifications"] += 1
    if s["clarifications"] >= 3:
        s["stage"] = "handoff"
        return choose(s, "I’m having trouble understanding. I’ve flagged this demo session for human review; nothing has been booked.", "समझने में परेशानी हो रही है। डेमो में मानव समीक्षा के लिए दर्ज किया है; बुकिंग नहीं हुई।"), None
    return choose(s, "I didn’t catch that. ", "मैं समझ नहीं पाई। ") + question(s), None

