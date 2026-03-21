"""Run the IMSP Gateway server.

Usage:
    python -m gateway [--port PORT] [--host HOST] [--debug]
"""
from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="IMSP API Gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    os.environ.setdefault("GATEWAY_HOST", args.host)
    os.environ.setdefault("GATEWAY_PORT", str(args.port))
    if args.debug:
        os.environ["GATEWAY_DEBUG"] = "true"

    import uvicorn
    uvicorn.run(
        "gateway.server:app",
        host=args.host,
        port=args.port,
        reload=args.debug,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
