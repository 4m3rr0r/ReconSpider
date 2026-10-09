"""Local fixture only. Run: python examples/local_app.py --port 8000"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGES = {
    "/": (
        "text/html",
        '<html><a href="/account?id=1&id=2">Account</a><a href="/redirect">Redirect</a><a href="/blocked">Blocked</a><script src="/app.js"></script><form action="/search" method="get"><input name="q"></form><iframe src="/frame"></iframe><a href="https://external.invalid/">External</a></html>',
    ),
    "/robots.txt": ("text/plain", "User-agent: *\nDisallow: /blocked\nSitemap: /sitemap.xml\n"),
    "/sitemap.xml": (
        "application/xml",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>/download</loc></url></urlset>',
    ),
    "/app.js": (
        "application/javascript",
        'fetch("/api/v1/users?limit=10"); axios.post("/api/profile", {data:{name:"example"}}); const endpoint="/graphql";',
    ),
    "/api/v1/users": ("application/json", '{"users":[],"documentation":"/openapi.json"}'),
    "/openapi.json": (
        "application/json",
        '{"openapi":"3.0.0","paths":{"/api/users/{id}":{"get":{"parameters":[{"name":"id","in":"path"}]}}}}',
    ),
    "/blocked": ("text/html", "Should never be fetched when respecting robots"),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        content_type, body = PAGES.get(path, ("text/html", "<html>Local fixture</html>"))
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Fixture listening at http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
