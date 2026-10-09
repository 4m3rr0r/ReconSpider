# ReconSpider

ReconSpider inventories the web attack surface of **explicitly authorized targets** using Scrapy's asynchronous downloader. It discovers observed URLs, static JavaScript route references, parameters, forms, API documentation, and optional historical references. Classifications are hints, never vulnerability claims.

Python 3.11+, Ubuntu, MIT licensed. Local CLI and a `universal` spider configured for Zyte Scrapy Cloud project **881056**. This repository has not been deployed to Cloud; deployment and job execution require your platform credentials.

## Quick start on Ubuntu

```bash
sudo apt-get update
sudo apt-get install python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
reconspider --help
```

Some Ubuntu versions ship Python older than 3.11. Install a supported interpreter first. Chromium is not needed.

```bash
reconspider crawl --target https://example.com --max-depth 5 --max-pages 1000
reconspider crawl --targets-file targets.txt --scope-file config/scope.example.yaml
reconspider crawl --target https://example.com --exclude '/logout*' --sqlite history.sqlite
reconspider analyze-js --file examples/app.js
reconspider export --format csv --output output/results.csv
reconspider report --input output/crawl_results.jsonl --previous previous.jsonl
reconspider diff --old previous.jsonl --new output/crawl_results.jsonl
```

Replace example.com with a target you are permitted to crawl. Target files contain one absolute HTTP(S) URL per line, with optional `#` comment lines.

## Working local demonstration

In one terminal:

```bash
python examples/local_app.py --port 8000
```

In another:

```bash
reconspider crawl --target http://127.0.0.1:8000 --allow-local \
  --max-pages 30 --rate-limit 10 --output output/demo
reconspider report --input output/demo/crawl_results.jsonl --output output/demo
```

The fixture includes links, JS, forms, robots exclusions, a sitemap, an API, OpenAPI metadata, and a redirect. `--allow-local` explicitly disables the non-public address restriction for authorized local fixtures; hostname and exclusion checks still apply. Keep it off for public targets. Saved example results are in [examples/results](examples/results).

## Features and defaults

* Explicit exact-host and `*.host` scope, path exclusions, redirect validation, protected DNS address delivery, and public-address filtering.
* HTML anchors/navigation, frames, scripts, stylesheets, images/media, canonical links, refresh metadata, URL-valued data attributes, embedded JSON, robots sitemap declarations, recursive XML sitemaps.
* Conservative static JS extraction for fetch, XHR, axios, jQuery URLs, API route literals, imports, URL constructors, GraphQL, and WebSocket references. No code evaluation or token reconstruction.
* Observed query/form parameters and statically inferred JS/OpenAPI parameters; POST form metadata without submission. Source maps require explicit opt-in.
* Independent Internet Archive, Common Crawl, and URLScan passive adapters. Source attribution and timestamps retained; validation is off by default.
* Exact canonical URL identity preserves values, duplicate query keys, and query order. Separate endpoint and parameter-pattern fingerprints support grouping without discarding observations.
* JSONL stream, JSON/CSV/TXT exports, optional SQLite runs, searchable HTML reports, and historical inventory comparisons.
* Robots obedience, two-second domain delay, one concurrent request per domain, AutoThrottle, depth five, and a 1,000-attempt request budget. Global concurrency defaults to eight across different domains.
* Two retries, asynchronous exponential 429/503 backoff, TLS certificate verification, timeouts, body limits, graceful Ctrl-C, local resumable scheduler state, and JSON logs.

`max_pages` is a strict download-attempt budget, including internal robots requests, retries, redirects, and passive API calls. Robots-denied URLs remain discoveries and are not counted as dispatched requests. `max_discoveries=20000` and `max_links_per_page=1000` bound extraction/inventory growth. These limits intentionally trade completeness for resource control.

## Scope configuration

```yaml
hosts:
  - example.com
  - '*.authorized.example.com'
exclude:
  - /logout*
  - /delete*
  - 'https://example.com/private*'
```

Targets grant their exact hosts automatically. Wildcards authorize descendants of the listed host, not the wildcard root itself. `--include-subdomains` is an **explicit authorization grant** for descendants of each target; it is never enabled implicitly or based on a public suffix calculation. Scope files add authorized hosts but do not seed unknown subdomains. Exclusions are case-sensitive shell patterns against decoded normalized paths or URLs. They apply before any crawler or robots download.

Discovery of an external reference does not authorize its download. Literal non-public IPs are blocked before scheduling; DNS answers containing any non-public address are withheld entirely from Twisted's connection endpoint. Every new resolution is checked, preventing public-to-private DNS rebinding. Proxies and alternate HTTP handlers must not replace the protected transport.

## Architecture

```text
CLI / validated Cloud arguments
              |
     Scope + URL identities
              |
     Scrapy scheduler / downloader
     | early scope guard | robots | budget | protected DNS/TLS |
              |
     HTML / JS / XML / JSON extractors
              |
     normalized inventory + provenance
              |
     JSONL / optional SQLite / Cloud items
              |
     exports / HTML report / snapshot diff
```

Core rules live in `reconspider/core`; extraction in `extractors`; passive response adapters in `passive`; the spider orchestrates discovery and scheduling. `storage` streams results and retains local runs; `reports` builds artifacts independently of the crawler. No synchronous target-fetch loop is used. Optional HTTPS snapshot transfer uses httpx outside the crawl.

## Outputs

A local run produces:

```text
output/
  all_urls.txt
  unique_urls.txt
  urls_with_parameters.txt
  parameters.json
  forms.json
  javascript_files.txt
  api_endpoints.txt
  interesting_endpoints.txt
  out_of_scope_references.txt
  crawl_results.jsonl
  summary.json
  report.html
```

JSONL records have `kind` values `url`, `request`, `response`, `form`, `skipped`, `error`, and local `run` metadata. A `url` record records discovery only, even if a later request is scheduled. A `request` records dispatch to the download handler, not proof of network success. A `response` records an HTTP response, including errors; `successful` indicates 2xx. Join them by canonical `url` to derive lifecycle state. Passive references carry `historical=true`. Forms never store field values and never submit; literal URL query values are preserved and may require restricted storage.

Each repeated discovery keeps its provenance. `unique_urls.txt` deduplicates identities; `all_urls.txt` retains observations. Inventory sets in comparisons use in-scope URLs; out-of-scope references remain in reports. Removed discoveries describe snapshot differences, not confirmed removal from a live application.

## Zyte Scrapy Cloud

```bash
shub login
shub deploy 881056
shub schedule 881056/universal -u 1 \
  -a target=https://example.com -a max_pages=1000 -a max_depth=5
```

`shub schedule` starts a job, while periodic scheduling is configured separately in the platform or your scheduler. The Cloud default emits standard Scrapy items without creating local persistence. Export results after a job:

```bash
shub items 881056/SPIDER_ID/JOB_ID > current.jsonl
reconspider report --input current.jsonl --output output/cloud
reconspider diff --old previous.jsonl --new current.jsonl
```

See [deployment](docs/zyte-deployment.md), [installation](docs/installation.md), [configuration](docs/configuration.md), and [usage](docs/usage.md). The stack selection follows [Zyte's deployment tutorial](https://docs.zyte.com/web-scraping/tutorial/cloud.html); `requirements.txt` extends the stack as described in [shub deployment documentation](https://shub.readthedocs.io/en/latest/deploying.html).

## Development and verification

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check .
ruff format --check .
python -m build
scrapy list
```

Tests use mocks, deterministic response fixtures, and a loopback HTTP server, with no public bounty targets. They cover scope boundaries, exclusion decoding, redirects, normalization, query identity, extractors, passive filtering, budgets, reports, storage, and address-stream rebinding. Compatibility is checked against Scrapy 2.14 and 2.19. Actual Cloud deployment, provider credentials/policies, and platform egress are separate operational checks.

## Troubleshooting and limitations

* No requests: check scope, non-public DNS answers, exclusions, robots rules, and remaining budget. A tiny budget can be consumed by robots before a target page is fetched.
* HTTP 403, CAPTCHA, or access restrictions: record the response and stop there. There is no bypass logic.
* Passive errors: check the provider status/API access, index selection, and source policies. The adapters take bounded first-page snapshots, not full archive exhaustiveness. URLScan caps a request at 100 results; Common Crawl defaults to one configured index. An absent/stale index can return an error; choose an available index explicitly.
* JavaScript extraction is conservative regex/literal scanning, not a complete AST interpreter. Dynamic concatenations, computed templates, bundled runtime routes, CSS URLs, and undocumented payload schemas may be missed; false positives are possible. Query values are preserved, including nested URL references, without inventing parameter values.
* Browser rendering is disabled. `--browser` fails explicitly because Playwright subresources and DNS use a separate transport. The optional dependency alone is insufficient: independently enforced browser egress is a roadmap item, rather than a silent scope gap. Source maps are static-only and opt-in.
* POST-only APIs are inventoried but never invoked with POST. Templated OpenAPI paths are not fetched. Form actions are inventoried without being fetched solely because of their form appearance.
* Automatic reports load the bounded inventory into memory. Raise discovery limits carefully; large offline report generation needs more memory than crawling. The 768 MiB memory limit is a project guard, not an assertion about current Cloud unit quotas.
* `JOBDIR` supports graceful local resume only. Keep target/scope/settings identical; do not reuse it for independent snapshots. Scheduler and spider counters are persisted at graceful shutdown; a forced kill may lose recent state. Local output appends on resume. Cloud local files are ephemeral and do not establish run-to-run history.
* Host scope permits all ports of an authorized host. IP-layer classification cannot protect against a public-address reverse proxy that itself accesses internal resources. The HTTPS storage endpoint is an operator-configured service outside target scope; configure it only for trusted storage.

## Ethical use and roadmap

Use this tool only where you have explicit permission and follow the program's rate and resource limits. There are no form submissions, brute force, vulnerability payloads, authentication bypasses, credential reconstruction, CAPTCHA/WAF bypasses, or proxy rotation. Inventory data may be sensitive; control access and retention.

Future work: a browser with a pinned, scope-enforced egress proxy; a modern JS AST backend; pagination and archive checkpointing under provider quotas; streaming report generation for very large inventories; provider-specific storage adapters; and a live Cloud compatibility pipeline with test credentials.
