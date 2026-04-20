"""Entry point: `python -m voxflow`."""
from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from voxflow.app import VoxFlowApp


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = VoxFlowApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
