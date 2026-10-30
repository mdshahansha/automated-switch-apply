#!/usr/bin/env python3
"""Track applications through a date-wise queue under output/job_pipeline/.

Layout:
  output/job_pipeline/<YYYY-MM-DD>/queue.csv        jobs waiting to be applied
  output/job_pipeline/<YYYY-MM-DD>/in_progress.csv  jobs being applied right now
  output/job_pipeline/<YYYY-MM-DD>/completed.csv    applied, skipped or failed
  output/job_pipeline/done/<YYYY-MM-DD>/            the whole day folder, moved
                                                    here once queue and
                                                    in_progress are both empty

Commands:
  python tools/job_pipeline.py add --date D --jobs jobs.json
  python tools/job_pipeline.py start --date D --id ID --model MODEL
  python tools/job_pipeline.py finish --date D --id ID --result applied|skipped|failed [--notes TEXT]
  python tools/job_pipeline.py status [--date D]
"""

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "output" / "job_pipeline"
DONE = PIPELINE / "done"
STAGES = ("queue", "in_progress", "completed")
RESULTS = ("applied", "skipped", "failed")
COLUMNS = [
    "id", "fit", "title", "company", "location", "exp_asked", "link", "portal",
    "posted_date", "stage", "status", "model_used", "resume_used",
    "queued_at", "started_at", "completed_at", "notes",
]
DEFAULT_RESUME = "personal/Mohammad_Shahansha_Resume.pdf"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def day_dir(date: str) -> Path:
    return PIPELINE / date


def read(date: str, stage: str) -> list:
    path = day_dir(date) / f"{stage}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write(date: str, stage: str, rows: list) -> None:
    path = day_dir(date) / f"{stage}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def all_ids(date: str) -> set:
    return {row["id"] for stage in STAGES for row in read(date, stage)}


def take(date: str, stage: str, job_id: str) -> dict:
    rows = read(date, stage)
    for i, row in enumerate(rows):
        if row["id"] == job_id:
            del rows[i]
            write(date, stage, rows)
            return row
    sys.exit(f"job {job_id} is not in {stage}.csv for {date}")


def archive_if_finished(date: str) -> bool:
    if read(date, "queue") or read(date, "in_progress"):
        return False
    DONE.mkdir(parents=True, exist_ok=True)
    target = DONE / date
    if target.exists():
        sys.exit(f"{target} already exists; merge it by hand")
    shutil.move(str(day_dir(date)), str(target))
    return True


def cmd_add(args) -> None:
    if (DONE / args.date).exists():
        sys.exit(f"{args.date} is already archived in done/")
    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    seen = all_ids(args.date)
    queue = read(args.date, "queue")
    added = 0
    for job in jobs:
        job_id = str(job.get("id") or "").strip()
        if not job_id or job_id in seen:
            continue
        row = {col: job.get(col, "") for col in COLUMNS}
        row.update(id=job_id, stage="queue", status="queued", queued_at=now(),
                   resume_used=job.get("resume_used") or DEFAULT_RESUME)
        queue.append(row)
        seen.add(job_id)
        added += 1
    write(args.date, "queue", queue)
    for stage in ("in_progress", "completed"):
        if not (day_dir(args.date) / f"{stage}.csv").exists():
            write(args.date, stage, [])
    print(json.dumps({"date": args.date, "added": added, "queue": len(queue)}))


def cmd_start(args) -> None:
    row = take(args.date, "queue", args.id)
    row.update(stage="in_progress", status="applying", model_used=args.model, started_at=now())
    write(args.date, "in_progress", read(args.date, "in_progress") + [row])
    print(json.dumps({"id": args.id, "stage": "in_progress"}))


def cmd_finish(args) -> None:
    row = take(args.date, "in_progress", args.id)
    row.update(stage="completed", status=args.result, completed_at=now())
    if args.notes:
        row["notes"] = args.notes
    write(args.date, "completed", read(args.date, "completed") + [row])
    archived = archive_if_finished(args.date)
    print(json.dumps({"id": args.id, "status": args.result, "archived_to_done": archived}))


def cmd_status(args) -> None:
    dates = [args.date] if args.date else sorted(
        p.name for p in PIPELINE.glob("*") if p.is_dir() and p.name != "done")
    report = {d: {s: len(read(d, s)) for s in STAGES} for d in dates}
    report["done"] = sorted(p.name for p in DONE.glob("*")) if DONE.exists() else []
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--date", required=True)
    add.add_argument("--jobs", required=True, help="JSON array of jobs using the column names")
    start = sub.add_parser("start")
    start.add_argument("--date", required=True)
    start.add_argument("--id", required=True)
    start.add_argument("--model", required=True, help="model applying, e.g. claude-opus-5-5")
    finish = sub.add_parser("finish")
    finish.add_argument("--date", required=True)
    finish.add_argument("--id", required=True)
    finish.add_argument("--result", required=True, choices=RESULTS)
    finish.add_argument("--notes")
    status = sub.add_parser("status")
    status.add_argument("--date")
    args = parser.parse_args()
    {"add": cmd_add, "start": cmd_start, "finish": cmd_finish, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    main()
