"""Read-only V18 direct source audit. No status promotions or runtime writes."""
import argparse, ast, csv, json, math, re, subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MASTER="docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md"
CENTRAL="docs/development/v18-five-stage-task-evidence.json"
PERSONA="docs/development/v18-phase08-personality-status-evidence.json"
IDS=re.compile(r"^(?:CA-\d+|ML-\d{3}|GA-\d{3})$")
LABELS=re.compile(r"\b(?:CA-\d+|ML-\d{3}|GA-\d{3})\b")
WORD=re.compile(r"[a-z][a-z0-9]{3,}")
STOP=set("""against already architecture audit based before build change code complete
current data design each ensure evidence existing failed failure from given have
into model models must never only original owner phase production project
projects record records required requirement requirements review reviewed
source sources state support system task tasks test tests their these through
unknown using verified verify where while with without would""".split())
REVIEWED=set("""CA-1101 CA-1102 CA-1701 CA-1702 CA-1703 CA-1704 CA-1705
CA-1706 CA-2101 CA-2304 CA-2501 CA-3003 CA-301 CA-302 CA-303 CA-304
CA-305 CA-306 CA-307 CA-308 CA-309 CA-310 CA-3106 CA-3107 CA-3108
CA-311 CA-3110 CA-312 CA-3308 CA-3505 CA-3701 CA-401 CA-4101
CA-4102 CA-4906 CA-6202 CA-6608 ML-021 ML-027 ML-036""".split())

def words(s):
    s=re.sub(r"([a-z0-9])([A-Z])",r"\1 \2",s)
    return set(WORD.findall(s.lower()))-STOP

def git(root,*args):
    return subprocess.run(["git",*args],cwd=root,capture_output=True,check=True,timeout=30).stdout.decode("utf-8")

def inventory(root):
    rows=[]
    for line in (root/MASTER).read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("|"):continue
        parts=[c.strip() for c in line.strip().strip("|").split("|")]
        if len(parts)==10 and IDS.fullmatch(parts[0]):
            rows.append({"id":parts[0],"kind":parts[2],"requirement":parts[8],"next_proof":parts[9]})
    if len(rows)!=780 or len(set(x["id"] for x in rows))!=780:raise ValueError("bad 780-item original roadmap")
    a=json.loads((root/CENTRAL).read_text(encoding="utf-8"))["tasks"]
    b=json.loads((root/PERSONA).read_text(encoding="utf-8"))["tasks"]
    seen=[x["task_id"] for x in a]+[x["id"] for x in b]
    if len(set(seen))!=len(seen) or not set(seen)<=set(x["id"] for x in rows):
        raise ValueError("bad or overlapping evidence IDs")
    return rows,set(seen)

def target(node):
    return node.id if isinstance(node,ast.Name) else node.attr if isinstance(node,ast.Attribute) else ""

def source_index(root):
    tracked=[p for p in git(root,"ls-files","-z").split("\0") if p.endswith(".py") and p.startswith(("src/sofia/","test/"))]
    entries=[];callers=defaultdict(list);test_calls=defaultdict(list);errors=[]
    for path in tracked:
        f=root/path
        if not f.is_file() or f.is_symlink():continue
        try:
            content=f.read_text(encoding="utf-8-sig")
            tree=ast.parse(content,filename=path)
        except (SyntaxError,UnicodeError) as exc:
            errors.append({"path":path,"exception":type(exc).__name__});continue
        lines=content.splitlines();is_test=path.startswith("test/")
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and not is_test:
                c=target(n.func)
                if len(c)>6:callers[c].append((path,n.lineno))
            if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
            if is_test and not n.name.startswith("test_"):continue
            chunk="\n".join(lines[n.lineno-1:min(n.end_lineno or n.lineno,n.lineno+140)])
            d=ast.get_docstring(n) or ""
            assertive=any(isinstance(v,ast.Assert) or (isinstance(v,ast.Call) and target(v.func).lower() in ("raises","assertequal","asserttrue","assertfalse","assertraises","assertraisesregex")) for v in ast.walk(n))
            entry={"path":path,"line":n.lineno,"name":n.name,"test":is_test,
                   "body":words(chunk[:14000]),"namewords":words(n.name),
                   "doc":words(d),"mentions":set(LABELS.findall(chunk)),
                   "assertive":assertive}
            entries.append(entry)
            if is_test and assertive:
                for v in ast.walk(n):
                    if isinstance(v,ast.Call):
                        c=target(v.func)
                        if len(c)>6:test_calls[c].append((path,n.lineno,n.name))
    inverted=defaultdict(set)
    for i,e in enumerate(entries):
        for w in e["body"]:inverted[w].add(i)
    return tracked,entries,inverted,callers,test_calls,errors

def evaluate(task,entries,inverted,callers,test_calls):
    query=words(task["requirement"])
    known=sorted((w for w in query if w in inverted),key=lambda w:len(inverted[w]))[:28]
    pool=Counter(i for w in known for i in inverted[w])
    ranked=[]
    for i,n in pool.items():
        e=entries[i]
        if e["test"]:continue
        hit=query&e["body"];specific=query&e["namewords"];docs=query&e["doc"]
        exact=task["id"] in e["mentions"]
        if len(hit)<2 and not exact:continue
        score=sum(1+math.log1p(500/(len(inverted.get(w,()))+1)) for w in hit&set(known))+3*len(specific)+2*len(docs)+15*exact
        if score>7:ranked.append((score,i))
    ranked.sort(reverse=True)
    symbols=[];seen=set()
    for score,i in ranked:
        e=entries[i]
        if e["path"] in seen and len(symbols)>0:continue
        seen.add(e["path"])
        refs=callers.get(e["name"],[])
        refs=[{"path":p,"line":ln} for p,ln in refs if p!=e["path"]][:3] if len(refs)<150 else []
        ass=[{"path":p,"line":ln,"test":name} for p,ln,name in test_calls.get(e["name"],[])][:3]
        symbols.append({"path":e["path"],"line":e["line"],"symbol":e["name"],
                        "matching_body_terms":sorted(query&e["body"])[:15],
                        "exact_task_annotation":task["id"] in e["mentions"],
                        "cross_file_callers":refs,"test_assertion_callers":ass,
                        "relevance_score":round(score,2)})
        if len(symbols)>=3:break
    tranked=[]
    for i,n in pool.items():
        e=entries[i]
        if not e["test"] or not e["assertive"]:continue
        hit=query&e["body"]
        exact=task["id"] in e["mentions"]
        if len(hit)<2 and not exact:continue
        score=4*len(query&e["namewords"])+len(hit)+12*exact
        if score>=5:tranked.append((score,i))
    tranked.sort(reverse=True)
    tests=[]
    for score,i in tranked[:3]:
        e=entries[i];tests.append({"path":e["path"],"line":e["line"],"test":e["name"],"assertive":True})
    hascaller=any(s["cross_file_callers"] for s in symbols)
    hastest=any(s["test_assertion_callers"] for s in symbols)
    strength=("symbol_caller_test" if symbols and hascaller and hastest else
              "symbol_caller" if symbols and hascaller else
              "symbol_test" if symbols and hastest else
              "symbol_only" if symbols else "no_source_symbol_link")
    gap=("Reviewed design decision and trade-off signoff not established by code." if task["kind"]=="Design"
         else "Each requirement clause, runtime effects and exact-SHA test results need independent verification." if task["kind"]=="Build"
         else "Required unit/CI/host results have not been executed by this audit." if task["kind"]=="Verify"
         else "Actual scientific outcome, measured gain, and owner-approved training/transfer unproven.")
    return {**task,"direct_code":symbols,"assertion_test_bodies":tests,"source_trace":strength,
            "previous_manual_review":task["id"] in REVIEWED,
            "remaining_acceptance":gap,"status":"UNVERIFIED","tests_run":False,"promoted":False}

def audit(root):
    root=root.resolve(strict=True)
    head=git(root,"rev-parse","--verify","HEAD").strip()
    if not re.fullmatch(r"[0-9a-f]{40}",head):raise ValueError("exact Git SHA required")
    master,classified=inventory(root)
    paths,entries,index,callers,test_calls,errors=source_index(root)
    tasks=[evaluate(x,entries,index,callers,test_calls) for x in master if x["id"] not in classified]
    if len(tasks)!=780-len(classified):raise ValueError("not all unclassified tasks inspected")
    summary={"total":780,"already_classified":len(classified),"source_traced":len(tasks),
             "newly_source_scanned":sum(not t["previous_manual_review"] for t in tasks),
             "prior_manual_review":sum(t["previous_manual_review"] for t in tasks),
             "tracked_python_read":len(paths),"parsed_definitions":len(entries),
             "test_functions_with_assertions":sum(t["test"] and t["assertive"] for t in entries),
             "code_trace_counts":dict(Counter(t["source_trace"] for t in tasks)),
             "parse_errors":len(errors),"promoted_tasks":0}
    return {"schema":"sofia.v18.independent-source-ast-v1","revision":head,
            "utc":datetime.now(timezone.utc).isoformat(),"summary":summary,
            "parse_errors":errors,"tasks":tasks,
            "limitations":["Actual Python bodies, callers and assertion-bearing test functions inspected for relevance.",
                           "Lexical relevance and call graphs are evidence leads, not clause-by-clause proof.",
                           "Tests were read, not executed as acceptance tests.",
                           "No live Venus/Artemis hardware, signed gate reviews, or private user state inspected.",
                           "No task status or gate level promoted."]}

def output(report,out):
    out.mkdir(parents=True,exist_ok=True)
    (out/"v18-direct-code.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (out/"v18-direct-code.csv").open("w",newline="",encoding="utf-8") as f:
        fields=("id","kind","requirement","source_trace","symbols","callers","tests","remaining_acceptance")
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for t in report["tasks"]:
            symbols=t["direct_code"]
            writer.writerow({"id":t["id"],"kind":t["kind"],"requirement":t["requirement"],
                "source_trace":t["source_trace"],
                "symbols":"; ".join(s["path"]+":"+str(s["line"])+" "+s["symbol"] for s in symbols),
                "callers":"; ".join(p["path"]+":"+str(p["line"]) for s in symbols for p in s["cross_file_callers"]),
                "tests":"; ".join(z["path"]+":"+str(z["line"]) for z in t["assertion_test_bodies"]),
                "remaining_acceptance":t["remaining_acceptance"]})
    head=report["revision"]
    lines=["# Sofía V18 Direct Git Code Audit","",
           "Exact Git revision: "+head,"",
           "All 651 unclassified tasks are traced against parsed Python code bodies,",
           "cross-module call sites and assertion-bearing test bodies. The prior 40",
           "manual reviews are separate; the other 611 are automated code inspections.",
           "This is not 611 manual acceptance reviews and no task is promoted.","",
           "## Evidence classification",""]
    lines.extend("- "+k+": "+str(v) for k,v in report["summary"]["code_trace_counts"].items())
    lines+=["","## Requirement-to-code findings",""]
    for t in report["tasks"]:
        lines.extend(["### "+t["id"]+" ["+t["kind"]+"]","",t["requirement"],"",
                     "Code-trace confidence category: "+t["source_trace"],""])
        for s in t["direct_code"]:
            link="https://github.com/Crazysodaman/SofiaAdaLyra/blob/"+head+"/"+s["path"]+"#L"+str(s["line"])
            lines.append("- Source: ["+s["path"]+":"+str(s["line"])+"]("+link+") function/class "+s["symbol"])
            for c in s["cross_file_callers"][:2]:
                cl="https://github.com/Crazysodaman/SofiaAdaLyra/blob/"+head+"/"+c["path"]+"#L"+str(c["line"])
                lines.append("  - Caller: ["+c["path"]+":"+str(c["line"])+"]("+cl+")")
        for s in t["assertion_test_bodies"]:
            tl="https://github.com/Crazysodaman/SofiaAdaLyra/blob/"+head+"/"+s["path"]+"#L"+str(s["line"])
            lines.append("- Test source with assertions: ["+s["test"]+"]("+tl+")")
        lines.extend(["","Unproven: "+t["remaining_acceptance"],""])
    lines+=["## Limits","","Source trace != functional acceptance. Tests not executed by this scanner."]
    (out/"v18-direct-code.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=Path,default=Path("."))
    ap.add_argument("--out",type=Path,default=Path("v18-code-audit-results"))
    args=ap.parse_args()
    result=audit(args.repo);output(result,args.out)
    print(json.dumps(result["summary"],indent=2,sort_keys=True))
