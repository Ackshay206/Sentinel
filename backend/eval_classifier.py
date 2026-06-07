"""Evaluate the scam classifier against the labeled dataset.

Runs the LIVE classifier (same code path as production) over:
  - Data/English_Scam.txt      (label = scam)
  - Data/English_NonScam.txt   (label = not scam)
  - Data/FullTranscriptData.csv (label = scam; real YouTube scam calls)

Reports precision / recall / F1 + confusion matrix, sample misses, and the
predicted scam_type distribution (= taxonomy coverage). This is the baseline we
measure taxonomy changes against.

Usage (from backend/, venv active, OPENAI_API_KEY set):
    python eval_classifier.py                 # quick sample (80/class)
    python eval_classifier.py --limit 200     # bigger sample
    python eval_classifier.py --full          # everything
    python eval_classifier.py --no-csv        # skip the real-call slice
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from pathlib import Path

from app.classifier import classify
from app.config import get_settings

DATA = Path(__file__).parent / "Data"

# Template placeholders in the synthetic data → realistic fillers.
PLACEHOLDERS = {
    "[Greetings]": "Hello",
    "[Company]": "Acme Services",
    "[Product]": "your account",
    "[Name]": "Alex Carter",
    "[Title]": "Officer",
    "[Money]": "$500",
    "[Number]": "your account",
    "[Date]": "today",
}
_NUM_PREFIX = re.compile(r"^\s*(?:\d+\.\s*)+")
_ANY_PLACEHOLDER = re.compile(r"\[[^\]]+\]")


def clean(line: str) -> str:
    line = _NUM_PREFIX.sub("", line.strip())
    for k, v in PLACEHOLDERS.items():
        line = line.replace(k, v)
    line = _ANY_PLACEHOLDER.sub("the company", line)  # any remaining [X]
    return line.strip()


def load_lines(path: Path) -> list[str]:
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        c = clean(raw)
        if len(c) >= 12:  # drop blanks / stray numbers
            out.append(c)
    return out


def load_csv(path: Path) -> list[str]:
    out: list[str] = []
    with path.open(encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            content = (row.get("Content") or "").strip()
            if len(content) >= 40:
                out.append(content[:4000])  # cap very long transcripts
    return out


def is_scam_pred(result: dict | None) -> bool | None:
    """Binary prediction from the classifier output. None = classifier error."""
    if result is None:
        return None
    return result.get("scam_type", "none") != "none"


async def run_slice(name: str, texts: list[str], concurrency: int) -> list[dict | None]:
    sem = asyncio.Semaphore(concurrency)

    async def one(t: str):
        async with sem:
            return await classify(t)

    print(f"  classifying {len(texts)} {name} examples…", flush=True)
    return await asyncio.gather(*(one(t) for t in texts))


def metrics(tp: int, fp: int, tn: int, fn: int) -> dict:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) else 0.0
    return {"precision": prec, "recall": rec, "specificity": spec, "f1": f1, "accuracy": acc}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=80, help="examples per class (ignored with --full)")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--no-csv", action="store_true")
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()

    import logging
    logging.getLogger("sentinel.classifier").setLevel(logging.ERROR)  # quiet per-call + retry logs

    if not get_settings().has_openai:
        sys.exit("OPENAI_API_KEY not set — eval needs the classifier.")

    scam = load_lines(DATA / "English_Scam.txt")
    nonscam = load_lines(DATA / "English_NonScam.txt")
    real = [] if args.no_csv else load_csv(DATA / "FullTranscriptData.csv")

    if not args.full:
        scam = scam[: args.limit]
        nonscam = nonscam[: args.limit]
        real = real[: max(1, args.limit // 2)]

    print(f"Model: {get_settings().openai_model}")
    print(f"Dataset: {len(scam)} scam, {len(nonscam)} non-scam, {len(real)} real-call scam\n")

    scam_res = await run_slice("synthetic-scam", scam, args.concurrency)
    nonscam_res = await run_slice("non-scam", nonscam, args.concurrency)
    real_res = await run_slice("real-call scam", real, args.concurrency) if real else []

    # Binary metrics (scam = positive). Real-call slice folds into scam positives.
    tp = fp = tn = fn = errors = 0
    type_counts: dict[str, int] = {}
    fn_samples: list[str] = []
    fp_samples: list[str] = []

    for text, r in list(zip(scam, scam_res)) + list(zip(real, real_res)):
        pred = is_scam_pred(r)
        if pred is None:
            errors += 1
            continue
        st = r.get("scam_type", "none")
        type_counts[st] = type_counts.get(st, 0) + 1
        if pred:
            tp += 1
        else:
            fn += 1
            if len(fn_samples) < 6:
                fn_samples.append(text[:140])

    for text, r in zip(nonscam, nonscam_res):
        pred = is_scam_pred(r)
        if pred is None:
            errors += 1
            continue
        if pred:
            fp += 1
            if len(fp_samples) < 6:
                fp_samples.append(f"[{r.get('scam_type')}/{r.get('confidence')}] {text[:120]}")
        else:
            tn += 1

    m = metrics(tp, fp, tn, fn)
    print("\n================ RESULTS ================")
    print(f"Confusion:  TP={tp}  FP={fp}  TN={tn}  FN={fn}  (errors={errors})")
    print(f"Precision : {m['precision']:.3f}")
    print(f"Recall    : {m['recall']:.3f}   <- scams caught")
    print(f"Specificity:{m['specificity']:.3f}   <- benign correctly cleared")
    print(f"F1        : {m['f1']:.3f}")
    print(f"Accuracy  : {m['accuracy']:.3f}")

    print("\nPredicted scam_type distribution (scam-labeled examples):")
    for st, c in sorted(type_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {st:20s} {c}")
    unknown = type_counts.get("unknown", 0)
    total_typed = sum(type_counts.values()) or 1
    print(f"  -> 'unknown' rate: {unknown / total_typed:.1%} (lower = better taxonomy coverage)")

    if fn_samples:
        print("\nMissed scams (false negatives):")
        for s in fn_samples:
            print(f"  ✗ {s}")
    if fp_samples:
        print("\nFalse alarms on benign (false positives):")
        for s in fp_samples:
            print(f"  ! {s}")
    print("=========================================")


if __name__ == "__main__":
    asyncio.run(main())
