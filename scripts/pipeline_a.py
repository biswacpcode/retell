"""
PIPELINE A: Demo Call Transcript -> Account Memo JSON + Retell Agent Spec (v1)
==============================================================================
What this script does:
  1. Reads every demo transcript from /transcripts/demo/
  2. Sends the transcript to Groq (free AI)
  3. Groq extracts structured business info -> Account Memo JSON
  4. Groq generates a Retell Agent Spec JSON (the AI phone agent config)
  5. Saves both files to /outputs/accounts/<account_id>/v1/

HOW TO RUN:
  Step 1: pip install groq
  Step 2: Get your free Groq API key from https://console.groq.com
  Step 3: Paste your API key in the GROQ_API_KEY line below
  Step 4: Run from your repo root:  python scripts/pipeline_a.py
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
# FOLDER PATHS — adjust if your folder structure is different
# ============================================================
DEMO_TRANSCRIPTS_FOLDER = "transcripts/demo"
OUTPUTS_FOLDER = "outputs/accounts"

# ============================================================
# STEP 1: CONFIGURE GROQ CLIENT
# ============================================================
client = Groq(api_key=GROQ_API_KEY)

def call_llm(prompt):
    """Send a prompt to Groq and return the response text."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # Free model on Groq
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2  # Low temperature = more consistent, factual output
    )
    return response.choices[0].message.content


# ============================================================
# STEP 2: PROMPT TO EXTRACT ACCOUNT MEMO JSON
# ============================================================
def build_extraction_prompt(transcript_text):
    return f"""
You are a data extraction assistant for a company called Clara that builds AI phone agents for field service businesses (HVAC, plumbing, fire protection, etc.).

Read the following demo call transcript carefully. Extract the information and return ONLY a valid JSON object — no explanation, no markdown, no code block formatting. Just the raw JSON.

Use this exact structure:
{{
  "account_id": "string — use the account ID from the transcript header",
  "company_name": "string",
  "business_hours": {{
    "days": "string e.g. Monday to Friday",
    "start": "string e.g. 7:00 AM",
    "end": "string e.g. 6:00 PM",
    "timezone": "string e.g. Mountain Time"
  }},
  "office_address": "string or null if not mentioned",
  "services_supported": ["list", "of", "services"],
  "emergency_definition": ["list of what qualifies as an emergency"],
  "emergency_routing_rules": [
    {{
      "priority": 1,
      "name": "contact name",
      "phone": "phone number",
      "wait_seconds": 120
    }}
  ],
  "emergency_fallback": "what to tell caller if all contacts fail",
  "non_emergency_routing_rules": "what to do with non-emergency after-hours calls",
  "call_transfer_rules": {{
    "timeout_seconds": 120,
    "retries": "describe retry logic",
    "if_transfer_fails": "what to say to caller"
  }},
  "integration_constraints": ["list of rules about software like ServiceTitan, Housecall Pro etc."],
  "after_hours_flow_summary": "short summary of after-hours call flow",
  "office_hours_flow_summary": "short summary of office-hours call flow",
  "questions_or_unknowns": ["list any info that was missing or unclear — leave empty list if nothing missing"],
  "notes": "any extra important notes"
}}

Rules:
- Do NOT invent information that is not in the transcript.
- If something is not mentioned, use null or an empty list.
- Be concise but accurate.

TRANSCRIPT:
{transcript_text}
"""


# ============================================================
# STEP 3: PROMPT TO GENERATE RETELL AGENT SPEC
# ============================================================
def build_agent_spec_prompt(account_memo):
    return f"""
You are an AI phone agent configuration expert for Clara, a company that builds AI voice agents for field service businesses.

Using the following account memo JSON, generate a Retell Agent Spec. Return ONLY a valid JSON object — no explanation, no markdown, no code block formatting. Just raw JSON.

Use this exact structure:
{{
  "agent_name": "Clara for [Company Name]",
  "version": "v1",
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

SYSTEM PROMPT REQUIREMENTS — the system_prompt field must include ALL of the following sections written as a single coherent instruction to the AI agent:

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

5. CALL TRANSFER: Describe the exact transfer protocol using the emergency contacts from the memo.

6. FALLBACK: If all transfers fail, use the emergency fallback from the memo.

ACCOUNT MEMO:
{json.dumps(account_memo, indent=2)}
"""


# ============================================================
# STEP 4: HELPER — CLEAN JSON FROM GEMINI RESPONSE
# ============================================================
def extract_json(response_text):
    """
    Gemini sometimes wraps JSON in ```json ... ``` even when told not to.
    This function strips that and returns a clean Python dict.
    """
    # Remove markdown code fences if present
    cleaned = re.sub(r"```json|```", "", response_text).strip()
    return json.loads(cleaned)


# ============================================================
# STEP 5: SAVE OUTPUT FILES
# ============================================================
def save_output(account_id, filename, data):
    folder = os.path.join(OUTPUTS_FOLDER, account_id, "v1")
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ Saved: {filepath}")


# ============================================================
# STEP 6: PROCESS ONE TRANSCRIPT FILE
# ============================================================
def process_demo_transcript(filepath):
    filename = os.path.basename(filepath)
    account_id = filename.replace("_demo.txt", "")
    print(f"\n{'='*60}")
    print(f"Processing: {filename}  (Account: {account_id})")
    print(f"{'='*60}")

    # Read transcript
    with open(filepath, "r") as f:
        transcript_text = f.read()

    # --- EXTRACTION: Get Account Memo JSON ---
    print("  🤖 Sending to Groq for extraction...")
    extraction_prompt = build_extraction_prompt(transcript_text)
    extraction_response_text = call_llm(extraction_prompt)

    try:
        account_memo = extract_json(extraction_response_text)
        account_memo["account_id"] = account_id  # ensure correct account_id
        print("  ✅ Account memo extracted successfully")
    except Exception as e:
        print(f"  ❌ ERROR parsing account memo JSON: {e}")
        print(f"  Raw response preview: {extraction_response_text[:500]}")
        return

    # Save account memo
    save_output(account_id, "account_memo_v1.json", account_memo)

    # Small delay to respect Groq free tier rate limits
    time.sleep(2)

    # --- AGENT SPEC: Generate Retell Agent Config ---
    print("  🤖 Sending to Groq for agent spec generation...")
    agent_spec_prompt = build_agent_spec_prompt(account_memo)
    agent_response_text = call_llm(agent_spec_prompt)

    try:
        agent_spec = extract_json(agent_response_text)
        agent_spec["version"] = "v1"
        agent_spec["account_id"] = account_id
        print("  ✅ Agent spec generated successfully")
    except Exception as e:
        print(f"  ❌ ERROR parsing agent spec JSON: {e}")
        print(f"  Raw response preview: {agent_response_text[:500]}")
        return

    # Save agent spec
    save_output(account_id, "agent_spec_v1.json", agent_spec)
    print(f"  🎉 Pipeline A complete for {account_id}!")

    # Delay between accounts to avoid rate limiting
    time.sleep(3)


# ============================================================
# STEP 7: RUN PIPELINE A ON ALL DEMO TRANSCRIPTS
# ============================================================
def run_pipeline_a():
    print("\n🚀 PIPELINE A STARTED")
    print(f"Looking for demo transcripts in: {DEMO_TRANSCRIPTS_FOLDER}\n")

    if not os.path.exists(DEMO_TRANSCRIPTS_FOLDER):
        print(f"❌ Folder not found: {DEMO_TRANSCRIPTS_FOLDER}")
        print("Make sure you are running this script from the ROOT of your repo.")
        return

    transcript_files = [
        f for f in os.listdir(DEMO_TRANSCRIPTS_FOLDER)
        if f.endswith("_demo.txt")
    ]

    if not transcript_files:
        print("❌ No demo transcript files found. Make sure files end in _demo.txt")
        return

    print(f"Found {len(transcript_files)} demo transcript(s): {transcript_files}")

    for filename in sorted(transcript_files):
        filepath = os.path.join(DEMO_TRANSCRIPTS_FOLDER, filename)
        process_demo_transcript(filepath)

    print(f"\n{'='*60}")
    print("✅ PIPELINE A COMPLETE")
    print(f"Outputs saved to: {OUTPUTS_FOLDER}/")
    print(f"{'='*60}\n")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    run_pipeline_a()
