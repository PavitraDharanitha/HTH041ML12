"""Flask server: runs the streaming engine in a background thread and exposes REST API + dashboard.
   python app.py [--source sim|csv] [--csv data/skab.csv] [--seed 42] [--tick-ms 100] [--port 8000]"""
import argparse, threading, time
from flask import Flask, jsonify, request, send_from_directory, Response
from sentinel.config import DEMO_SCRIPT
from sentinel.sources import SimulatedSource, CsvSource
from sentinel.engine import Engine
from sentinel.store import Store
from sentinel import report

class Runtime:
    def __init__(self, args):
        self.args, self.lock, self.running, self.speed = args, threading.Lock(), True, 2
        self.store = Store(args.db); self.eng = None; self.new(demo=args.demo)
        threading.Thread(target=self.loop, daemon=True).start()
    def new(self, demo=False):
        a = self.args; self.store.new_run()
        src = CsvSource(a.csv) if a.source == "csv" else SimulatedSource(seed=a.seed, script=DEMO_SCRIPT if demo else None)
        with self.lock: self.eng = Engine(src, on_alert=self.store.add_alert, seed=a.seed)
    def loop(self):
        while True:
            if self.running:
                with self.lock:
                    for _ in range(self.speed):
                        if self.eng.done: self.running = False; break
                        self.eng.step()
            time.sleep(self.args.tick_ms / 1000)

def create_app(args):
    rt = Runtime(args); app = Flask(__name__, static_folder="dashboard"); app.rt = rt

    @app.get("/")
    def index(): return send_from_directory("dashboard", "index.html")
    @app.get("/api/state")
    def state():
        with rt.lock: s = rt.eng.snapshot()
        s.update(running=rt.running, speed=rt.speed, source=rt.eng.src.kind); return jsonify(s)
    @app.post("/api/inject")
    def inject():
        d = request.get_json(force=True)
        with rt.lock: r = rt.eng.inject(int(d["sensor"]), d["type"], d.get("mag"), d.get("dur"))
        return (jsonify(ok=True, id=r) if r else (jsonify(ok=False, error="not ready / unsupported source"), 409))
    @app.post("/api/feedback")
    def feedback():
        d = request.get_json(force=True)
        with rt.lock: m = rt.eng.feedback(int(d["alert_id"]), bool(d["useful"]))
        rt.store.add_feedback(int(d["alert_id"]), bool(d["useful"])); return jsonify(ok=True, multiplier=round(m, 2))
    @app.post("/api/control")
    def control():
        d = request.get_json(force=True); a = d.get("action")
        if a == "pause": rt.running = False
        elif a == "resume": rt.running = True
        elif a == "demo": rt.new(demo=True); rt.running = True
        elif a == "reset": rt.new(demo=False); rt.running = True
        elif a == "speed": rt.speed = max(1, min(8, int(d.get("value", 2))))
        else: return jsonify(ok=False), 400
        return jsonify(ok=True)
    @app.get("/api/report")
    def rep():
        with rt.lock: return jsonify(report.build(rt.eng))
    @app.get("/api/report.md")
    def repmd():
        with rt.lock: return Response(report.markdown(report.build(rt.eng)), mimetype="text/markdown")
    @app.get("/api/history")
    def history(): return jsonify(rt.store.history())
    return app

def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sim", "csv"], default="sim"); ap.add_argument("--csv"); ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tick-ms", type=int, default=100); ap.add_argument("--port", type=int, default=8000); ap.add_argument("--db", default="sentinel.db")
    ap.add_argument("--demo", action="store_true", help="start with the scripted fault sequence"); return ap.parse_args(argv)

if __name__ == "__main__":
    a = parse(); print(f"SentinelIQ running at http://localhost:{a.port}"); create_app(a).run(host="0.0.0.0", port=a.port, threaded=True)
