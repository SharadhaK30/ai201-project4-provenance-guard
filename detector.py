from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from statistics import mean, pstdev
from typing import Any


AI_PHRASES = {
    "as an ai language model",
    "it is important to note",
    "in conclusion",
    "delve into",
    "tapestry",
    "leverage",
    "robust",
    "seamless",
    "furthermore",
    "moreover",
    "additionally",
    "ultimately",
}

HUMAN_MARKERS = {
    "i think",
    "i remember",
    "my draft",
    "honestly",
    "rough notes",
    "not sure",
    "typo",
    "lol",
}


@dataclass(frozen=True)
class Signal:
    name: str
    score: float
    weight: float
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClassificationResult:
    classification: str
    confidence: float
    ai_likelihood: float
    transparency_label: str
    recommended_action: str
    signals: list[Signal]
    rationale: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signals"] = [signal.to_dict() for signal in self.signals]
        return payload


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def lexical_diversity_signal(words: list[str]) -> Signal:
    if not words:
        return Signal("lexical_diversity", 0.5, 0.18, "No words available for lexical analysis.")
    unique_ratio = len(set(words)) / len(words)
    score = _clamp((0.58 - unique_ratio) / 0.32)
    return Signal(
        "lexical_diversity",
        round(score, 3),
        0.18,
        "Lower vocabulary variation can indicate generated or heavily templated text.",
    )


def sentence_uniformity_signal(sentences: list[str]) -> Signal:
    if len(sentences) < 3:
        return Signal("sentence_uniformity", 0.5, 0.16, "Too few sentences for stable rhythm analysis.")
    lengths = [len(_words(sentence)) for sentence in sentences if _words(sentence)]
    if len(lengths) < 3:
        return Signal("sentence_uniformity", 0.5, 0.16, "Too few complete sentences for stable rhythm analysis.")
    avg = mean(lengths)
    variation = pstdev(lengths) / avg if avg else 0
    score = _clamp((0.72 - variation) / 0.72)
    return Signal(
        "sentence_uniformity",
        round(score, 3),
        0.16,
        "Generated prose often has unusually even sentence rhythm.",
    )


def ai_phrase_signal(text: str) -> Signal:
    lower_text = text.lower()
    hits = [phrase for phrase in AI_PHRASES if phrase in lower_text]
    score = _clamp(len(hits) / 4)
    detail = "Matched common AI-style phrases." if hits else "No common AI-style phrases matched."
    return Signal("ai_phrase_patterns", round(score, 3), 0.24, detail)


def human_marker_signal(text: str) -> Signal:
    lower_text = text.lower()
    hits = [marker for marker in HUMAN_MARKERS if marker in lower_text]
    score = _clamp(0.5 - len(hits) * 0.18, 0.0, 0.5)
    detail = "Personal uncertainty markers reduce AI likelihood." if hits else "No strong first-person drafting markers found."
    return Signal("human_marker_absence", round(score, 3), 0.12, detail)


def punctuation_signal(text: str) -> Signal:
    if not text.strip():
        return Signal("punctuation_shape", 0.5, 0.10, "No punctuation available for analysis.")
    punctuation = re.findall(r"[,:;.!?]", text)
    comma_ratio = text.count(",") / max(1, len(punctuation))
    exclamation_count = text.count("!")
    score = _clamp((comma_ratio * 0.7) + (0.2 if exclamation_count == 0 else -0.1))
    return Signal(
        "punctuation_shape",
        round(score, 3),
        0.10,
        "Measures whether punctuation looks polished and low-variance.",
    )


def structure_signal(text: str, sentences: list[str]) -> Signal:
    transition_starts = sum(
        1
        for sentence in sentences
        if sentence.lower().startswith(("first", "second", "finally", "overall", "in summary", "therefore"))
    )
    paragraph_count = len([part for part in text.split("\n\n") if part.strip()])
    score = _clamp((transition_starts * 0.18) + (0.18 if paragraph_count >= 3 else 0))
    return Signal(
        "template_structure",
        round(score, 3),
        0.20,
        "Looks for organized, template-like transitions and paragraphing.",
    )


def _label_for(ai_likelihood: float, confidence: float) -> tuple[str, str, str]:
    if confidence < 0.55 or 0.42 <= ai_likelihood <= 0.58:
        return (
            "uncertain",
            "Needs human review",
            "This content has mixed signals, so the system should not make a final automated claim.",
        )
    if ai_likelihood >= 0.75:
        return (
            "likely_ai_generated",
            "Likely AI-generated",
            "Show an AI-content label and allow the creator to appeal.",
        )
    if ai_likelihood <= 0.25:
        return (
            "likely_human_written",
            "Likely human-written",
            "No AI label recommended, but keep the decision in the audit log.",
        )
    return (
        "uncertain",
        "Needs human review",
        "The evidence is not strong enough for a confident automated label.",
    )


def classify_content(text: str) -> ClassificationResult:
    words = _words(text)
    sentences = _sentences(text)
    signals = [
        lexical_diversity_signal(words),
        sentence_uniformity_signal(sentences),
        ai_phrase_signal(text),
        human_marker_signal(text),
        punctuation_signal(text),
        structure_signal(text, sentences),
    ]

    weighted_score = sum(signal.score * signal.weight for signal in signals) / sum(signal.weight for signal in signals)
    length_penalty = 0.0 if len(words) >= 80 else (80 - len(words)) / 400
    phrase_boost = next(signal.score for signal in signals if signal.name == "ai_phrase_patterns") * 0.14
    human_marker_reduction = (0.5 - next(signal.score for signal in signals if signal.name == "human_marker_absence")) * 0.16
    ai_likelihood = _clamp(
        _sigmoid((weighted_score - 0.45) * 4.2) + phrase_boost - human_marker_reduction - length_penalty
    )
    distance_from_uncertain = abs(ai_likelihood - 0.5) * 2
    evidence_volume = _clamp(len(words) / 120)
    agreement = 1 - min(1.0, pstdev([signal.score for signal in signals]) if len(signals) > 1 else 0.0)
    confidence = _clamp((distance_from_uncertain * 0.55) + (evidence_volume * 0.25) + (agreement * 0.20))
    if len(words) < 25:
        confidence = min(confidence, 0.45)

    classification, transparency_label, recommended_action = _label_for(ai_likelihood, confidence)
    top_signals = sorted(signals, key=lambda signal: signal.score * signal.weight, reverse=True)[:3]
    rationale = [f"{signal.name}: {signal.explanation}" for signal in top_signals]
    warnings: list[str] = []
    if len(words) < 80:
        warnings.append("Short submissions are harder to classify reliably.")
    if classification == "uncertain":
        warnings.append("Do not treat this as a final authorship decision without human review.")

    return ClassificationResult(
        classification=classification,
        confidence=round(confidence, 3),
        ai_likelihood=round(ai_likelihood, 3),
        transparency_label=transparency_label,
        recommended_action=recommended_action,
        signals=signals,
        rationale=rationale,
        warnings=warnings,
    )
