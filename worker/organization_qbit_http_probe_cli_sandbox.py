"""Explicit sandbox-only GET probe CLI; never reads VIEWTV settings or secrets."""

from __future__ import annotations

import argparse
import json
import sys

from worker.organization_qbit_http_probe_sandbox import check_sandbox_torrent_http


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--sandbox-guid", required=True)
    parser.add_argument("--download-id", required=True, type=int)
    parser.add_argument("--torrent-hash", required=True)
    args = parser.parse_args()

    # Return exactly one strict JSON object for the Windows broker.
    # An HTTP timeout, missing marker, or invalid identity is a denial,
    # never a transport-dependent permission to admit a download.
    decision = check_sandbox_torrent_http(
        args.base_url,
        args.sandbox_guid,
        args.download_id,
        args.torrent_hash,
    )
    result = {"allowed": decision.allowed, "code": decision.code}

    print(json.dumps(result, separators=(",", ":"), allow_nan=False))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
