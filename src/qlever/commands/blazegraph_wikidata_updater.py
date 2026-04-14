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

        Blazegraph may return either:

        1. Clean XML::

            <?xml version="1.0"?>
            <data modified="123" milliseconds="456"/>

        2. An HTML page with stats in ``<p>`` tags (common for the
           default SPARQL endpoint)::

            <html>…
            <p>totalElapsed=40ms, …, mutationCount=27</p>
            <p>COMMIT: totalElapsed=988ms, commitTime=…, mutationCount=27</p>
            </html>

        3. An HTML error page on real failures.
        """
        result = result.strip()

        # Empty response — treat as success (some Blazegraph versions
        # return 200 with empty body for no-op updates).
        if not result:
            log.info("Blazegraph returned empty response (no-op update)")
            return {"time_total_ms": 0}

        # Try clean XML first (<data modified="N" milliseconds="M"/>).
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

        # HTML response — Blazegraph wraps successful UPDATE results in
        # HTML with statistics in <p> tags.  Look for the COMMIT line
        # which confirms the transaction completed.
        commit_match = re.search(
            r"COMMIT:.*?totalElapsed=(\d+)ms.*?mutationCount=(\d+)",
            result,
        )
        if commit_match:
            total_elapsed_ms = int(commit_match.group(1))
            mutation_count = int(commit_match.group(2))
            verbose = getattr(args, "verbose", "no")
            if verbose == "yes":
                log.info(
                    f"Blazegraph: mutationCount={mutation_count}, "
                    f"totalElapsed={total_elapsed_ms}ms"
                )
            return {"time_total_ms": total_elapsed_ms}

        # Also accept the non-COMMIT stats line (update without commit info).
        stats_match = re.search(
            r"totalElapsed=(\d+)ms.*?mutationCount=(\d+)",
            result,
        )
        if stats_match:
            total_elapsed_ms = int(stats_match.group(1))
            mutation_count = int(stats_match.group(2))
            verbose = getattr(args, "verbose", "no")
            if verbose == "yes":
                log.info(
                    f"Blazegraph: mutationCount={mutation_count}, "
                    f"totalElapsed={total_elapsed_ms}ms"
                )
            return {"time_total_ms": total_elapsed_ms}

        # If we got HTML but no recognizable stats, it's likely an error.
        if "<html" in result.lower():
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
