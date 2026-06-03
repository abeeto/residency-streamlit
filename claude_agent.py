import json
import os
import re

import anthropic
import streamlit as st

SYSTEM_PROMPT = """You are a medical residency research assistant. Your job is to determine
whether a US residency program explicitly states on their official website
that they will not grant interviews to applicants who have not signalled
them through ERAS. ALWAYS ASSUME INTERNAL MEDICINE RESIDENCY PROGRAMS IN THE UNITED STATES WHEN GIVEN A PROGRAM NAME, UNLESS THE PROGRAM NAME EXPLICITLY INCLUDES A DIFFERENT SPECIALTY.
This is a strict binary check. You are NOT inferring, guessing, or
interpreting. You are only looking for an explicit written statement
on the program's official website that says something equivalent to:
"We do not interview applicants who have not signalled us" or
"Signalling is required to receive an interview invitation."
If no such explicit statement exists on the website, the answer is
"Not Found." This is not a negative result — it is simply the absence
of an explicit requirement.
## Your process for each program:
### Step 1 — Find the official website
Use web search with query: "[Program Name] residency program official site"
Identify the official program or hospital department URL from results.
Ignore SDN, Doximity, Reddit, or any third-party sources.
### Step 2 — Fetch the homepage
Fetch the homepage of the official site.
Extract every internal link on the page.
### Step 3 — Filter internal links
From all internal links, keep only pages whose URL path or anchor text
contains any of these keywords (case-insensitive):
apply, application, how-to-apply, international, img, foreign, faq,
frequently-asked, interview, selection, eligibility, signal, eras,
about, overview, program, prospective, residents, admissions, recruit
Discard pages whose URL or anchor text contains:
news, events, staff, faculty, directory, contact, donate, research,
publications, gallery, login, portal, careers, jobs
### Step 4 — Fetch all filtered pages
Fetch every page that passed the filter. Do not skip any.
Read the full content of each page.
### Step 5 — Search for explicit signal language
As you read each page, look for any sentence or passage that explicitly
states the program will not interview or will not consider applicants
who have not signalled them.
Trigger phrases to watch for:
- "signal", "signalled", "signaling"
- "will not interview"
- "required to receive an interview"
- "only applicants who have signalled"
- Any equivalent phrasing that conditions interviews on signalling
### Step 6 — Fallback if few links found
If the homepage yields fewer than 5 internal links after filtering
(e.g. the site is a SPA or hospital portal), run a second search:
"[Program Name] residency apply signal site:[domain]"
Fetch any new pages this surfaces that were not already fetched.
### Step 7 — Output
Return a JSON object with exactly these fields:
{
  "program": "<program name as given>",
  "signal_required_explicit": true | false,
  "verbatim_quote": "<exact sentence(s) from the page>" | null,
  "source_url": "<exact URL of the page containing the quote>" | null
}
Only populate verbatim_quote and source_url if signal_required_explicit
is true. Otherwise both fields are null."""

TOOLS = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
    {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 20},
]


def _get_client() -> anthropic.Anthropic:
    api_key = None
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        pass
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=api_key)


def _extract_json(text: str) -> dict | None:
    # Try ```json ... ``` block first
    code_block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    # Fall back to last bare JSON object containing "program"
    matches = list(re.finditer(r"\{[^{}]*\"program\"[^{}]*\}", text, re.DOTALL))
    for m in reversed(matches):
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            continue
    return None


def check_program(program_name: str, stream_callback=None) -> dict:
    client = _get_client()
    full_text = ""

    with client.messages.stream(
        model="claude-sonnet-4-6",
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[{"role": "user", "content": f"Check this residency program: {program_name}"}],
        max_tokens=16000,
    ) as stream:
        for chunk in stream.text_stream:
            full_text += chunk
            if stream_callback:
                stream_callback(full_text)

    parsed = _extract_json(full_text)
    if parsed:
        return parsed

    return {
        "program": program_name,
        "signal_required_explicit": None,
        "verbatim_quote": None,
        "source_url": None,
        "error": "Could not parse JSON from response",
        "raw_response": full_text,
    }
