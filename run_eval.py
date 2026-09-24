"""Batch evaluation over several seeds: python run_eval.py [--seeds 10] [--csv path]"""
import argparse, json, numpy as np
from sentinel.config import DEMO_SCRIPT
from sentinel.sources import SimulatedSource, CsvSource
from sentinel.engine import Engine
from sentinel import report

def run(seed=42, csv=None, ticks=620):
    eng = Engine(CsvSource(csv) if csv else SimulatedSource(seed=seed, script=DEMO_SCRIPT), seed=seed)
    while not eng.done and (csv or eng.t < ticks): eng.step()
    return report.build(eng)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=10); ap.add_argument("--csv"); a = ap.parse_args()
    reps = [run(csv=a.csv)] if a.csv else [run(s) for s in range(a.seeds)]
    if a.csv: print(report.markdown(reps[0])); raise SystemExit
    print(f"{'seed':>4} {'det':>5} {'type✓':>6} {'lat':>5} {'raw':>5} {'naive':>6} {'pings':>6} {'FP':>3} {'blip→op':>8}")
    for i, r in enumerate(reps): print(f"{i:>4} {r['detected']:>2}/{r['injected']:<2} {r['type_correct']:>6} {r['mean_latency_s']:>5} {r['raw']:>5} {r['naive_alerts']:>6} {r['pings']:>6} {r['false_positive_alerts']:>3} {r['blips_reaching_operator']:>4}/{r['blips']}")
    tot = lambda k: sum(r[k] for r in reps)
    print(f"\nTOTAL detected {tot('detected')}/{tot('injected')}, type-correct {tot('type_correct')}, mean pings {tot('pings')/len(reps):.1f} vs naive {tot('naive_alerts')/len(reps):.0f}, unexplained alerts {tot('false_positive_alerts')}")
    open("reports/eval_summary.json", "w").write(json.dumps(reps, indent=1)); open("reports/sample_report.md", "w").write(report.markdown(reps[0]))
