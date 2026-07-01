# Provenance Guard

Provenance Guard is a Flask backend and demo dashboard for AI attribution safety. A creative platform can submit text, receive an attribution result with confidence, show a plain-language transparency label, log every decision, and let creators appeal contested labels.

The app runs locally at `http://127.0.0.1:5010/` and includes a browser dashboard plus API endpoints.

## Run

```bash
cd provenance_guard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Architecture Overview

A submission enters through `POST /submit` or `POST /classify`. The API validates the text, runs six independent detection signals, combines them into an AI-likelihood score, computes confidence separately, maps the result to a transparency label, writes a structured audit event, and returns JSON to the caller.

An appeal enters through `POST /appeal` or `POST /appeals`. The API captures creator reasoning, links the appeal to the original decision where possible, marks it `under_review`, writes an audit event, and exposes the result through `/log`, `/audit`, `/appeals`, and `/review-queue`.

```text
SUBMISSION FLOW

POST /submit or POST /classify
       |
       v
request validation
       |
       v
six detection signals
       |
       v
AI-likelihood score + confidence score
       |
       v
plain-language transparency label
       |
       v
structured audit log
       |
       v
JSON response + dashboard update

APPEAL FLOW

POST /appeal or POST /appeals
       |
       v
creator reasoning captured
       |
       v
status set to under_review
       |
       v
appeal stored and audit event written
       |
       v
reviewer sees /review-queue, /appeals, /audit, or /log
```

## API Endpoints

- `GET /` browser dashboard
- `POST /submit` assignment-compatible content submission endpoint
- `POST /classify` richer dashboard/API classification endpoint
- `POST /appeal` assignment-compatible appeal endpoint
- `POST /appeals` richer appeal endpoint
- `GET /log` assignment-compatible audit log endpoint
- `GET /audit` raw audit events
- `GET /appeals` stored appeals
- `GET /review-queue` low-confidence decisions and appeals
- `GET /analytics` detection, appeal, confidence, and content-type metrics
- `POST /certificates`, `GET /certificates` verified-human credential workflow
- `POST /metadata/analyze` image metadata support
- `POST /home-repair/guardrail` Week 4 lab-style safety classifier
- `GET /health` service health check

## Detection Signals

This version uses six local, explainable signals. That is also the ensemble detection stretch feature.

| Signal | What it measures | Why it helps | What it misses |
| --- | --- | --- | --- |
| Lexical diversity | Unique-word ratio | Repetitive vocabulary can indicate generated or templated prose | Formal human writing can repeat domain terms |
| Sentence uniformity | Sentence length variance | AI prose often has a steady rhythm | Essays and professional writing can also be even |
| AI phrase patterns | Phrases like "it is important to note" and "in conclusion" | Common model outputs often overuse these transitions | Humans can intentionally write this way |
| Human drafting markers | Phrases like "honestly", "I remember", "my draft" | Personal context and visible uncertainty reduce AI likelihood | Some human writing is polished and impersonal |
| Punctuation shape | Polished, low-variance punctuation | Generated prose can have formulaic punctuation | Careful writers also use clean punctuation |
| Template structure | Organized transitions and paragraph structure | Templated content often follows predictable structure | Academic or business writing can look structured |

## Multi-Modal Support

The text classifier is the primary Project 4 path, but the app also supports a second content type: `image_metadata`.

`POST /metadata/analyze` accepts image-adjacent metadata such as:

```json
{
  "creator_id": "creator_demo",
  "content_id": "image_demo",
  "metadata": {
    "tool": "Midjourney",
    "prompt": "cinematic portrait, studio lighting",
    "exif_present": false,
    "edit_history_present": false
  }
}
```

It does not claim to inspect image pixels. Instead, it analyzes metadata signals: generator tool mentions, prompt artifacts, missing camera metadata, source-file evidence, and edit-history evidence. This keeps the safety claim honest while still extending the pipeline beyond plain text.

## Confidence Scoring

The system separates `ai_likelihood` from `confidence`.

- `ai_likelihood` estimates how AI-like the content appears.
- `confidence` estimates whether the system has enough evidence to trust that estimate.

This matters because a short caption can have low AI likelihood but still be unsafe to label confidently. Short or mixed-signal inputs are pushed toward `uncertain` rather than forced into a binary decision.

Label mapping:

| Result | Meaning |
| --- | --- |
| `likely_ai_generated` | AI likelihood is high and confidence is high enough to show an AI label |
| `likely_human_written` | AI likelihood is low and confidence is high enough to avoid an AI label |
| `uncertain` | Evidence is mixed, short, or too low-confidence for an automated verdict |

Example validation results:

| Example | Classification | Confidence | AI likelihood |
| --- | --- | ---: | ---: |
| Template-style AI prose with repeated transitions | `likely_ai_generated` | `0.589` | `0.766` |
| Personal human draft with lived-context markers | `likely_human_written` | `0.710` | `0.052` |
| Two-word caption | `uncertain` | `0.450` | `0.033` |
| Course-provided polished AI sample | `uncertain` | `0.432` | `0.329` |

The last case is intentional: this detector favors caution when evidence is not strong enough. False positives against human creators are treated as worse than false negatives.

## Transparency Labels

The exact label text returned by the API:

| Variant | Exact label text |
| --- | --- |
| High-confidence AI | "Our system found strong indicators that this content may have been generated by an AI writing tool. This is not a final accusation and no creator penalty should be applied without review. If you wrote this yourself, submit an appeal with context about your drafting process." |
| Uncertain | "Our system was not able to confidently determine whether this content was written by a person or an AI tool. No automated action should be taken. A human reviewer should consider the context before applying a label." |
| High-confidence human | "Our system found stronger indicators that this content was written by a person. No AI-generated content label is recommended." |

## Appeals Workflow

Creators can appeal any classification.

Assignment-compatible request:

```bash
curl -s http://127.0.0.1:5010/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "content_abc123",
    "creator_reasoning": "I wrote this myself and can provide draft history."
  }'
```

The system:

- captures the creator's reasoning
- links the appeal to the original `content_id` and `decision_id` when available
- stores the appeal with status `under_review`
- writes an `appeal_received` event to the audit log
- exposes the item in `/review-queue`

## Provenance Certificates

`POST /certificates` implements the verified-human credential stretch feature. A reviewer can issue a certificate after checking evidence such as draft history, profile history, source files, or a creator interview.

Example request:

```bash
curl -s http://127.0.0.1:5010/certificates \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "creator_demo",
    "verification_method": "draft history + profile review",
    "evidence_summary": "Creator provided timestamped drafts and portfolio history."
  }'
```

Once issued, future classification responses for that creator include a `provenance_certificate` object and the UI displays `Verified human creator`. The certificate does not override the classifier; it gives reviewers additional accountability context.

## Rate Limiting

`POST /submit` and `POST /classify` are rate-limited to:

```text
10 requests per minute per IP address or X-API-Key
```

Reasoning: a real creator might submit several drafts in a short session, but 10 submissions per minute is already generous for normal use. A scripted flood would hit the limit quickly. Audit viewing and appeals are not rate-limited by this limiter so reviewers and creators can inspect decisions without being blocked.

Rate-limit test evidence from 12 rapid `/submit` requests:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

## Audit Log

Audit events are structured JSONL entries written to `data/audit.log`. Appeals are also stored in `data/appeals.jsonl`. Runtime log files are ignored by git, but `/log`, `/audit`, and the dashboard's Refresh Audit button expose the same evidence.

Representative entries:

```json
{
  "event_type": "classification_decision",
  "content_id": "content_d784265ab7fa",
  "creator_id": "ratelimit-test",
  "attribution": "uncertain",
  "confidence": 0.45,
  "ai_likelihood": 0.056,
  "signals_used": ["lexical_diversity", "sentence_uniformity", "ai_phrase_patterns", "human_marker_absence", "punctuation_shape", "template_structure"],
  "signal_scores": {
    "lexical_diversity": 0.0,
    "sentence_uniformity": 0.5,
    "ai_phrase_patterns": 0.0,
    "human_marker_absence": 0.5,
    "punctuation_shape": 0.2,
    "template_structure": 0.0
  },
  "status": "classified"
}
```

```json
{
  "event_type": "classification_decision",
  "content_id": "post_demo",
  "creator_id": "creator_demo",
  "attribution": "uncertain",
  "confidence": 0.349,
  "ai_likelihood": 0.605,
  "transparency_label": "Needs human review",
  "status": "classified"
}
```

```json
{
  "event_type": "appeal_received",
  "appeal_id": "appeal_b115e2631724",
  "decision_id": "decision_335cf311d603",
  "creator_id": "creator_demo",
  "appeal_reasoning": "This was my original draft and I want a human reviewer to check the edit history.",
  "status": "received"
}
```

## Stretch Features

- Ensemble detection: six documented text signals.
- Provenance certificate: `POST /certificates` issues a verified-human credential and displays it on future decisions.
- Analytics dashboard: `GET /analytics` and the UI show decision count, appeal rate, uncertain rate, average confidence, verified creators, and content types.
- Multi-modal support: `POST /metadata/analyze` handles image metadata as a second content type.
- Additional safety classifier: `/home-repair/guardrail` refuses high-risk electrical, gas, structural, and hazardous-material repair questions.

## Known Limitations

Formal human writing is the largest false-positive risk. Academic essays, legal writing, professional posts, and careful non-native English writing can be polished, structured, and low-variance, which overlaps with AI-like signals.

Very short content is also difficult. A caption, title, or short poem does not provide enough text for reliable sentence rhythm or vocabulary analysis. The implementation caps confidence for very short inputs and routes them to `uncertain`.

This is not a real-world AI detector. It is a production safety-layer exercise showing how to communicate uncertainty, log decisions, rate-limit abuse, and support appeals.

## Spec Reflection

The spec helped most by forcing the transparency labels and uncertainty behavior to be designed before implementation. That made the code easier to write because classification, confidence, and user-facing messaging had clear contracts.

The implementation diverged from the recommended Groq-plus-stylometrics pairing. I used six deterministic local signals instead, so the project can run in a live demo without API keys or network access. To keep the spirit of the spec, each signal captures a distinct property and the README documents each signal's blind spots.

## AI Usage

1. I used AI assistance to compare this project against a public Provenance Guard sample repo. The useful output was a gap list: add `/submit`, `/appeal`, `/log`, a planning document, rate-limit evidence, and exact label variants. I revised the implementation to keep my version deterministic and dashboard-focused instead of copying the sample's Groq implementation.

2. I used AI assistance to refine the dashboard UX after noticing that Refresh Audit technically worked but looked inactive. The revision added an audit status badge and an Audit Snapshot panel so users can see recent events without reading raw JSON.

## Testing

```bash
python3 -m unittest discover -s tests
python3 -m py_compile app.py detector.py audit.py rate_limit.py home_repair.py tests/test_detector.py
```

Both pass locally.

## Walkthrough Video Notes

For the short portfolio walkthrough, show:

1. Open `http://127.0.0.1:5010/`.
2. Click Classify and explain the label, confidence, AI likelihood, and signals.
3. Submit an appeal and show it appears in the audit/review flow.
4. Click Refresh Audit and explain structured logging.
5. Use the home repair guardrail with an electrical panel question and explain refusal behavior.
