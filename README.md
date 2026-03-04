# Clara AI — Demo & Onboarding Automation Pipeline

An automated pipeline that takes field service business call transcripts and generates AI phone agent configurations for [Retell](https://www.retellai.com/).

---

## What This Does

This project automates two workflows:

**Pipeline A — Demo Call → Preliminary Agent (v1)**
Reads a demo call transcript, extracts structured business information, and generates a preliminary Retell AI agent configuration.

**Pipeline B — Onboarding Call → Updated Agent (v2)**
Reads an onboarding call transcript, compares it against the existing v1 configuration, applies updates, regenerates the agent spec, and produces a changelog of every change made.

---

## Architecture & Data Flow

```
transcripts/
├── demo/                        (input for Pipeline A)
│   └── account_XXX_demo.txt
└── onboarding/                  (input for Pipeline B)
    └── account_XXX_onboarding.txt
          │
          ▼
    scripts/pipeline_a.py
          │
          ├── Groq LLM (extraction prompt)
          │       └── Account Memo JSON (v1)
          │
          └── Groq LLM (agent spec prompt)
                  └── Retell Agent Spec JSON (v1)
                              │
                              ▼
                    scripts/pipeline_b.py
                              │
                    ├── Groq LLM (update extraction)
                    │       └── Account Memo JSON (v2)
                    │
                    ├── Groq LLM (changelog generation)
                    │       └── changelog.json
                    │
                    └── Groq LLM (agent spec v2)
                            └── Retell Agent Spec JSON (v2)

outputs/
└── accounts/
    └── account_XXX/
        ├── v1/
        │   ├── account_memo_v1.json
        │   └── agent_spec_v1.json
        └── v2/
            ├── account_memo_v2.json
            ├── agent_spec_v2.json
            └── changelog.json
```

---

## Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| LLM (AI brain) | Groq API — llama-3.3-70b-versatile | Free |
| Orchestration | Python scripts | Free |
| Storage | JSON files in GitHub repo | Free |
| Transcripts | Plain text `.txt` files | Free |

---

## Prerequisites

- Python 3.10 or higher
- A free Groq API key from [console.groq.com](https://console.groq.com)
- Git (to clone and push the repo)

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 2. Install dependencies

```bash
pip install groq
```

### 3. Add your Groq API key

Open `scripts/pipeline_a.py` and `scripts/pipeline_b.py`.
In both files, find this line near the top and replace with your key:

```python
GROQ_API_KEY = "PASTE_YOUR_GROQ_API_KEY_HERE"
```

Get your free key at: [console.groq.com](https://console.groq.com)

---

## How to Plug In the Dataset

Place transcript files in the correct folders:

```
transcripts/
├── demo/
│   ├── account_001_demo.txt
│   ├── account_002_demo.txt
│   └── ...
└── onboarding/
    ├── account_001_onboarding.txt
    ├── account_002_onboarding.txt
    └── ...
```

**Naming rules:**
- Demo transcripts must end in `_demo.txt`
- Onboarding transcripts must end in `_onboarding.txt`
- The prefix (e.g. `account_001`) becomes the `account_id` in all outputs

---

## Running the Pipelines

> ⚠️ Always run from the **root of the repo**, not from inside `/scripts`

### Run Pipeline A (Demo → v1)

```bash
python scripts/pipeline_a.py
```

This will process all `_demo.txt` files and generate v1 outputs for each account.

### Run Pipeline B (Onboarding → v2)

```bash
python scripts/pipeline_b.py
```

This will process all `_onboarding.txt` files and generate v2 outputs + changelogs.

> ⚠️ Pipeline A must be run before Pipeline B — Pipeline B reads the v1 memo files produced by Pipeline A.

### Run Both Pipelines (Full Dataset)

```bash
python scripts/pipeline_a.py && python scripts/pipeline_b.py
```

---

## Output Files Explained

For each account, the following files are generated:

| File | Version | Description |
|---|---|---|
| `account_memo_v1.json` | v1 | Structured business info extracted from demo call |
| `agent_spec_v1.json` | v1 | Full Retell agent configuration after demo |
| `account_memo_v2.json` | v2 | Updated business info after onboarding |
| `agent_spec_v2.json` | v2 | Updated Retell agent configuration after onboarding |
| `changelog.json` | v2 | Every change between v1 and v2, with reasons |

### Sample Account Memo (v1)

```json
{
  "account_id": "account_001",
  "company_name": "Arctic Air HVAC",
  "business_hours": {
    "days": "Monday to Friday",
    "start": "7:00 AM",
    "end": "6:00 PM",
    "timezone": "Mountain Time"
  },
  "emergency_definition": ["total system failure in extreme weather", "refrigerant leak", "carbon monoxide alarm"],
  "emergency_routing_rules": [
    { "priority": 1, "name": "Dave Kowalski", "phone": "720-555-0192", "wait_seconds": 120 },
    { "priority": 2, "name": "Linda Torres", "phone": "720-555-0340", "wait_seconds": 120 }
  ],
  ...
}
```

### Sample Changelog Entry

```json
{
  "field": "emergency_routing_rules[0]",
  "old_value": "Dave Kowalski — 720-555-0192",
  "new_value": "Jason Park — 720-555-0887",
  "reason": "Dave Kowalski left the company and was replaced by Jason Park as primary on-call technician"
}
```

---

## Retell Agent Setup (Manual Import)

Since Retell's programmatic agent creation requires a paid plan, follow these steps to import the generated spec manually:

1. Go to [app.retellai.com](https://app.retellai.com) and log in
2. Click **"Create Agent"**
3. Set the agent name from `agent_spec_vX.json` → `agent_name`
4. Paste the contents of `system_prompt` into the system prompt field
5. Set voice style to: professional, warm, calm
6. Configure call transfer numbers from `call_transfer_protocol`
7. Save the agent

The generated JSON is structured to match Retell's configuration fields exactly, making manual import straightforward.

---

## Idempotency

Both pipelines are safe to run multiple times:
- Pipeline A overwrites existing v1 files if re-run (no duplicate chaos)
- Pipeline B overwrites existing v2 files if re-run
- Running the same pipeline twice on the same data produces identical outputs

---

## Known Limitations

- **No Retell API integration** — Retell requires a paid plan for programmatic agent creation. The agent spec JSON is production-ready for manual import or future API integration.
- **No task tracker integration** — A task item per account can be manually created in Asana/Trello using the account memo data.
- **Rate limiting** — Groq free tier has per-minute limits. The scripts include automatic delays between accounts to handle this. If you hit rate limits, wait 60 seconds and re-run.
- **Audio transcription** — This pipeline accepts text transcripts only. For audio files, run [Whisper](https://github.com/openai/whisper) locally first to generate transcripts, then feed them in.

---

## What I Would Improve With Production Access

- **Retell API integration** — Auto-create and update agents via API, eliminating the manual import step
- **Webhook trigger** — Instead of running scripts manually, trigger Pipeline A automatically when a new demo call recording lands in a cloud storage bucket
- **Asana/Slack integration** — Auto-create a task in Asana and post a Slack notification when each agent is created or updated
- **Diff viewer UI** — A simple web dashboard showing v1 vs v2 side-by-side with highlighted changes
- **Supabase storage** — Replace JSON files with a proper database for querying, filtering, and audit history
- **Audio pipeline** — Integrate Whisper transcription as an automatic first step so the pipeline accepts raw audio directly

---

## Repository Structure

```
/
├── transcripts/
│   ├── demo/                    ← input demo call transcripts
│   └── onboarding/              ← input onboarding call transcripts
├── scripts/
│   ├── pipeline_a.py            ← Demo → v1 pipeline
│   └── pipeline_b.py            ← Onboarding → v2 pipeline
├── outputs/
│   └── accounts/
│       └── account_XXX/
│           ├── v1/
│           └── v2/
└── README.md
```

---

## Dataset Used

This submission uses 5 mock accounts representing realistic field service businesses:

| Account ID | Company | Industry |
|---|---|---|
| account_001 | Arctic Air HVAC | Heating & Cooling |
| account_002 | Blue River Plumbing | Plumbing |
| account_003 | Comfort Zone Heating & Cooling | Heating & Cooling |
| account_004 | Desert Storm AC | AC & Refrigeration |
| account_005 | Elite Fire Protection | Fire Protection |

---

## Author

Built as part of the Clara AI Intern Assignment.
