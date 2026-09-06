"""Rebuild data_sources/stations/india_stations.json from erail's public JS.

erail.in ships its entire IR station directory (code,name pairs, ~9,100 entries
including tourist aliases like Ooty→UAM, Kodaikanal→DG, Manali→SML) at
/js/cmp/stations.js. We bundle it so city→station-code resolution works for
essentially any rail-served Indian town, offline (gate doc: erail_train_source.md).

Run occasionally to refresh; the generated file is committed. The parser lives
in utils.geo so tests can replay the recorded fixture (tests/data/erail_stations_fixture.js).
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.geo import STATIONS_URL, parse_station_blob  # noqa: E402

OUT = ROOT / "data_sources" / "stations" / "india_stations.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def main() -> None:
    req = urllib.request.Request(STATIONS_URL, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    pairs = parse_station_blob(raw)
    if len(pairs) < 8000:
        raise SystemExit(f"parse yielded only {len(pairs)} stations — erail format changed?")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    import json
    OUT.write_text(json.dumps(pairs, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"wrote {len(pairs)} stations → {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
