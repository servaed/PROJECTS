"""Evaluate all 36 sample questions against the running app."""
import json, sys, io, time, re
import urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8080"
DOMAINS = ["banking", "telco", "government"]
LANGS   = ["id", "en"]

def get_samples(domain, lang):
    url = f"{BASE}/api/samples?domain={domain}&lang={lang}"
    with urllib.request.urlopen(url) as r:
        return json.load(r)

def ask(question, domain, language="id"):
    payload = json.dumps({"question": question, "domain": domain, "language": language, "history": []}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    answer_tokens = []
    mode_seen = None
    sql_seen = None
    doc_citations = 0
    sql_citation = False
    error = None
    ev = None
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            for raw in resp:
                line = raw.decode("utf-8").rstrip()
                if not line:
                    continue
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                    except Exception:
                        data = data_str
                    if ev == "mode":
                        mode_seen = data.get("mode") if isinstance(data, dict) else data
                    elif ev == "token":
                        tok = data.get("text", data.get("token", "")) if isinstance(data, dict) else data
                        answer_tokens.append(tok)
                    elif ev == "sql":
                        sql_seen = data.get("sql", "") if isinstance(data, dict) else str(data)
                    elif ev == "done":
                        if isinstance(data, dict):
                            doc_citations = len(data.get("doc_citations", []))
                            sql_citation = data.get("sql_citation") is not None
                    elif ev == "error":
                        error = data
    except Exception as exc:
        error = str(exc)
    elapsed = time.time() - start
    return {
        "mode": mode_seen,
        "answer": "".join(answer_tokens),
        "sql": sql_seen,
        "doc_citations": doc_citations,
        "sql_citation": sql_citation,
        "elapsed": round(elapsed, 1),
        "error": error,
    }

def short(text, n=120):
    text = (text or "").strip().replace("\n", " ")
    return text[:n] + "..." if len(text) > n else text

results = []
total = 0
for domain in DOMAINS:
    for lang in LANGS:
        samples = get_samples(domain, lang)
        for s in samples:
            total += 1
            q = s["text"]
            expected_mode = s["mode"]
            print(f"\n[{total:02d}] [{domain}/{lang}] [{expected_mode}]", flush=True)
            print(f"     Q: {q}", flush=True)
            r = ask(q, domain, language=lang)
            mode_ok = r["mode"] == expected_mode
            has_answer = len((r["answer"] or "").strip()) > 20
            fallback = any(kw in (r["answer"] or "").lower() for kw in [
                "not found", "cannot be answered", "no relevant documents",
                "no data", "sql query failed",
            ])
            issues = []
            if not mode_ok:
                issues.append(f"mode={r['mode']} expected={expected_mode}")
            if not has_answer:
                issues.append("empty/short answer")
            if fallback:
                issues.append("fallback response")
            if expected_mode in ("data", "combined") and not r["sql_citation"]:
                issues.append("no SQL citation")
            if expected_mode in ("document", "combined") and r["doc_citations"] == 0:
                issues.append("no doc citations")
            status = "FAIL" if issues else "OK"
            flag = "OK" if status == "OK" else "FAIL"
            print(f"     [{flag}] mode={r['mode']} docs={r['doc_citations']} sql={r['sql_citation']} t={r['elapsed']}s", flush=True)
            if issues:
                print(f"     ISSUES: {'; '.join(issues)}", flush=True)
            print(f"     A: {short(r['answer'])}", flush=True)
            if r["error"]:
                print(f"     ERROR: {r['error']}", flush=True)
            results.append({
                "n": total, "domain": domain, "lang": lang,
                "expected_mode": expected_mode, "question": q,
                "status": status, "issues": issues, **r,
            })

print("\n" + "="*70)
print("EVALUATION SUMMARY")
print("="*70)
ok = sum(1 for r in results if r["status"] == "OK")
fail = sum(1 for r in results if r["status"] == "FAIL")
print(f"PASS: {ok}/{total}   FAIL: {fail}/{total}")

for domain in DOMAINS:
    for lang in LANGS:
        sub = [r for r in results if r["domain"] == domain and r["lang"] == lang]
        sub_ok = sum(1 for r in sub if r["status"] == "OK")
        print(f"  {domain}/{lang}: {sub_ok}/{len(sub)}")

fails = [r for r in results if r["status"] == "FAIL"]
if fails:
    print("\nFAILURES:")
    for r in fails:
        print(f"  [{r['n']:02d}] [{r['domain']}/{r['lang']}] [{r['expected_mode']}]")
        print(f"       Q: {r['question'][:80]}")
        print(f"       Issues: {'; '.join(r['issues'])}")
else:
    print("\nAll questions passed.")

# ── Multi-turn conversation eval ───────────────────────────────────────────
# Tests that follow-up questions resolve correctly with prior history.
# Each scenario is a list of (question, domain, language, expected_mode) turns;
# each turn receives the accumulated history from previous turns.

MULTI_TURN_SCENARIOS = [
    # Banking — ID: drill-down follow-up after a data query
    [
        ("Berapa total outstanding kredit UMKM di Jakarta?", "banking", "id", "data"),
        ("Bagaimana dengan di Bandung?", "banking", "id", "data"),
    ],
    # Banking — EN: follow-up from dokumen to gabungan
    [
        ("What are the credit restructuring conditions per bank policy?", "banking", "en", "document"),
        ("Which customers in Bandung meet those conditions?", "banking", "en", "combined"),
    ],
    # Banking — ID: vague pronoun follow-up ("them" / "mereka")
    [
        ("Tampilkan 5 nasabah dengan eksposur kredit tertinggi.", "banking", "id", "data"),
        ("Apakah mereka memenuhi syarat restrukturisasi?", "banking", "id", "combined"),
    ],
    # Telco — ID: comparative follow-up
    [
        ("Tampilkan utilisasi jaringan per wilayah.", "telco", "id", "data"),
        ("Wilayah mana yang melampaui batas SLA ketersediaan?", "telco", "id", "combined"),
    ],
    # Telco — EN: policy follow-up after data
    [
        ("How many subscribers have churn risk above 70?", "telco", "en", "data"),
        ("Do they qualify for the retention program?", "telco", "en", "combined"),
    ],
    # Government — ID: budget drill-down
    [
        ("Tampilkan realisasi anggaran per satuan kerja.", "government", "id", "data"),
        ("Satuan kerja mana yang berisiko kena penalti APBD?", "government", "id", "combined"),
    ],
    # Government — EN: service standard follow-up
    [
        ("What is the processing time standard for electronic ID cards?", "government", "en", "document"),
        ("Which services are currently below that standard?", "government", "en", "combined"),
    ],
    # Banking — ID: top-N refinement ("top 10 instead")
    [
        ("Tampilkan 5 nasabah dengan total eksposur kredit tertinggi.", "banking", "id", "data"),
        ("Sekarang tampilkan 10 nasabah teratas.", "banking", "id", "data"),
    ],
    # Telco — ID: language carry-over (ask about previous answer in English)
    [
        ("Berapa pelanggan dengan churn risk score di atas 70?", "telco", "id", "data"),
        ("What is the retention eligibility criteria for those subscribers?", "telco", "en", "document"),
    ],
    # Government — EN: follow-up drill into a specific service
    [
        ("Show budget realization per work unit.", "government", "en", "data"),
        ("What is the APBD regulation on the penalty threshold?", "government", "en", "document"),
    ],
]

print("\n" + "="*70)
print("MULTI-TURN CONVERSATION EVAL")
print("="*70)
mt_results = []
mt_total = 0
for scenario_idx, scenario in enumerate(MULTI_TURN_SCENARIOS, 1):
    history = []
    print(f"\nScenario {scenario_idx}:", flush=True)
    for turn_idx, (question, domain, language, expected_mode) in enumerate(scenario, 1):
        mt_total += 1
        print(f"  Turn {turn_idx}: [{domain}/{language}] [{expected_mode}] {question[:70]}", flush=True)
        r = ask(question, domain, language=language)
        mode_ok = r["mode"] == expected_mode
        has_answer = len((r["answer"] or "").strip()) > 20
        fallback = any(kw in (r["answer"] or "").lower() for kw in [
            "not found", "cannot be answered", "no relevant documents",
            "no data", "sql query failed",
        ])
        issues = []
        if not mode_ok:
            issues.append(f"mode={r['mode']} expected={expected_mode}")
        if not has_answer:
            issues.append("empty/short answer")
        if fallback:
            issues.append("fallback response")
        status = "FAIL" if issues else "OK"
        print(f"    [{status}] mode={r['mode']} t={r['elapsed']}s", flush=True)
        if issues:
            print(f"    ISSUES: {'; '.join(issues)}", flush=True)
        print(f"    A: {short(r['answer'])}", flush=True)
        # Build history for next turn
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": r["answer"] or ""})
        mt_results.append({
            "scenario": scenario_idx, "turn": turn_idx,
            "domain": domain, "lang": language,
            "expected_mode": expected_mode, "question": question,
            "status": status, "issues": issues, **r,
        })

mt_ok = sum(1 for r in mt_results if r["status"] == "OK")
mt_fail = sum(1 for r in mt_results if r["status"] == "FAIL")
print(f"\nMulti-turn PASS: {mt_ok}/{mt_total}   FAIL: {mt_fail}/{mt_total}")

mt_fails = [r for r in mt_results if r["status"] == "FAIL"]
if mt_fails:
    print("Multi-turn FAILURES:")
    for r in mt_fails:
        print(f"  Scenario {r['scenario']} Turn {r['turn']}: [{r['domain']}/{r['lang']}]")
        print(f"    Q: {r['question'][:80]}")
        print(f"    Issues: {'; '.join(r['issues'])}")
else:
    print("All multi-turn scenarios passed.")

grand_ok   = ok + mt_ok
grand_total = total + mt_total
print(f"\nGRAND TOTAL: {grand_ok}/{grand_total} passed")
