# Usage and inventory lifecycle

## Crawl and analyze

```bash
reconspider crawl --target https://example.com --exclude '/logout*' --output output/run1
reconspider crawl --targets-file targets.txt --scope-file config/scope.example.yaml \
  --max-depth 3 --max-pages 300 --rate-limit 0.25 --output output/run2
reconspider analyze-js --file examples/app.js
```

HTML forms are recorded with names, types, method, and encoding, but no values or submissions. Their actions are not fetched solely because they appear in a form. Query names are observed; names in static JavaScript literals/objects and OpenAPI are inferred. Confidence reflects an extractor's string context, not endpoint existence. WebSocket references are inventoried, never connected.

Only `/robots.txt` and `/sitemap.xml` are standard metadata seeds. Other pages come from observed references; no path wordlist is probed. Linked source maps require `--source-maps`. OpenAPI operation methods are retained as metadata, and dynamic path templates are never requested.

## Passive collection

```bash
reconspider crawl --target https://example.com --passive wayback --passive commoncrawl \
  --commoncrawl-index CC-MAIN-2026-38 --passive-limit 200
# Validation requires permission to fetch the returned historical routes:
reconspider crawl --target https://example.com --passive wayback --validate-passive --max-pages 200
```

These calls use Scrapy's protected public-address transport and bounded response bodies. They do not submit URLs for scans. URLScan uses only public search; optionally export `URLSCAN_API_KEY`. Each source can fail independently; the crawl records errors. Adapters fetch bounded first-page results, so they are not substitutes for exhaustive archive downloads. Historical timestamps are metadata, not current availability checks. Out-of-scope historical references may be recorded but never scheduled.

## Exports, report, and comparison

```bash
reconspider export --input output/run1/crawl_results.jsonl --format json --output results.json
reconspider export --input output/run1/crawl_results.jsonl --format csv --output results.csv
reconspider export --database history.sqlite --format jsonl --output latest.jsonl
reconspider report --input output/run2/crawl_results.jsonl --previous output/run1/crawl_results.jsonl --output output/report
reconspider diff --old output/run1/crawl_results.jsonl --new output/run2/crawl_results.jsonl --output diff.json
```

HTML tables filter by search text, scope, and discovery/request/fetch stage. Summary includes statuses, categories, parameter names, forms, JS files, APIs, errors, skipped URLs, and local duration. Comparisons show added/removed URLs, endpoint-qualified parameter names, JS, APIs, form metadata, and referenced hosts. Form signatures include action/method/encoding/control names/types, not field values. Changed forms appear as a removed and an added signature. Out-of-scope host references remain reported but are excluded from the authorized historical inventory sets. Partial/rate-limited snapshots can create apparent removals.

JSONL is the primary portable format. CSV guards spreadsheet formula prefixes; report HTML escapes untrusted text. Reports do not turn inventory URLs into executable links or claim vulnerabilities. SQLite commits in batches of 100 and at graceful shutdown; use its `runs` table or `--run-id` to export a particular crawl.

## Resume and continuous local runs

```bash
reconspider crawl --target https://example.com --jobdir .scrapy/run1 --output output/run1
# Ctrl-C once, wait for graceful close, then run the identical command to resume.
```

Job state contains queued requests, exact request fingerprints, seen/scheduled sets, and request/discovery counters. Local JSONL appends on a graceful resume. Reusing state for a different scope is unsupported. A fresh crawl requires a fresh job directory (or no job directory).

For repeated independent snapshots, use distinct output directories and compare them. Configure system cron with the installed absolute executable path and your authorized URL; keep authentication and environment variables out of crontab text. Cloud periodic schedules and externally retained exports are described in the deployment guide.

## External snapshot storage

The generic adapter supports authenticated HTTPS endpoints that accept PUT/GET for an object. It does not discover or provision storage. Configure a trusted endpoint outside the target scope:

```bash
export RECON_STORAGE_URL=https://storage.example.net/recon/current.jsonl
# Set RECON_STORAGE_TOKEN securely in your environment, when needed.
reconspider sync push --file output/run2/crawl_results.jsonl
reconspider sync pull --file previous.jsonl
```

Redirects and environment proxies are disabled for this adapter, TLS validation is enabled, and transfer is explicit. Use separate object paths for historical snapshots. It also works with downloaded Cloud item JSONL. Signed object URLs can be supplied through the environment; do not commit them. The adapter is operator-configured and does not apply target hostname scope to your storage service.
