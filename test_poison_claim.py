import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from pipeline.search import gather_evidence_for_claim

claim = "Humans are technically capable of producing poison."
print(f"Testing claim: '{claim}'")
res = gather_evidence_for_claim(claim)

print("\n--- FINAL VERDICT RESULT ---")
print("Label:", res.get("label"))
print("Confidence:", res.get("confidence"))
print("Summary:", res.get("summary"))
print("Reasoning:", res.get("reasoning"))
print("Stopping reason:", res.get("stopping_reason"))
print("Retrieval rounds:", res.get("retrieval_rounds"))
print("Queries executed:", res.get("queries_executed"))

fs = res.get("fact_check_summary", {})
print("\n--- FACT CHECK SUMMARY ---")
print("Searches run:", fs.get("searches_run"))
print("Sources found:", fs.get("sources_found"))
print("Sources accepted:", fs.get("sources_accepted"))
print("Sources blocked:", fs.get("sources_blocked"))
print("Consensus score:", fs.get("consensus_score"))

print(f"\n--- EVIDENCE ITEMS ({len(res.get('evidence', []))}) ---")
for idx, ev in enumerate(res.get("evidence", [])):
    print(f"[{idx+1}] {ev.get('source_title')} ({ev.get('domain')})")
    print(f"    URL: {ev.get('source_url')}")
    print(f"    Stance: {ev.get('stance')} | Supports: {ev.get('supports_claim')} | Rel: {ev.get('relevance_score')} | Indep: {ev.get('is_independent')}")
    print(f"    Explanation: {ev.get('explanation')}")
    print(f"    Snippet: {ev.get('snippet')[:100]}...")
