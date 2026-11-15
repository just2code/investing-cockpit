"""Add a Tijori sector to sectors.csv from pasted text (one company per line, first column = name or symbol).
Usage:  python tools/paste_to_csv.py "TJI Realty" < pasted.txt
"""
import sys, re, difflib, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.universe import load_nifty500, ROOT


def norm(x):
    w = re.sub(r"[^a-z0-9 ]", " ", x.lower()).split()
    return " ".join(i for i in w if i not in ("ltd", "limited"))


sector = sys.argv[1]
n5 = load_nifty500()
by_name = {norm(n): s for n, s in zip(n5.name, n5.symbol)}
syms = set(n5.symbol)
found, missing = [], []
for line in sys.stdin:
    t = re.split(r"\t|\s{2,}", line.strip())[0]
    if not t:
        continue
    if t.upper() in syms:
        found.append(t.upper())
        continue
    m = difflib.get_close_matches(norm(t), by_name, n=1, cutoff=0.85)
    if m:
        found.append(by_name[m[0]])
    else:
        missing.append(t)

with open(ROOT / "sectors.csv", "a") as f:
    for s in sorted(set(found)):
        f.write(f"{sector},{s},{dt.date.today().isoformat()}\n")
print(f"added {len(set(found))} to '{sector}'")
if missing:
    print("NOT matched (outside Nifty 500 or spelled differently); add manually as NSE symbols:")
    print("\n".join("  " + m for m in missing))
