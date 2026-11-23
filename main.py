import os

for var in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ.setdefault(var, "1")

import argparse
import json
import time
import warnings

import pandas as pd

from config import Experiment, Paths
from src.data_io import DatasetLoader
from src.evaluate import Evaluator, GapTable, ResultStore
from src.models import ModelFactory
from src.splits import SplitMaker


class CommandLine:
    @staticmethod
    def parse():
        parser = argparse.ArgumentParser(description="NIDS generalization-gap experiments (milestone)")
        parser.add_argument("--scope", choices=["sample", "full"], default="sample")
        parser.add_argument("--full", action="store_true")
        parser.add_argument("--datasets", nargs="+", default=["cic", "unsw"], choices=["cic", "unsw"])
        parser.add_argument("--splits", nargs="+", default=["random", "time", "predefined"],
                            choices=["random", "time", "predefined"])
        parser.add_argument("--models", nargs="+", default=ModelFactory.NAMES,
                            choices=ModelFactory.NAMES)
        parser.add_argument("--seeds", nargs="+", type=int, default=Experiment.SEEDS)
        parser.add_argument("--resume", action="store_true",
                            help="reuse finished runs in results/<scope>/runs instead of running them again")
        args = parser.parse_args()
        if args.full:
            args.scope = "full"
        del args.full
        return args


class NewRun:
    def __init__(self, out_dir, resume):
        self.out_dir = out_dir
        self.resume = resume
        self.evaluator = Evaluator()

    def run(self, split, model_name, seed):
        saved = ResultStore.run_path(self.out_dir, split.dataset, split.name, model_name, seed)
        if self.resume and saved.exists():
            result = json.loads(saved.read_text())
        else:
            model = ModelFactory.build(model_name, split, seed=seed)
            result = self.evaluator.run(model, split, seed=seed)
        self.print_line(split, model_name, seed, result)
        return result

    @staticmethod
    def print_line(split, model_name, seed, r):
        print(f"[run] {split.dataset:5s} {split.name:10s} {model_name:7s} seed={seed} "
              f"AUROC={r['auroc']:.4f} AUPRC={r['auprc']:.4f} "
              f"R@1%FPR={r['recall_at_1pct_fpr']:.4f} testFPR={r['test_fpr_at_threshold']:.4f} "
              f"fit={r['fit_seconds']:.1f}s", flush=True)


class ResultTables:
    def __init__(self, out_dir):
        self.out_dir = out_dir

    def save_summary(self, results):
        rows = [ResultStore.summary_row(r) for r in results]
        pd.DataFrame(rows).to_csv(self.out_dir / "summary.csv", index=False)

    def save_gap_table(self, results):
        gaps = GapTable.build(results)
        pd.set_option("display.width", 200)
        pd.set_option("display.max_columns", 30)
        print("\n=== Generalization gap (mean over seeds; gap = random - protocol) ===")
        print(gaps.round(4).to_string(index=False))
        gaps.to_csv(self.out_dir / "gap_table.csv", index=False)

    def save_per_family(self, results):
        rows = [{"dataset": r["dataset"], "model": r["model"], "split": r["split"], "seed": r["seed"],
                 "family": family, "recall": d["recall"], "n": d["n"]}
                for r in results for family, d in r["per_family_recall"].items()]
        per_family = (pd.DataFrame(rows).groupby(["dataset", "model", "split", "family"])
                      .agg(recall=("recall", "mean"), n=("n", "mean")).reset_index())
        per_family.to_csv(self.out_dir / "per_family_recall.csv", index=False)

    def save_runtime(self, args, elapsed, n_runs):
        runtime = {"argv": vars(args), "elapsed_seconds": round(elapsed, 2), "n_runs": n_runs}
        (self.out_dir / "runtime.json").write_text(json.dumps(runtime, indent=2))


class Experiments:
    def __init__(self, args):
        self.args = args
        self.out_dir = Paths.results(args.scope)
        self.loader = DatasetLoader()
        self.splitter = SplitMaker()
        self.new_run = NewRun(self.out_dir, args.resume)
        self.tables = ResultTables(self.out_dir)

    def prepare_output(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        summary_path = self.out_dir / "summary.csv"
        if summary_path.exists():
            summary_path.unlink()

    def run_dataset(self, dataset):
        results = []
        df = self.loader.load(dataset, self.args.scope)
        print(f"[data] {dataset} ({self.args.scope}): {len(df):,} flows, attack share {df['y'].mean():.3f}")
        for split_name in self.args.splits:
            for seed in self.args.seeds:
                split = self.splitter.by_name(split_name, df, dataset, seed)
                if split is None:
                    continue
                for model_name in self.args.models:
                    results.append(self.new_run.run(split, model_name, seed))
        return results

    def run(self):
        start = time.perf_counter()
        warnings.filterwarnings("ignore", category=UserWarning)
        self.prepare_output()
        results = []
        for dataset in self.args.datasets:
            results += self.run_dataset(dataset)
        self.tables.save_summary(results)
        self.tables.save_gap_table(results)
        self.tables.save_per_family(results)
        elapsed = time.perf_counter() - start
        self.tables.save_runtime(self.args, elapsed, len(results))
        print(f"\nSaved to {self.out_dir}. Total runtime: {elapsed:.1f} s for {len(results)} runs.")


if __name__ == "__main__":
    Experiments(CommandLine.parse()).run()
