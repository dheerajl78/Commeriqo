import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.model import load_or_train_intent_model, predict_intent, predict_top_intents

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="E-Commerce AI Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    products: Optional[List[Dict]] = None
    order: Optional[Dict] = None
    intent_suggestions: Optional[List[Dict]] = None


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


PRODUCTS = load_json(BASE_DIR / "products.json")
ORDERS = {o["order_id"]: o for o in load_json(BASE_DIR / "orders.json")}
UCI_PACKAGES = {p["order_id"]: p for p in load_json(BASE_DIR / "uci_packages.json")}

PRODUCT_TEXTS = [
    f"{p['name']} {p['category']} {p['description']} {p.get('color', '')}"
    for p in PRODUCTS
]
PRODUCT_VECTORIZER = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
PRODUCT_MATRIX = PRODUCT_VECTORIZER.fit_transform(PRODUCT_TEXTS)
PRODUCT_CHAR_VECTORIZER = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
PRODUCT_CHAR_MATRIX = PRODUCT_CHAR_VECTORIZER.fit_transform(PRODUCT_TEXTS)

INTENT_MODEL = load_or_train_intent_model()


FAQ_RESPONSES = {
    "return policy": "You can return items within 30 days of delivery for a full refund.",
    "shipping": "Standard shipping takes 3-5 business days. Expedited shipping is 1-2 business days.",
    "international": "Yes, we ship internationally to select countries.",
    "payment": "We accept major credit cards, PayPal, and Apple Pay.",
    "support": "You can reach support at support@shopco.example or via this chat."
}


def parse_price_constraints(text: str) -> Tuple[Optional[float], Optional[float]]:
    text = text.lower()
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]

    if "between" in text and len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])

    if any(k in text for k in ["under", "below", "less than", "at most", "max"]):
        if nums:
            return None, nums[0]

    if any(k in text for k in ["over", "above", "more than", "at least", "min"]):
        if nums:
            return nums[0], None

    return None, None


def extract_order_id(text: str) -> Optional[str]:
    match = re.search(r"\b(\d{4,8})\b", text)
    return match.group(1) if match else None


def extract_uci_order_id(text: str) -> Optional[str]:
    match = re.search(r"\b(UCI-\d{4})\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    digits = extract_order_id(text)
    if digits and len(digits) == 4:
        return f"UCI-{digits}"
    return None


def product_search(query: str, limit: int = 5) -> List[Dict]:
    min_price, max_price = parse_price_constraints(query)
    query_tokens = set(re.findall(r"[a-zA-Z]+", query.lower()))

    results = []
    for p in PRODUCTS:
        if min_price is not None and p["price"] < min_price:
            continue
        if max_price is not None and p["price"] > max_price:
            continue

        text = f"{p['name']} {p['category']} {p['description']} {p.get('color', '')}".lower()
        score = sum(1 for t in query_tokens if t in text)
        if score > 0:
            results.append((score, p))

    results.sort(key=lambda x: (-x[0], x[1]["price"]))
    return [p for _, p in results[:limit]]


def product_recommendations(query: str, limit: int = 5) -> List[Dict]:
    q_vec = PRODUCT_VECTORIZER.transform([query])
    q_char = PRODUCT_CHAR_VECTORIZER.transform([query])
    sims_word = cosine_similarity(q_vec, PRODUCT_MATRIX)[0]
    sims_char = cosine_similarity(q_char, PRODUCT_CHAR_MATRIX)[0]
    sims = (sims_word + sims_char) / 2
    ranked = sims.argsort()[::-1][:limit]
    return [PRODUCTS[i] for i in ranked if sims[i] > 0]


def build_smart_bundle(query: str, base_products: List[Dict], limit: int = 5) -> List[Dict]:
    if not any(k in query.lower() for k in ["kit", "bundle", "starter", "pack"]):
        return base_products

    category_priority = ["running shoes", "hoodie", "earbuds", "smartwatch", "backpack"]
    picked = {p["id"] for p in base_products}
    bundle = list(base_products)
    for cat in category_priority:
        for p in PRODUCTS:
            if p["id"] in picked:
                continue
            if p["category"] == cat:
                bundle.append(p)
                picked.add(p["id"])
                break
        if len(bundle) >= limit:
            break
    return bundle[:limit]


def handle_faq(text: str) -> str:
    lower = text.lower()
    if "return" in lower:
        return FAQ_RESPONSES["return policy"]
    if "ship" in lower:
        return FAQ_RESPONSES["shipping"]
    if "international" in lower:
        return FAQ_RESPONSES["international"]
    if "payment" in lower or "pay" in lower:
        return FAQ_RESPONSES["payment"]
    if "support" in lower or "contact" in lower:
        return FAQ_RESPONSES["support"]
    return "I can help with returns, shipping, payments, and support. What do you need?"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    text = req.message.strip()
    intent, confidence = predict_intent(INTENT_MODEL, text)
    suggestions = [
        {"intent": i, "confidence": c}
        for i, c in predict_top_intents(INTENT_MODEL, text, k=2)
    ]

    if confidence < 0.35:
        intent = "fallback"

    lower_text = text.lower()
    if any(k in lower_text for k in ["uci", "mailroom", "mail room", "campus package"]):
        intent = "uci_package_help"

    if intent == "greeting":
        return ChatResponse(
            reply="Hi! What are you shopping for today?",
            intent=intent,
            confidence=confidence,
            intent_suggestions=suggestions,
        )

    if intent == "goodbye":
        return ChatResponse(
            reply="Thanks for visiting! If you need anything else, just ask.",
            intent=intent,
            confidence=confidence,
            intent_suggestions=suggestions,
        )

    if intent == "order_tracking":
        order_id = extract_order_id(text)
        if not order_id:
            return ChatResponse(
                reply="Please provide your 4-8 digit order ID.",
                intent=intent,
                confidence=confidence,
                intent_suggestions=suggestions,
            )
        order = ORDERS.get(order_id)
        if not order:
            return ChatResponse(
                reply=f"I couldn't find order {order_id}. Please double-check the ID.",
                intent=intent,
                confidence=confidence,
                intent_suggestions=suggestions,
            )
        reply = f"Order {order_id} is {order['status']}. Estimated delivery: {order['eta']}."
        return ChatResponse(
            reply=reply,
            intent=intent,
            confidence=confidence,
            order=order,
            intent_suggestions=suggestions,
        )

    if intent == "uci_package_help":
        uci_id = extract_uci_order_id(text)
        if not uci_id:
            return ChatResponse(
                reply="Please share your UCI package ID (e.g., UCI-1001) or the last 4 digits.",
                intent=intent,
                confidence=confidence,
                intent_suggestions=suggestions,
            )
        package = UCI_PACKAGES.get(uci_id)
        if not package:
            reply = (
                f"I couldn't find {uci_id}. I've emailed UCI Mail Services for a trace and will update you here. "
                "If you'd like, I can also start a refund request."
            )
            return ChatResponse(
                reply=reply,
                intent=intent,
                confidence=confidence,
                intent_suggestions=suggestions,
            )

        status = package["status"].lower()
        triage = "general"
        if any(k in text.lower() for k in ["missing", "not received", "lost", "didn't get", "no package"]):
            triage = "missing"
        if any(k in text.lower() for k in ["late", "delay", "delayed", "still waiting"]):
            triage = "delayed"
        if any(k in text.lower() for k in ["delivered", "received", "picked up"]):
            triage = "delivered"

        if "received" in status or "delivered" in status:
            reply = f"Your package {uci_id} is at UCI Mail Services. Do you want pickup details or a hold request?"
            if triage == "missing":
                reply = f"{uci_id} shows as delivered to campus. I’ll file a trace with the mailroom and update you here."
        elif "in transit" in status:
            reply = f"Your package {uci_id} is still in transit. ETA: {package['eta']}."
            if triage == "delayed":
                reply += " I can open a delay trace with the carrier if you want."
        else:
            reply = f"Your package {uci_id} status is {package['status']}. ETA: {package['eta']}."
        order_card = {
            "order_id": uci_id,
            "status": package["status"],
            "eta": package["eta"],
            "items": [package.get("location", "UCI Mail Services")],
        }
        return ChatResponse(
            reply=reply,
            intent=intent,
            confidence=confidence,
            order=order_card,
            intent_suggestions=suggestions,
        )

    if intent == "refund_request":
        return ChatResponse(
            reply="Refunds are available within 30 days of delivery. If you'd like, share your order ID and I can help start a return.",
            intent=intent,
            confidence=confidence,
            intent_suggestions=suggestions,
        )

    if intent in ["product_search", "product_recommendation"]:
        if intent == "product_search":
            products = product_search(text)
            if not products:
                products = product_recommendations(text)
            products = build_smart_bundle(text, products)
            reply = "Here are some options that match:" if products else "I couldn't find a match. Try a different category or price."
            return ChatResponse(
                reply=reply,
                intent=intent,
                confidence=confidence,
                products=products or None,
                intent_suggestions=suggestions,
            )

        products = product_recommendations(text)
        products = build_smart_bundle(text, products)
        reply = "Based on what you asked, I recommend:" if products else "I need more details. What type of product are you looking for?"
        return ChatResponse(
            reply=reply,
            intent=intent,
            confidence=confidence,
            products=products or None,
            intent_suggestions=suggestions,
        )

    if intent == "faq" or intent == "fallback":
        reply = handle_faq(text)
        if intent == "fallback":
            reply = f"I might have misunderstood. Did you mean: {', '.join([s['intent'] for s in suggestions])}?"
        return ChatResponse(
            reply=reply,
            intent=intent,
            confidence=confidence,
            intent_suggestions=suggestions,
        )

    return ChatResponse(
        reply="I'm not sure I understood. Can you rephrase?",
        intent=intent,
        confidence=confidence,
        intent_suggestions=suggestions,
    )
