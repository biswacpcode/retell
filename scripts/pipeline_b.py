"""
PIPELINE B: Onboarding Call Transcript -> Updated Account Memo (v2) + Agent Spec (v2) + Changelog
==================================================================================================
What this script does:
  1. Reads every onboarding transcript from /transcripts/onboarding/
  2. Reads the existing v1 account memo for that account
  3. Sends BOTH to Groq and asks: "what changed?"
  4. Groq produces an updated v2 Account Memo JSON
  5. Groq generates a new v2 Retell Agent Spec JSON
  6. Groq produces a changelog explaining every change and why
  7. Saves all three files to /outputs/accounts/<account_id>/v2/

HOW TO RUN:
  Step 1: Make sure pipeline_a.py has already run (v1 files must exist)
  Step 2: Paste your Groq API key below
  Step 3: Run from your repo root:  python scripts/pipeline_b.py
"""

import os
import json
import re
import time
from groq import Groq

# ============================================================
# CONFIGURATION — PASTE YOUR GROQ API KEY HERE
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ============================================================
# FOLDER PATHS
# ============================================================
ONBOARDING_TRANSCRIPTS_FOLDER = "transcripts/onboarding"
OUTPUTS_FOLDER = "outputs/accounts"

# ============================================================
# STEP 1: CONFIGURE GROQ CLIENT
# ============================================================
client = Groq(api_key=GROQ_API_KEY)

def call_llm(prompt):
    """Send a prompt to Groq and return the response text."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content


# ============================================================
# STEP 2: PROMPT TO EXTRACT UPDATES FROM ONBOARDING TRANSCRIPT
# ============================================================
def build_update_extraction_prompt(onboarding_transcript, v1_memo):
    return f"""
You are a data extraction assistant for Clara, a company that builds AI phone agents for field service businesses.

You have two inputs:
1. An existing v1 account memo (JSON) created after a demo call
2. A new onboarding call transcript where the client reviews and updates their configuration

Your job:
- Read the onboarding transcript carefully
- Identify ONLY what has changed or been added compared to the v1 memo
- Return a COMPLETE updated v2 account memo JSON with ALL fields (not just the changes)
- For unchanged fields, copy them exactly from v1
- For changed fields, use the new values from the onboarding transcript

Return ONLY a valid JSON object — no explanation, no markdown, no code fences. Just raw JSON.

Use this exact structure:
{{
  "account_id": "same as v1",
  "company_name": "same as v1 unless changed",
  "business_hours": {{
    "days": "updated if changed",
    "start": "updated if changed",
    "end": "updated if changed",
    "timezone": "updated if changed"
  }},
  "office_address": "same as v1 unless changed",
  "services_supported": ["same as v1 unless changed"],
  "emergency_definition": ["updated if changed"],
  "emergency_routing_rules": [
    {{
      "priority": 1,
      "name": "updated if changed",
      "phone": "updated if changed",
      "wait_seconds": 120
    }}
  ],
  "emergency_fallback": "updated if changed",
  "non_emergency_routing_rules": "updated if changed",
  "call_transfer_rules": {{
    "timeout_seconds": 120,
    "retries": "updated if changed",
    "if_transfer_fails": "updated if changed"
  }},
  "integration_constraints": ["updated list if changed"],
  "after_hours_flow_summary": "updated if changed",
  "office_hours_flow_summary": "updated if changed",
  "questions_or_unknowns": [],
  "notes": "updated if changed"
}}

Rules:
- Do NOT invent anything not in the transcript or v1 memo
- Do NOT drop any fields — always include every field
- If something was not mentioned in onboarding, keep the v1 value

V1 ACCOUNT MEMO:
{json.dumps(v1_memo, indent=2)}

ONBOARDING TRANSCRIPT:
{onboarding_transcript}
"""


# ============================================================
# STEP 3: PROMPT TO GENERATE CHANGELOG
# ============================================================
def build_changelog_prompt(v1_memo, v2_memo, onboarding_transcript):
    return f"""
You are a documentation assistant for Clara, a company that builds AI phone agents.

Compare the v1 and v2 account memos below and produce a clear changelog.

Return ONLY a valid JSON object — no explanation, no markdown, no code fences. Just raw JSON.

Use this exact structure:
{{
  "account_id": "string",
  "company_name": "string",
  "version_from": "v1",
  "version_to": "v2",
  "changes": [
    {{
      "field": "name of the field that changed",
      "old_value": "what it was in v1",
      "new_value": "what it is now in v2",
      "reason": "brief explanation of why it changed, based on the onboarding transcript"
    }}
  ],
  "summary": "one paragraph summary of all changes made during onboarding"
}}

Rules:
- Only list fields that actually changed
- Be specific about what changed (e.g. phone number, hours, contact name)
- Keep reasons concise but clear

V1 MEMO:
{json.dumps(v1_memo, indent=2)}

V2 MEMO:
{json.dumps(v2_memo, indent=2)}

ONBOARDING TRANSCRIPT:
{onboarding_transcript}
"""


# ============================================================
# STEP 4: PROMPT TO REGENERATE AGENT SPEC FOR V2
# ============================================================
def build_agent_spec_prompt(account_memo):
    return f"""
You are an AI phone agent configuration expert for Clara, a company that builds AI voice agents for field service businesses.

Using the following v2 account memo JSON, generate an updated Retell Agent Spec. Return ONLY a valid JSON object — no explanation, no markdown, no code fences. Just raw JSON.

Use this exact structure:
{{
  "agent_name": "Clara for [Company Name]",
  "version": "v2",
  "voice_style": "professional, warm, calm",
  "timezone": "from account memo",
  "business_hours": {{
    "days": "from account memo",
    "start": "from account memo",
    "end": "from account memo"
  }},
  "key_variables": {{
    "company_name": "string",
    "office_address": "string",
    "timezone": "string",
    "emergency_contacts": ["list from account memo"],
    "integration_platform": "name of their software"
  }},
  "system_prompt": "FULL DETAILED PROMPT — see instructions below",
  "call_transfer_protocol": "describe exactly how to transfer calls",
  "transfer_fail_protocol": "describe exactly what to say if transfer fails",
  "tool_invocation_placeholders": [
    "List actions the agent should trigger silently (do NOT mention these to caller). Example: log_call, attempt_transfer, create_message_record"
  ]
}}

SYSTEM PROMPT REQUIREMENTS — the system_prompt field must include ALL of the following:

1. IDENTITY: Agent introduces itself as Clara calling on behalf of [company name]. Never reveals it is an AI unless directly asked.

2. OFFICE HOURS FLOW:
   - Greet caller warmly
   - Ask for their name and callback number early
   - Understand the reason for their call
   - Route or transfer based on the issue
   - If transfer fails: take a message and confirm next steps
   - Offer "Is there anything else I can help you with?" before closing

3. AFTER HOURS FLOW:
   - Greet caller, explain the office is currently closed
   - Ask if this is an emergency
   - If YES emergency: collect name, callback number, and address immediately. Attempt transfer to on-call contact. If transfer fails, assure callback within the timeframe from the account memo.
   - If NO emergency: collect name, number, and description. Confirm next business day callback.
   - Offer "Is there anything else?" before closing.

4. STRICT RULES:
   - Never promise specific arrival times
   - Never mention "function calls", "tools", or internal system actions to the caller
   - Never quote prices
   - Always confirm caller name and callback number before ending call
   - Follow all integration constraints: {account_memo.get("integration_constraints", [])}

5. CALL TRANSFER: Use the emergency contacts from the v2 memo.

6. FALLBACK: Use the emergency fallback from the v2 memo.

V2 ACCOUNT MEMO:
{json.dumps(account_memo, indent=2)}
"""


# ============================================================
# STEP 5: HELPER — CLEAN JSON FROM LLM RESPONSE
# ============================================================
def extract_json(response_text):
    cleaned = re.sub(r"```json|```", "", response_text).strip()
    return json.loads(cleaned)


# ============================================================
# STEP 6: SAVE OUTPUT FILES
# ============================================================
def save_output(account_id, filename, data):
    folder = os.path.join(OUTPUTS_FOLDER, account_id, "v2")
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ Saved: {filepath}")


# ============================================================
# STEP 7: PROCESS ONE ONBOARDING TRANSCRIPT
# ============================================================
def process_onboarding_transcript(filepath):
    filename = os.path.basename(filepath)
    account_id = filename.replace("_onboarding.txt", "")

    print(f"\n{'='*60}")
    print(f"Processing: {filename}  (Account: {account_id})")
    print(f"{'='*60}")

    # --- Load onboarding transcript ---
    with open(filepath, "r") as f:
        onboarding_transcript = f.read()

    # --- Load existing v1 memo ---
    v1_memo_path = os.path.join(OUTPUTS_FOLDER, account_id, "v1", "account_memo_v1.json")
    if not os.path.exists(v1_memo_path):
        print(f"  ❌ ERROR: v1 memo not found at {v1_memo_path}")
        print(f"  Please run pipeline_a.py first!")
        return

    with open(v1_memo_path, "r") as f:
        v1_memo = json.load(f)
    print(f"  📂 Loaded v1 memo for {account_id}")

    # --- STEP A: Generate updated v2 Account Memo ---
    print("  🤖 Sending to Groq to extract updates...")
    update_prompt = build_update_extraction_prompt(onboarding_transcript, v1_memo)
    update_response_text = call_llm(update_prompt)

    try:
        v2_memo = extract_json(update_response_text)
        v2_memo["account_id"] = account_id
        print("  ✅ v2 account memo created successfully")
    except Exception as e:
        print(f"  ❌ ERROR parsing v2 memo JSON: {e}")
        print(f"  Raw response preview: {update_response_text[:500]}")
        return

    save_output(account_id, "account_memo_v2.json", v2_memo)
    time.sleep(2)

    # --- STEP B: Generate Changelog ---
    print("  🤖 Sending to Groq to generate changelog...")
    changelog_prompt = build_changelog_prompt(v1_memo, v2_memo, onboarding_transcript)
    changelog_response_text = call_llm(changelog_prompt)

    try:
        changelog = extract_json(changelog_response_text)
        print("  ✅ Changelog generated successfully")
    except Exception as e:
        print(f"  ❌ ERROR parsing changelog JSON: {e}")
        print(f"  Raw response preview: {changelog_response_text[:500]}")
        return

    save_output(account_id, "changelog.json", changelog)
    time.sleep(2)

    # --- STEP C: Generate v2 Agent Spec ---
    print("  🤖 Sending to Groq to generate v2 agent spec...")
    agent_spec_prompt = build_agent_spec_prompt(v2_memo)
    agent_response_text = call_llm(agent_spec_prompt)

    try:
        v2_agent_spec = extract_json(agent_response_text)
        v2_agent_spec["version"] = "v2"
        v2_agent_spec["account_id"] = account_id
        print("  ✅ v2 agent spec generated successfully")
    except Exception as e:
        print(f"  ❌ ERROR parsing v2 agent spec JSON: {e}")
        print(f"  Raw response preview: {agent_response_text[:500]}")
        return

    save_output(account_id, "agent_spec_v2.json", v2_agent_spec)
    print(f"  🎉 Pipeline B complete for {account_id}!")
    time.sleep(3)


# ============================================================
# STEP 8: RUN PIPELINE B ON ALL ONBOARDING TRANSCRIPTS
# ============================================================
def run_pipeline_b():
    print("\n🚀 PIPELINE B STARTED")
    print(f"Looking for onboarding transcripts in: {ONBOARDING_TRANSCRIPTS_FOLDER}\n")

    if not os.path.exists(ONBOARDING_TRANSCRIPTS_FOLDER):
        print(f"❌ Folder not found: {ONBOARDING_TRANSCRIPTS_FOLDER}")
        print("Make sure you are running this script from the ROOT of your repo.")
        return

    transcript_files = [
        f for f in os.listdir(ONBOARDING_TRANSCRIPTS_FOLDER)
        if f.endswith("_onboarding.txt")
    ]

    if not transcript_files:
        print("❌ No onboarding transcript files found. Make sure files end in _onboarding.txt")
        return

    print(f"Found {len(transcript_files)} onboarding transcript(s): {transcript_files}")

    for filename in sorted(transcript_files):
        filepath = os.path.join(ONBOARDING_TRANSCRIPTS_FOLDER, filename)
        process_onboarding_transcript(filepath)

    print(f"\n{'='*60}")
    print("✅ PIPELINE B COMPLETE")
    print(f"Outputs saved to: {OUTPUTS_FOLDER}/")
    print(f"{'='*60}")
    print("\nFinal output structure:")
    print("  outputs/accounts/")
    print("  └── account_XXX/")
    print("      ├── v1/")
    print("      │   ├── account_memo_v1.json")
    print("      │   └── agent_spec_v1.json")
    print("      └── v2/")
    print("          ├── account_memo_v2.json")
    print("          ├── agent_spec_v2.json")
    print("          └── changelog.json")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    run_pipeline_b()
