# Provenance Guard — Planning Document

## Architecture

### Architecture Narrative

Provenance Guard is a safety layer for creative platforms. A submission enters through either `POST /classify` or the sample-compatible `POST /submit`. The API validates the request, runs a Groq semantic signal when `GROQ_API_KEY` is available plus six independent local detection signals, combines them into an AI-likelihood score, computes confidence separately from likelihood, and maps the result to one of three outcomes: likely AI-generated, likely human-written, or uncertain.

The system treats uncertainty as a first-class result. Short submissions and mixed signals are routed to human review instead of being forced into a binary label. Every classification decision is written to an append-only JSONL audit log with a content hash, creator ID, signal summary, confidence, and transparency label.

Appeals enter through either `POST /appeals` or the sample-compatible `POST /appeal`. Appeals are stored separately from the original decision and also logged as audit events. A reviewer can inspect `GET /review-queue`, `GET /audit`, `GET /appeals`, or `GET /log`.

The browser dashboard at `/` makes the backend usable without Postman or curl. It includes content classification, appeal submission, audit inspection, and the home repair guardrail lab.

Stretch features add three more flows: `POST /certificates` issues verified-human credentials, `GET /analytics` summarizes detection and appeal patterns, and `POST /metadata/analyze` supports image metadata as a second content type.

### Submission Flow

```text
POST /classify or POST /submit
       |
       v
Validate content, creator, and size limits
       |
       v
Groq semantic signal + six local signals
       |
       v
AI-likelihood scorer
       |
       v
Confidence scorer
       |
       v
Transparency label generator
       |
       v
Append-only audit log
       |
       v
JSON response and dashboard rendering
```

### Appeal Flow

```text
POST /appeals or POST /appeal
       |
       v
Validate decision_id or content_id plus creator reasoning
       |
       v
Find the original classification decision when content_id is provided
       |
       v
Store appeal record with status under_review
       |
       v
Append appeal_received event to the audit log
       |
       v
Reviewer inspects /review-queue, /appeals, /audit, or /log
```

## Detection Signals

### 0. Groq Semantic AI Probability

Uses `GROQ_API_KEY` and `GROQ_MODEL` from the runtime environment. The default model is `llama-3.3-70b-versatile`. The model returns a JSON `ai_probability` from 0.0 to 1.0 with one-sentence reasoning.

Blind spot: polished human writing can look AI-like, and the signal requires an external API key. If the key is missing or the API fails, this signal receives weight 0 and the local signals continue.

### 1. Lexical Diversity

Measures whether the text repeats vocabulary unusually often. Lower variety can indicate generated or heavily templated prose, but formal human writing can also repeat domain vocabulary.

### 2. Sentence Uniformity

Measures whether sentence lengths are unusually even. Generated prose often has a steady rhythm, while human writing is more irregular.

### 3. AI Phrase Patterns

Looks for common AI-style phrasing such as "it is important to note", "furthermore", "moreover", and "in conclusion." This signal is intentionally explainable but not trusted alone.

### 4. Human Drafting Markers

Looks for personal or process-oriented markers such as "honestly", "I remember", "my draft", and "not sure." These reduce AI likelihood because they suggest lived context or visible drafting uncertainty.

### 5. Punctuation Shape

Measures whether punctuation is polished and low-variance. It is a weak signal because careful human writing can look polished.

### 6. Template Structure

Looks for highly organized transitions and paragraph structure. This catches generated or templated submissions but can also flag essays and professional writing, so it contributes only part of the final score.

## Confidence and Uncertainty

AI likelihood and confidence are not the same thing.

- `ai_likelihood` estimates how AI-like the content appears.
- `confidence` estimates whether the system has enough evidence to trust that estimate.

That separation prevents short texts from receiving falsely confident labels. A two-word caption may have low AI likelihood, but it should still be uncertain because there is not enough evidence.

The raw signal outputs are normalized to scores between 0.0 and 1.0. The weighted signal score becomes `ai_likelihood`. Confidence is then computed from distance away from the uncertain middle, evidence volume, and signal agreement. A score near 0.5 means "do not make an automated authorship claim"; it does not mean "barely AI."

## Label Mapping

| Condition | Classification | User-facing label |
| --- | --- | --- |
| High AI likelihood and enough confidence | `likely_ai_generated` | Likely AI-generated |
| Low AI likelihood and enough confidence | `likely_human_written` | Likely human-written |
| Mixed, short, or low-confidence evidence | `uncertain` | Needs human review |

Exact transparency labels:

**High-confidence AI**

> "Our system found strong indicators that this content may have been generated by an AI writing tool. This is not a final accusation and no creator penalty should be applied without review. If you wrote this yourself, submit an appeal with context about your drafting process."

**Uncertain**

> "Our system was not able to confidently determine whether this content was written by a person or an AI tool. No automated action should be taken. A human reviewer should consider the context before applying a label."

**High-confidence human**

> "Our system found stronger indicators that this content was written by a person. No AI-generated content label is recommended."

## Appeals Workflow

Creators can appeal any decision by submitting a `decision_id` or by using the sample-compatible `content_id` flow.

The system stores:

- original decision ID
- content ID
- creator ID
- appeal reason
- optional evidence
- timestamp
- review status

No automatic reclassification happens during appeal. A human reviewer should compare the original decision, the signal-level rationale, and the creator's context.

## Production Guardrails

- Sliding-window rate limiting by API key or IP address
- Append-only audit events
- Content hashing instead of storing raw submitted text in the audit log
- Explicit uncertainty warnings for short text
- Reviewer queue for uncertain decisions and appeals
- Home repair safety endpoint that refuses high-risk electrical, gas, structural, and hazardous-material questions
- Verified-human certificates that attach creator provenance context to future decisions
- Analytics summary for decision count, appeal rate, uncertain rate, average confidence, creator certificates, and content types
- Image metadata analysis for a second content type

## Differences From The Reference Sample

The reference sample uses a Groq LLM signal and one stylometric signal. This version uses Groq when `GROQ_API_KEY` is present and also remains local-first enough to run without an API key during a live demo. It expands the safety layer beyond attribution by adding:

- Groq plus six explainable local signals instead of two total signals
- a dashboard UI at `/`
- home repair refusal guardrail
- review queue endpoint
- short-text confidence cap
- API compatibility with `/submit`, `/appeal`, and `/log`

## Known Limitations

Formal human writing remains the hardest case. Academic essays, legal writing, professional blog posts, and careful writing from non-native English speakers can look structured and polished in ways that overlap with AI text. The system mitigates this with an uncertain band, short-text warnings, signal-level explanations, and an appeal workflow.

Specific edge cases:

1. A poem or caption with only a few words will not provide enough evidence for sentence rhythm or vocabulary diversity. The system caps confidence and routes it to `uncertain`.
2. A formal human essay can look AI-like because it may have even sentence structure, clean punctuation, and few personal drafting markers.
3. A heavily edited AI draft may look human because human edits add irregularity and personal wording.

This is not a real AI detector. It is a production-engineering exercise showing how to build the accountability layer around an uncertain classifier.

## AI Tool Plan

### M3: Submission Endpoint And First Signal

Spec sections to provide: Architecture, Detection Signals, and Confidence and Uncertainty.

Request: generate a Flask skeleton with `POST /submit`, validation, content IDs, a first local detection signal, and a structured audit-log helper.

Verification: call the signal directly with clearly AI-like, clearly human-like, and short text inputs before wiring it into the endpoint. Confirm `/submit` returns `content_id`, attribution, confidence, and label fields.

### M4: Additional Signals And Scoring

Spec sections to provide: Detection Signals, Confidence and Uncertainty, Label Mapping.

Request: implement the remaining local signals and the scoring logic that separates `ai_likelihood` from `confidence`.

Verification: test at least four samples: AI-like template prose, casual human writing, formal human writing, and a short caption. Print individual signals to see which one drives each result.

### M5: Production Layer

Spec sections to provide: exact transparency labels, Appeals Workflow, Production Guardrails, and Architecture.

Request: implement appeals, rate limiting, audit log endpoints, reviewer queue, and dashboard controls.

Verification: submit an appeal and confirm `/log` records it; run 12 rapid `/submit` calls and confirm the final two return `429`; use the dashboard buttons end to end.

## Stretch Feature Plan

I completed all listed stretch categories:

1. **Ensemble detection:** Groq semantic classification plus six local text signals instead of the required two.
2. **Provenance certificate:** `POST /certificates` stores a verified-human credential after a reviewer checks evidence such as draft history or profile history. Future decisions include the certificate context.
3. **Analytics dashboard:** `GET /analytics` and the UI show total decisions, appeal rate, uncertain rate, average confidence, verified creators, and content-type mix.
4. **Multi-modal support:** `POST /metadata/analyze` classifies image metadata using generator-tool, prompt-artifact, camera metadata, source-file, and edit-history signals. It does not claim to inspect image pixels.

I also added the home repair guardrail as an extra Week 4 safety demonstration.
