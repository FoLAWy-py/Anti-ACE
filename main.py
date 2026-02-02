"""Compatibility entrypoint.

The implementation lives in the `antiace` package now.
"""

from antiace.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
