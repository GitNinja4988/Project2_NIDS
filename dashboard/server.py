#!/usr/bin/env python3
import csv
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class Settings:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    STATIC_DIR = Path(__file__).resolve().parent / "static"
    HOST = "127.0.0.1"
    PORT = 8765
    SAFE_CMD = re.compile(
        r"^python(?:3(?:\.\d+)?)?"
        r"(?:\s+-m\s+[\w.]+|\s+[\w./-]+\.py)"
        r"(?:\s+[\w./=-]+)*$"
    )
    PRESETS = {
        "smoke": {
            "label": "Smoke test",
            "command": "python tests/smoke_test.py",
            "hint": "~3 s · synthetic data · must end with SYNTHETIC smoke test passed",
        },
        "sample": {
            "label": "Sample runs (main.py)",
            "command": "python main.py",
            "hint": "~50 s · 36 runs on data/sample/",
        },
        "analysis_sample": {
            "label": "Analysis (sample)",
            "command": "python -m src.analysis --scope sample",
            "hint": "~1–4 s · tables + figures from saved sample runs",
        },
        "download_unsw": {
            "label": "Download UNSW",
            "command": "python data/download.py --unsw",
            "hint": "~20 s · official train/test CSVs, MD5 checked",
        },
        "download_cic": {
            "label": "Download / verify CIC",
            "command": "python data/download.py --cic",
            "hint": "MD5 check + unzip (zip may already be present)",
        },
        "clean": {
            "label": "Clean full data",
            "command": "python data/clean.py",
            "hint": "~50 s · needs ~9 GB free memory",
        },
        "full": {
            "label": "Full runs (main.py --scope full)",
            "command": "python main.py --scope full",
            "hint": "~25–30 min · 36 runs on cleaned full data",
        },
        "full_resume": {
            "label": "Full runs (resume)",
            "command": "python main.py --scope full --resume",
            "hint": "Skip finished runs; rebuild summary + gap table",
        },
        "analysis_full": {
            "label": "Analysis (full)",
            "command": "python -m src.analysis --scope full",
            "hint": "Tables + figures from saved full runs",
        },
        "demo_cic_time": {
            "label": "Quick demo: CIC time logreg",
            "command": "python main.py --scope full --datasets cic --splits time --models logreg --seeds 0",
            "hint": "~1.5 min · one full-data CIC time-split logistic regression",
        },
    }
    MIME = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }


class CommandRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.run_id = 0
        self.status = "idle"
        self.command = ""
        self.exit_code = None
        self.started_at = None
        self.finished_at = None
        self.events = queue.Queue()
        self.history = []

    def start(self, command):
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return {"ok": False, "error": "A command is already running. Stop it first."}
            if not Settings.SAFE_CMD.match(command.strip()):
                return {"ok": False, "error": (
                    "Command rejected. Use a documented project command that starts "
                    "with python / python3 and runs a .py file or -m module under the repo.")}
            self.run_id += 1
            run_id = self.run_id
            self.status = "running"
            self.command = command
            self.exit_code = None
            self.started_at = time.time()
            self.finished_at = None
            self.events = queue.Queue()
            self.history = []
            try:
                self.proc = self.launch(command)
            except OSError as exc:
                self.status = "error"
                self.exit_code = -1
                self.finished_at = time.time()
                return {"ok": False, "error": str(exc)}
            self.emit({"type": "start", "run_id": run_id, "command": command})
            threading.Thread(target=self.pump, args=(self.proc.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self.pump, args=(self.proc.stderr, "stderr"), daemon=True).start()
            threading.Thread(target=self.wait, args=(run_id,), daemon=True).start()
            return {"ok": True, "run_id": run_id, "command": command}

    @staticmethod
    def launch(command):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        argv = command.strip().split()
        if argv and argv[0] in ("python", "python3"):
            argv[0] = sys.executable
        return subprocess.Popen(argv, cwd=str(Settings.REPO_ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
                                start_new_session=True)

    def pump(self, pipe, stream):
        try:
            for line in iter(pipe.readline, ""):
                self.emit({"type": "line", "stream": stream, "text": line.rstrip("\n")})
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def wait(self, run_id):
        code = self.proc.wait()
        time.sleep(0.05)
        with self.lock:
            if run_id != self.run_id:
                return
            self.exit_code = code
            self.finished_at = time.time()
            if self.status == "killed":
                final = "killed"
            elif code == 0:
                self.status = "finished"
                final = "finished"
            else:
                self.status = "error"
                final = "error"
            self.proc = None
        self.emit({"type": "done", "run_id": run_id, "status": final, "exit_code": code})
        self.events.put(None)

    def emit(self, event):
        event["ts"] = time.time()
        self.history.append(event)
        event["id"] = len(self.history)
        if len(self.history) > 4000:
            self.history = self.history[-2000:]
        self.events.put(event)

    def stop(self):
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                return {"ok": False, "error": "No running command."}
            self.status = "killed"
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            return {"ok": True, "run_id": self.run_id}

    def snapshot(self):
        with self.lock:
            return {"run_id": self.run_id, "status": self.status, "command": self.command,
                    "exit_code": self.exit_code, "started_at": self.started_at,
                    "finished_at": self.finished_at}


class FileReader:
    @staticmethod
    def csv_rows(path):
        if not path.is_file():
            return []
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def json_file(path):
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def number(value):
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def whole(cls, value):
        f = cls.number(value)
        return int(f) if f is not None else None


class ResultFiles(FileReader):
    GAP_NUMBERS = ["auroc", "auroc_sd", "auprc", "auprc_sd", "recall_at_1pct_fpr", "recall_sd",
                   "test_fpr", "gap_auroc", "gap_auprc", "gap_recall_at_1pct_fpr"]
    SUMMARY_NUMBERS = ["seed", "auroc", "auprc", "attack_prevalence_test", "threshold", "target_fpr",
                       "recall_at_1pct_fpr", "test_fpr_at_threshold", "val_fpr_at_threshold",
                       "val_auroc", "fit_seconds", "score_seconds"]
    SPLIT_RUNS = {
        "cic_time": "cic__time__logreg__seed0.json",
        "cic_random": "cic__random__logreg__seed0.json",
        "unsw_predefined": "unsw__predefined__logreg__seed0.json",
        "unsw_random": "unsw__random__logreg__seed0.json",
    }

    def __init__(self, scope):
        self.scope = scope if scope in ("full", "sample") else "full"
        self.folder = Settings.REPO_ROOT / "results" / self.scope

    def gap_table(self):
        rows = []
        for row in self.csv_rows(self.folder / "gap_table.csv"):
            item = {"dataset": row.get("dataset"), "model": row.get("model"),
                    "split": row.get("split"), "n_seeds": self.whole(row.get("n_seeds"))}
            for key in self.GAP_NUMBERS:
                item[key] = self.number(row.get(key))
            rows.append(item)
        return rows

    def main_table(self):
        return [{"dataset": row.get("dataset"), "split": row.get("split"), "model": row.get("model"),
                 "auroc": self.number(row.get("auroc")),
                 "recall_at_1pct_fpr": self.number(row.get("recall_at_1pct_fpr")),
                 "test_fpr": self.number(row.get("test_fpr")), "runs": self.whole(row.get("runs"))}
                for row in self.csv_rows(self.folder / "analysis" / "main_table.csv")]

    def family_recall(self):
        rows = []
        for row in self.csv_rows(self.folder / "analysis" / "time_split_family_recall.csv"):
            item = {"family": row.get("family")}
            for key, value in row.items():
                if key != "family":
                    item[key] = self.number(value)
            rows.append(item)
        return rows

    def per_family(self):
        return [{"dataset": row.get("dataset"), "model": row.get("model"), "split": row.get("split"),
                 "family": row.get("family"), "recall": self.number(row.get("recall")),
                 "n": self.number(row.get("n"))}
                for row in self.csv_rows(self.folder / "per_family_recall.csv")]

    def summary(self):
        rows = []
        for row in self.csv_rows(self.folder / "summary.csv"):
            cleaned = dict(row)
            for key in self.SUMMARY_NUMBERS:
                if key in cleaned:
                    cleaned[key] = self.number(cleaned[key])
            rows.append(cleaned)
        return rows

    def split_sizes(self):
        out = {}
        for key, name in self.SPLIT_RUNS.items():
            path = self.folder / "runs" / name
            data = self.json_file(path)
            if data is None:
                continue
            summary = data.get("split_summary") or {}
            out[key] = {
                "source": str(path.relative_to(Settings.REPO_ROOT)),
                "name": summary.get("name"),
                "dataset": summary.get("dataset"),
                "n_features": summary.get("n_features"),
                "train": summary.get("train"),
                "val": summary.get("val"),
                "test": summary.get("test"),
                "days": summary.get("days"),
                "families_unseen_in_train": summary.get("families_unseen_in_train"),
                "val_rows_removed_overlap_with_train": summary.get("val_rows_removed_overlap_with_train"),
                "test_rows_removed_overlap_with_train": summary.get("test_rows_removed_overlap_with_train"),
            }
        return out

    def payload(self):
        return {
            "scope": self.scope,
            "generated_at": time.time(),
            "gap_table": self.gap_table(),
            "main_table": self.main_table(),
            "time_split_family_recall": self.family_recall(),
            "per_family_recall": self.per_family(),
            "summary": self.summary(),
            "runtime": self.json_file(self.folder / "runtime.json"),
            "split_sizes": self.split_sizes(),
            "figures": {
                "recall_by_split": f"/api/figure/{self.scope}/recall_by_split.png",
                "time_split_families": f"/api/figure/{self.scope}/time_split_families.png",
            },
        }


class DatasetFiles(FileReader):
    N = r"([\d,]+)"
    PATTERNS = {
        "rows_with_inf": (rf"converted\s+{N}\s+rows\s+containing\s+infinite\s+values\s+in\s+CIC-IDS2017"
                          rf"\s+\({N}\s+in\s+UNSW-NB15\)", 1, 2),
        "rows_dropped_exact_duplicates": (rf"removed\s+{N}\s+and\s+{N}\s+exact\s+duplicate\s+rows", 1, 2),
        "rows_dropped_label_conflicts": (rf"{N}\s+and\s+{N}\s+rows\s+whose\s+identical\s+features"
                                         rf"\s+carried\s+different\s+labels", 1, 2),
        "rows_raw": (rf"reducing\s+CIC-IDS2017\s+from\s+{N}\s+to\s+{N}\s+rows\s+and\s+UNSW-NB15"
                     rf"\s+from\s+{N}\s+to\s+{N}\s+rows", 1, 3),
        "rows_clean": (rf"reducing\s+CIC-IDS2017\s+from\s+{N}\s+to\s+{N}\s+rows\s+and\s+UNSW-NB15"
                       rf"\s+from\s+{N}\s+to\s+{N}\s+rows", 2, 4),
    }

    def clean_log(self, dataset):
        path = Settings.REPO_ROOT / "data" / "processed" / f"{dataset}_clean_log.json"
        log = self.json_file(path)
        if log is not None:
            log["source"] = str(path.relative_to(Settings.REPO_ROOT))
            return log
        return self.from_report().get(dataset)

    def from_report(self):
        path = Settings.REPO_ROOT / "report.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        cic = {"dataset": "cic", "source": "report.md"}
        unsw = {"dataset": "unsw", "source": "report.md"}
        for key, (pattern, cic_group, unsw_group) in self.PATTERNS.items():
            m = re.search(pattern, text)
            if m:
                cic[key] = self.to_int(m.group(cic_group))
                unsw[key] = self.to_int(m.group(unsw_group))
        return {"cic": cic, "unsw": unsw}

    @staticmethod
    def to_int(text):
        return int(text.replace(",", "").split()[0])

    def payload(self):
        return {
            "sample_info": self.json_file(Settings.REPO_ROOT / "data" / "sample" / "sample_info.json"),
            "cleaning": {"cic": self.clean_log("cic"), "unsw": self.clean_log("unsw")},
            "split_sizes_full": ResultFiles("full").split_sizes(),
        }


class ProjectInfo:
    TEAM = [
        {"name": "Arya Pravin Joshi", "role": [
            "Data download and MD5 checks",
            "Cleaning (duplicates, label conflicts, inf→NaN)",
            "Leakage controls",
            "Random, time, and UNSW official splits",
            "Metrics (AUROC, AUPRC, recall@1% FPR)",
            "Logistic regression baseline",
        ]},
        {"name": "Aditya More", "role": [
            "Random forest first results",
            "HistGradientBoosting first results",
            "Analysis tables and figures",
        ]},
    ]
    GOALS = [
        {"id": "data", "title": "Download and clean CIC-IDS2017 and UNSW-NB15", "status": "done", "owner": "Arya"},
        {"id": "leakage", "title": "Leakage checks (IDs/ports dropped, overlap removed, fit-on-train)",
         "status": "done", "owner": "Arya"},
        {"id": "splits", "title": "Random, CIC time, and UNSW predefined splits", "status": "done", "owner": "Arya"},
        {"id": "metrics", "title": "AUROC, AUPRC, recall at 1% FPR, per-family recall", "status": "done",
         "owner": "Arya"},
        {"id": "logreg", "title": "Logistic regression baseline on all four splits", "status": "done",
         "owner": "Arya"},
        {"id": "trees", "title": "Random forest and HGB first results (3 seeds)", "status": "done",
         "owner": "Aditya"},
        {"id": "analysis", "title": "Milestone tables and figures", "status": "done", "owner": "Aditya"},
    ]
    PLANNED = [
        "Leave-one-attack-family-out (LOFO) splits and runs",
        "Benign-only Isolation Forest",
        "Port-feature ablation",
        "Check on the corrected CIC-IDS2017 release",
        "Cross-dataset test (if time allows)",
        "Hybrid anomaly-score fallback for unsure predictions",
        "Error analysis of missed families",
        "Final report and fresh-clone test",
    ]

    @classmethod
    def payload(cls):
        return {
            "title": "How much does NIDS evaluation overestimate performance?",
            "course": "EAS 510 · Fall 2026 · Project 2",
            "team": cls.TEAM,
            "goals": cls.GOALS,
            "planned_for_final": cls.PLANNED,
            "presets": [{"id": key, **value} for key, value in Settings.PRESETS.items()],
        }


RUNNER = CommandRunner()


class Handler(BaseHTTPRequestHandler):
    server_version = "MilestoneDashboard/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code, payload):
        self.send(code, json.dumps(payload, indent=2).encode("utf-8"), "application/json; charset=utf-8")

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path in ("/", "/index.html"):
            return self.serve_file(Settings.STATIC_DIR / "index.html")
        if path.startswith("/static/"):
            return self.serve_file(Settings.STATIC_DIR / path[len("/static/"):])
        if path == "/api/meta":
            return self.send_json(200, ProjectInfo.payload())
        if path == "/api/datasets":
            return self.send_json(200, DatasetFiles().payload())
        if path == "/api/results":
            return self.send_json(200, ResultFiles((qs.get("scope") or ["full"])[0]).payload())
        if path == "/api/run/status":
            return self.send_json(200, RUNNER.snapshot())
        if path == "/api/run/stream":
            return self.stream_events()
        if path.startswith("/api/figure/"):
            return self.serve_figure(path)
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        data = self.read_json()
        if path == "/api/run":
            return self.start_command(data)
        if path == "/api/run/stop":
            return self.send_json(200, RUNNER.stop())
        self.send_json(404, {"error": "not found"})

    def start_command(self, data):
        preset = data.get("preset")
        command = data.get("command")
        if preset:
            if preset not in Settings.PRESETS:
                return self.send_json(400, {"ok": False, "error": "Unknown preset."})
            command = Settings.PRESETS[preset]["command"]
        if not command or not isinstance(command, str):
            return self.send_json(400, {"ok": False, "error": "Missing command."})
        result = RUNNER.start(command.strip())
        self.send_json(200 if result.get("ok") else 409, result)

    def serve_figure(self, path):
        parts = path.strip("/").split("/")
        if len(parts) == 4:
            scope, name = parts[2], parts[3]
            if scope in ("full", "sample") and name.endswith(".png"):
                return self.serve_file(Settings.REPO_ROOT / "results" / scope / "figures" / name)
        self.send_json(404, {"error": "figure not found"})

    @staticmethod
    def is_inside(path, folder):
        try:
            path.relative_to(folder.resolve())
            return True
        except ValueError:
            return False

    def serve_file(self, path):
        path = path.resolve()
        allowed = (self.is_inside(path, Settings.STATIC_DIR)
                   or self.is_inside(path, Settings.REPO_ROOT / "results"))
        if not allowed or not path.is_file():
            return self.send_json(404, {"error": "file not found"})
        self.send(200, path.read_bytes(), Settings.MIME.get(path.suffix.lower(), "application/octet-stream"))

    def stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_id = 0
        for event in list(RUNNER.history):
            self.write_event(event)
            last_id = max(last_id, int(event.get("id") or 0))
        snap = RUNNER.snapshot()
        if snap["status"] != "running":
            self.write_event({"type": "hello", "status": snap["status"]})
            return
        events = RUNNER.events
        while True:
            try:
                event = events.get(timeout=15.0)
            except queue.Empty:
                self.write_event({"type": "ping"})
                continue
            if event is None:
                break
            event_id = int(event.get("id") or 0)
            if event_id and event_id <= last_id:
                continue
            last_id = max(last_id, event_id)
            self.write_event(event)
            if event.get("type") == "done":
                break

    def write_event(self, event):
        try:
            self.wfile.write(("data: %s\n\n" % json.dumps(event)).encode("utf-8"))
            self.wfile.flush()
        except BrokenPipeError:
            pass


class DashboardServer:
    def __init__(self, open_browser=True):
        self.open_browser = open_browser
        self.url = "http://%s:%d/" % (Settings.HOST, Settings.PORT)

    def print_banner(self):
        print("Milestone dashboard")
        print("  serving  %s" % self.url)
        print("  repo     %s" % Settings.REPO_ROOT)
        print("  python   %s" % sys.executable)
        print("  bind     %s:%d (localhost only)" % (Settings.HOST, Settings.PORT))
        print("Press Ctrl+C to stop.\n")

    def run(self):
        os.chdir(Settings.REPO_ROOT)
        if not (Settings.STATIC_DIR / "index.html").is_file():
            print("Missing dashboard/static/index.html", file=sys.stderr)
            return 1
        httpd = ThreadingHTTPServer((Settings.HOST, Settings.PORT), Handler)
        self.print_banner()
        if self.open_browser:
            threading.Timer(0.6, lambda: webbrowser.open(self.url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            httpd.server_close()
            if RUNNER.proc is not None and RUNNER.proc.poll() is None:
                RUNNER.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(DashboardServer(open_browser="--no-browser" not in sys.argv).run())
