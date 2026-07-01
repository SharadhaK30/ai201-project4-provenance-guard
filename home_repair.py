from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


HIGH_RISK_PATTERNS = {
    "electrical_panel": r"\b(panel|breaker box|main breaker|service panel|fuse box|240v|220v)\b",
    "gas_line": r"\b(gas line|gas leak|propane|natural gas|pilot light)\b",
    "structural": r"\b(load[- ]bearing|foundation crack|structural beam|sagging roof)\b",
    "hazardous_material": r"\b(asbestos|lead paint|mold remediation|black mold)\b",
}

LOW_RISK_PATTERNS = {
    "paint": r"\b(paint|primer|wall color|touch up)\b",
    "basic_plumbing": r"\b(clogged drain|running toilet|leaky faucet|plunger)\b",
    "simple_carpentry": r"\b(cabinet hinge|squeaky door|weather stripping|caulk)\b",
    "maintenance": r"\b(filter|clean|replace batteries|smoke detector chirp)\b",
}


@dataclass(frozen=True)
class RepairGuardrailResult:
    should_answer: bool
    confidence: float
    safety_label: str
    response: str
    matched_topics: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_home_repair_question(question: str) -> RepairGuardrailResult:
    text = question.lower()
    high_risk_hits = [name for name, pattern in HIGH_RISK_PATTERNS.items() if re.search(pattern, text)]
    low_risk_hits = [name for name, pattern in LOW_RISK_PATTERNS.items() if re.search(pattern, text)]

    if high_risk_hits:
        return RepairGuardrailResult(
            should_answer=False,
            confidence=0.91,
            safety_label="refer_to_professional",
            response=(
                "This may involve electrical, gas, structural, or hazardous-material risk. "
                "I should not give step-by-step repair instructions. Please contact a licensed professional."
            ),
            matched_topics=high_risk_hits,
        )
    if low_risk_hits:
        return RepairGuardrailResult(
            should_answer=True,
            confidence=0.78,
            safety_label="answer_with_basic_precautions",
            response="This looks appropriate for general home-maintenance guidance with basic safety precautions.",
            matched_topics=low_risk_hits,
        )
    return RepairGuardrailResult(
        should_answer=False,
        confidence=0.54,
        safety_label="insufficient_context",
        response="I need more detail before answering confidently. Ask for the material, location, symptoms, and risk level first.",
        matched_topics=[],
    )
