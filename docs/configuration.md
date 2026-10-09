# Configuration

`reconspider crawl --config config/default.yaml` accepts validated YAML settings. CLI options override YAML fields; targets and exclusions are accumulated. Unknown keys and invalid limits cause clear errors. The scope file accepts only `hosts` and `exclude`.

| Option | Default | Meaning |
|---|---|---|
| `--target` | required seed(s) | Repeat for multiple absolute HTTP(S) URLs |
| `--targets-file` | none | UTF-8 file, one URL per line |
| `--scope-file` | none | Additional exact hosts/wildcards and exclusions |
| `--include-subdomains` | false | Explicitly grants descendants of seed hosts |
| `--exclude` | none | Repeat decoded path/URL shell patterns |
| `--max-depth` | 5 | Seed depth zero; redirects retain depth |
| `--max-pages` | 1000 | Total download attempts including robots, retries, passive calls |
| `--rate-limit` | 0.5 | Maximum requests/second per target domain via minimum delay |
| `--concurrency` | 8 | Global requests, while per-domain concurrency remains one |
| `--timeout` | 30 | Seconds per download |
| `--max-body-bytes` | 2097152 | Download/response body limit |
| `--max-discoveries` | 20000 | Total discovery observations before truncation |
| `--max-links-per-page` | 1000 | Bound URLs considered from each response |
| `--ignore-robots` | off | Sets `respect_robots=false`, only with permission |
| `--allow-local` | off | Explicit local/non-public fixture exception |
| `--source-maps` | off | Follow publicly linked source maps and scan embedded sources |
| `--passive` | none | Repeat wayback/commoncrawl/urlscan |
| `--validate-passive` | off | Fetch permitted historical URLs through the ordinary downloader |
| `--passive-limit` | 1000 | Bound records processed per source response |
| `--commoncrawl-index` | CC-MAIN-2026-38 | Explicit index ID; update to an available provider index |
| `--output` | output locally; none on Cloud | Artifact directory |
| `--sqlite` | none | Local database with independent run IDs |
| `--jobdir` | none | Local scheduler/spider state; resume the same scope/settings |
| `--browser` | off | Reserved option; fails until independently guarded egress exists |

AutoThrottle may slow the configured rate further. Passive slots use at least five seconds delay and one concurrent request per source host. Retries are limited to two; 429/503 add exponential 2/4-second delays, respecting numeric Retry-After up to 60 seconds. Retry-After HTTP dates currently fall back to exponential delay. HTTP 403 is never retried.

Wildcard `*.example.com` matches `a.example.com` and deeper descendants, but not `example.com` or `evil-example.com`. Hosts are IDNA-normalized. Exact seed hostnames are automatically allowed. No subdomain enumeration or speculative path generation takes place.

URLs preserve meaningful values and duplicate keys. Endpoint fingerprints remove the query; parameter fingerprints replace each observed value with `VALUE`, preserving key order and duplicates. Those fingerprints are inventory fields and never change request identity.

Changing target limits requires authorization under the program's rules. The `allow_local` flag disables non-public DNS/IP restrictions only; it does not grant hostname scope or override exclusions. The default Twisted HTTP handler, resolver, and scope guard must remain installed. Browser/alternate transport configuration is deliberately rejected through the supported CLI.

Configuration does not automatically load `.env` into the crawler. Export environment variables explicitly; shub can read SHUB_APIKEY using its own CLI support. Do not pass credentials as target URLs or command-line spider arguments.
