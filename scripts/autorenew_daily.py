#!/usr/bin/env python3
"""Daily auto-renewal of trainer showcase placements (run via cron).

Charges the wallet of every trainer who opted into auto-renewal and whose
placement has expired, extending it by SHOWCASE_PERIOD_DAYS.
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, User
from app.main import _try_extend_placement


def main() -> None:
    db = SessionLocal()
    renewed, failed = 0, 0
    try:
        trainers = db.query(User).filter(
            User.role == "trainer",
            User.showcase_autorenew == True,  # noqa: E712
        ).all()
        now = datetime.utcnow()
        for t in trainers:
            if t.showcase_until and t.showcase_until > now:
                continue  # still active
            if _try_extend_placement(t, db):
                renewed += 1
                print("[%s] renewed trainer #%d (%s)" % (now.isoformat(), t.id, t.email))
            else:
                failed += 1
                print("[%s] FAILED to renew trainer #%d (%s): insufficient balance" % (now.isoformat(), t.id, t.email))
    finally:
        db.close()
    print("done: renewed=%d failed=%d" % (renewed, failed))


if __name__ == "__main__":
    main()
