#!/usr/bin/env python3
"""
Thin wrapper around UpdateWikidataCommand that targets a self-hosted
Blazegraph instance instead of QLever.

Usage::

    python -m qlever.commands.blazegraph_wikidata_updater \
        http://localhost:9999/bigdata/namespace/wdq/sparql

All other flags (--batch-size, --since, --offset, …) are the same as
the upstream ``qlever update-wikidata`` command.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET

from qlever.commands.update_wikidata import UpdateWikidataCommand
from qlever.log import log


class BlazegraphWikidataUpdater(UpdateWikidataCommand):
    """Subclass that overrides only what differs for Blazegraph."""

    def parse_update_result(
        self, result: str, args, curl_cmd: str,
    ) -> dict | str:
        """Parse a Blazegraph SPARQL UPDATE response.

        Blazegraph returns XML like::

            <?xml version="1.0"?>
            <data modified="123" milliseconds="456"/>

        or an HTML error page on failure.
        """
        result = result.strip()

        # Empty response — treat as success (some Blazegraph versions
        # return 200 with empty body for no-op updates).
        if not result:
            log.info("Blazegraph returned empty response (no-op update)")
            return {"time_total_ms": 0}

        # Try XML parse first (the normal success case).
        try:
            root = ET.fromstring(result)
            modified = root.attrib.get("modified", "?")
            millis = int(root.attrib.get("milliseconds", 0))
            verbose = getattr(args, "verbose", "no")
            if verbose == "yes":
                log.info(
                    f"Blazegraph: modified={modified} triples, "
                    f"time={millis}ms"
                )
            return {"time_total_ms": millis}
        except ET.ParseError:
            pass

        # Not valid XML — check for common HTML error markers.
        if "<html" in result.lower() or "<title>" in result.lower():
            # Try to extract a meaningful error message.
            title_match = re.search(
                r"<title>(.*?)</title>", result, re.IGNORECASE | re.DOTALL,
            )
            error_msg = title_match.group(1).strip() if title_match else "unknown"
            log.error(
                f"Blazegraph returned an error page: {error_msg}. "
                f"First 500 chars: {result[:500]}"
            )
            return "error"

        # Unknown format — log and fail.
        log.error(
            f"Unexpected Blazegraph response format. "
            f"First 500 chars: {result[:500]}"
        )
        return "error"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Keep a self-hosted Blazegraph instance synchronized with "
            "Wikidata via the public RDF update stream (SSE)."
        ),
    )
    parser.add_argument(
        "sparql_endpoint",
        help=(
            "Blazegraph SPARQL endpoint URL, e.g. "
            "http://localhost:9999/bigdata/namespace/wdq/sparql"
        ),
    )

    # Register the same flags that UpdateWikidataCommand uses.
    updater = BlazegraphWikidataUpdater()
    updater.additional_arguments(parser)

    args = parser.parse_args()

    # Attributes expected by execute() that are QLever-specific and not
    # relevant for Blazegraph, but must be present on the namespace.
    args.show = False

    success = updater.execute(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
