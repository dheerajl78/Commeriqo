import json
from pathlib import Path
from typing import List, Tuple

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = BASE_DIR / "artifacts"
INTENT_MODEL_PATH = ARTIFACT_DIR / "intent_model.joblib"
INTENTS_PATH = BASE_DIR / "intents.json"


def load_intents() -> Tuple[list, list]:
    with INTENTS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    texts = []
    labels = []
    for item in data.get("intents", []):
        intent = item.get("intent")
        for ex in item.get("examples", []):
            texts.append(ex)
            labels.append(intent)
    return texts, labels


def train_intent_model() -> Pipeline:
    texts, labels = load_intents()
    if not texts:
        raise ValueError("No training data found in intents.json")

    model = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), stop_words="english")),
            ("clf", LogisticRegression(max_iter=300)),
        ]
    )
    model.fit(texts, labels)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, INTENT_MODEL_PATH)
    return model


def load_or_train_intent_model() -> Pipeline:
    if INTENT_MODEL_PATH.exists():
        model_mtime = INTENT_MODEL_PATH.stat().st_mtime
        intents_mtime = INTENTS_PATH.stat().st_mtime
        if intents_mtime <= model_mtime:
            return joblib.load(INTENT_MODEL_PATH)
    return train_intent_model()


def predict_intent(model: Pipeline, text: str) -> Tuple[str, float]:
    proba = model.predict_proba([text])[0]
    classes = model.classes_
    idx = proba.argmax()
    return classes[idx], float(proba[idx])


def predict_top_intents(model: Pipeline, text: str, k: int = 2) -> List[Tuple[str, float]]:
    proba = model.predict_proba([text])[0]
    classes = model.classes_
    ranked = proba.argsort()[::-1][:k]
    return [(classes[i], float(proba[i])) for i in ranked]
