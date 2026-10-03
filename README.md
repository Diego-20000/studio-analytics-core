# studio-analytics-core

A small, fully-tested public reference implementation of one part of the architecture behind **Studio Analytics**: parsing official Instagram exports locally and incrementally.

This is a **companion reference to the Android app**, not a second product or the source repository. The main application is [Diego-20000/studio-analytics-app](https://github.com/Diego-20000/studio-analytics-app). The supporting remote-config/feedback service lives in [Diego-20000/studio-analytics-api](https://github.com/Diego-20000/studio-analytics-api), and APK releases are published in [Diego-20000/studio-analytics-releases](https://github.com/Diego-20000/studio-analytics-releases).

The implementation here is intentionally smaller and independent of the Android project: it isolates the parsing and validation decisions that are useful to inspect, test and reuse as an engineering reference.

## The problem

Instagram's official "Download Your Information" export is a folder of
JSON files. Most are small (`followers_1.json`, `following.json`), but
engagement history — `liked_posts.json`, `post_comments.json` — grows
with account age and easily reaches **tens of megabytes** for an
active, multi-year account.

The naive approach:

```python
import json
data = json.load(open("liked_posts.json"))  # loads the entire file into RAM
```

works fine on a laptop and then fails, silently or with an OOM kill, the
moment it runs on a memory-constrained mobile device — exactly where
this kind of tool needs to run, since the whole point is to never send
the data anywhere else to be processed on a server instead.

## The architecture

```
                    ┌────────────────────┐
   raw export       │      models.py     │   strict, validated
   JSON files  ────▶ │  (Pydantic schema) │──▶ data contracts
                    └────────────────────┘
                              ▲
                              │ validates records as they arrive
                              │
                    ┌────────────────────┐
                    │     parser.py      │   ijson streaming engine:
                    │  (streaming engine)│   O(unique usernames) memory,
                    └────────────────────┘   not O(file size)
                              ▲
                              │ raises typed errors, never bare
                              │ exceptions
                    ┌────────────────────┐
                    │   exceptions.py    │
                    │  (error taxonomy)  │
                    └────────────────────┘
```

Three modules, three responsibilities:

- **`src/models.py`** — Pydantic models that define exactly what a valid
  record looks like. Malformed input fails fast, at the boundary, with a
  specific error — not three call frames deep with a `KeyError`.
- **`src/parser.py`** — the streaming engine. Every function reads its
  input with [`ijson`](https://github.com/ICRAR/ijson) instead of
  `json.load`, so memory usage scales with the *aggregate being built*
  (a set of usernames, a running counter) rather than with the size of
  the file on disk. `analyze_relationships()` computes who doesn't
  follow back and the account's overall reciprocity percentage by
  streaming both files and taking a set difference — no server call,
  no intermediate storage, no network dependency of any kind.
- **`src/exceptions.py`** — a small typed error hierarchy
  (`InvalidExportFormatError`, `CorruptedJSONError`,
  `UnsupportedExportVersionError`) rooted at `StudioAnalyticsError`, so
  callers can catch precisely what they know how to handle instead of
  swallowing everything with a bare `except Exception`.

## Privacy by design, not by policy

The product's non-negotiable rule is that **no Instagram data —
followers, likes, activity, audience — ever leaves the user's device.**
That constraint is what shaped every decision here, and it's directly
visible in the code, not just asserted in a privacy policy:

- Every public function in `parser.py` takes a local file path and
  returns an in-memory result. There is no HTTP client, no serialization
  format for a network payload, no analytics SDK anywhere in this
  package.
- The data contracts in `models.py` model *only* what's needed to
  compute the requested aggregate (a username, a timestamp) — there's
  no code path that would even give you a place to bolt on
  "send this to a server for processing" later.
- Errors carry file paths and reasons, never record contents, so even
  crash logs can't leak user data.

## Relationship to the main project

The Android app contains the product UI, ZIP import flow and the broader analysis features. This repository keeps only a focused Python reference of the parsing architecture, so the two should not be treated as interchangeable codebases.

## Running it

```bash
pip install -r requirements.txt
pip install -e .
pytest
```

```python
from pathlib import Path
from src.parser import analyze_relationships

result = analyze_relationships(
    Path("followers_1.json"),
    Path("following.json"),
)
print(f"{len(result.not_following_back)} accounts don't follow you back")
print(f"Reciprocity: {result.reciprocity_percentage}%")
```

## What this repo deliberately leaves out

This is an architecture sample, not a product. It intentionally omits
the Android UI layer, the on-device notification scheduling, the
anti-tamper/signature-verification layer, remote config, and the
full richer activity-analysis feature set of the commercial app — all
of that is proprietary. What's here is the part that best demonstrates
the engineering: how to parse an untrusted, potentially huge, real-world
JSON export safely, on a memory budget, with typed error handling from
end to end.

## License

MIT — see [LICENSE](LICENSE).
