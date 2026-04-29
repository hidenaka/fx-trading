import http.server
import socketserver
import json
import os
from pathlib import Path

PORT = 8000
DATA_DIR = Path("dashboard/data")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    
    def do_GET(self):
        # Serve JSON files from dashboard/data
        if self.path.endswith('.json'):
            filepath = DATA_DIR / self.path.lstrip('/')
            if filepath.exists():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Not found"}).encode())
                return
        
        # Serve static files from dashboard directory
        if self.path == '/':
            self.path = '/index.html'
        
        # Try dashboard directory first
        dashboard_file = Path("dashboard") / self.path.lstrip('/')
        if dashboard_file.exists():
            self.send_response(200)
            if self.path.endswith('.html'):
                self.send_header('Content-type', 'text/html')
            elif self.path.endswith('.js'):
                self.send_header('Content-type', 'application/javascript')
            elif self.path.endswith('.css'):
                self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open(dashboard_file, 'rb') as f:
                self.wfile.write(f.read())
            return
        
        super().do_GET()

def run_server(port=PORT):
    if not Path("dashboard").exists():
        os.chdir("fx_trading")
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"Dashboard server running at http://localhost:{port}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
