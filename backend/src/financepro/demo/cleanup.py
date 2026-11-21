"""Deletes idle demo sandboxes. Run daily by .github/workflows/demo-cleanup.yml (the API itself sleeps
on the free plan, so it can't be trusted to run a timer); sandbox creation also cleans up on the way in."""

from sqlalchemy.orm import Session

from financepro.db import get_engine
from financepro.demo.sandbox import cleanup


def main() -> None:
    with Session(get_engine()) as db:
        print(f"Deleted {cleanup(db)} idle sandbox(es).")


if __name__ == "__main__":
    main()
