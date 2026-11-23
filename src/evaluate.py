import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from config import Paths
from src.metrics import Metrics
from src.splits import LeakageChecker


class ResultStore:
    @staticmethod
    def run_path(out_dir, dataset, split_name, model_name, seed):
        return Path(out_dir) / "runs" / f"{dataset}__{split_name}__{model_name}__seed{seed}.json"

    @staticmethod
    def summary_row(result):
        row = {k: v for k, v in result.items() if not isinstance(v, dict)}
        for family, d in result["per_family_recall"].items():
            row[f"recall[{family}]"] = d["recall"]
        return row

    @classmethod
    def save(cls, result, results_dir=None):
        if results_dir is None:
            results_dir = Paths.results(result["scope"])
        path = cls.run_path(results_dir, result["dataset"], result["split"], result["model"], result["seed"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, default=float))
        summary_path = Path(results_dir) / "summary.csv"
        table = pd.DataFrame([cls.summary_row(result)])
        if summary_path.exists():
            table = pd.concat([pd.read_csv(summary_path), table], ignore_index=True)
        table.to_csv(summary_path, index=False)


class Evaluator:
    @staticmethod
    def check_fit_on_train(model, split):
        seen = []
        for pipe in model.pipelines():
            prep = pipe.named_steps["prep"]
            for _, transformer, _ in prep.transformers_:
                steps = getattr(transformer, "named_steps", {"only": transformer})
                for step in steps.values():
                    if hasattr(step, "n_samples_seen_"):
                        seen.append(int(np.max(step.n_samples_seen_)))
        ok = len(seen) > 0 and all(n == len(split.X_train) for n in seen)
        return {"preprocessing_rows_seen": seen, "train_rows": len(split.X_train), "fit_on_train_only": ok}

    def run(self, model, split, seed=None, results_dir=None, save=True):
        seed = split.seed if seed is None else seed
        leakage = LeakageChecker().report(split)

        start = time.perf_counter()
        model.fit(split.X_train, split.y_train, X_val=split.X_val, y_val=split.y_val)
        fit_seconds = time.perf_counter() - start
        start = time.perf_counter()
        scores_val = model.score(split.X_val)
        scores_test = model.score(split.X_test)
        score_seconds = time.perf_counter() - start

        threshold = Metrics.threshold_at_fpr(split.y_val, scores_val)
        m = Metrics.compute(split.y_test, scores_test, split.fam_test, threshold,
                            y_val=split.y_val, scores_val=scores_val)

        result = {"model": model.name, "split": split.name, "dataset": split.dataset,
                  "scope": split.scope, "seed": seed, **m,
                  "fit_seconds": round(fit_seconds, 3), "score_seconds": round(score_seconds, 3),
                  "leakage": leakage, "preprocessing_check": self.check_fit_on_train(model, split),
                  "model_params": model.params(), "split_summary": split.summary()}
        if not result["preprocessing_check"]["fit_on_train_only"]:
            raise AssertionError(f"preprocessing was not fit on train only: {result['preprocessing_check']}")
        if save:
            ResultStore.save(result, results_dir)
        return result


class GapTable:
    COLUMNS = ["dataset", "model", "split", "seed", "auroc", "auprc",
               "recall_at_1pct_fpr", "test_fpr_at_threshold"]

    @classmethod
    def build(cls, results, baseline_split="random"):
        df = pd.DataFrame([{c: r[c] for c in cls.COLUMNS} for r in results])
        table = df.groupby(["dataset", "model", "split"]).agg(
            n_seeds=("seed", "nunique"),
            auroc=("auroc", "mean"), auroc_sd=("auroc", "std"),
            auprc=("auprc", "mean"), auprc_sd=("auprc", "std"),
            recall_at_1pct_fpr=("recall_at_1pct_fpr", "mean"),
            recall_sd=("recall_at_1pct_fpr", "std"),
            test_fpr=("test_fpr_at_threshold", "mean")).reset_index()
        for metric in ["auroc", "auprc", "recall_at_1pct_fpr"]:
            base = table[table["split"] == baseline_split].set_index(["dataset", "model"])[metric]
            table[f"gap_{metric}"] = [base.get((d, m), np.nan) - v for d, m, v
                                      in zip(table["dataset"], table["model"], table[metric])]
        return table
