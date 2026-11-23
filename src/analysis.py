import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import Paths


class AnalysisTables:
    MODEL_ORDER = ["logreg", "rf", "hgb"]

    def __init__(self, out_dir):
        self.runs = [json.loads(p.read_text()) for p in sorted((out_dir / "runs").glob("*.json"))]

    def main_table(self):
        df = pd.DataFrame([{k: r[k] for k in ["dataset", "split", "model", "seed", "auroc",
                                              "recall_at_1pct_fpr", "test_fpr_at_threshold"]}
                           for r in self.runs])
        return (df.groupby(["dataset", "split", "model"])
                .agg(auroc=("auroc", "mean"), recall_at_1pct_fpr=("recall_at_1pct_fpr", "mean"),
                     test_fpr=("test_fpr_at_threshold", "mean"), runs=("seed", "count"))
                .reset_index())

    def time_split_family_recall(self):
        rows = [{"family": f, "model": r["model"], "recall": d["recall"]}
                for r in self.runs if r["dataset"] == "cic" and r["split"] == "time"
                for f, d in r["per_family_recall"].items()]
        return (pd.DataFrame(rows).groupby(["family", "model"])["recall"].mean()
                .unstack().reindex(columns=self.MODEL_ORDER))


class AnalysisFigures:
    MODEL_ORDER = AnalysisTables.MODEL_ORDER
    PANELS = [("cic", ["random", "time"]), ("unsw", ["random", "predefined"])]

    def recall_by_split(self, table, path):
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
        x = np.arange(len(self.MODEL_ORDER))
        for ax, (dataset, splits) in zip(axes, self.PANELS):
            for i, split in enumerate(splits):
                part = table[(table["dataset"] == dataset) & (table["split"] == split)]
                values = part.set_index("model").reindex(self.MODEL_ORDER)["recall_at_1pct_fpr"]
                ax.bar(x + (i - 0.5) * 0.4, values, 0.4, label=split)
            ax.set_xticks(x, self.MODEL_ORDER)
            ax.set_ylim(0, 1.2)
            ax.set_yticks(np.linspace(0, 1, 6))
            ax.set_title(dataset.upper())
            ax.legend(loc="upper right", ncol=2)
        axes[0].set_ylabel("recall at 1% FPR")
        fig.suptitle("Recall at 1% FPR: random split vs stricter split (mean over seeds)")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

    def time_split_families(self, values, path):
        fig, ax = plt.subplots(figsize=(5.5, 0.5 * len(values) + 1.5))
        im = ax.imshow(values.to_numpy(), vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(values.shape[1]), values.columns)
        ax.set_yticks(range(values.shape[0]), values.index)
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                v = values.iat[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        color="white" if v < 0.6 else "black", fontsize=8)
        ax.set_title("CIC time split: recall per Friday family")
        fig.colorbar(im, ax=ax, label="recall")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)


class Analysis:
    def __init__(self, scope):
        out_dir = Paths.results(scope)
        self.tables_dir = out_dir / "analysis"
        self.figures_dir = out_dir / "figures"
        self.tables = AnalysisTables(out_dir)
        self.figures = AnalysisFigures()

    def run(self):
        self.tables_dir.mkdir(exist_ok=True)
        self.figures_dir.mkdir(exist_ok=True)
        table = self.tables.main_table()
        table.to_csv(self.tables_dir / "main_table.csv", index=False)
        families = self.tables.time_split_family_recall()
        families.to_csv(self.tables_dir / "time_split_family_recall.csv")
        self.figures.recall_by_split(table, self.figures_dir / "recall_by_split.png")
        self.figures.time_split_families(families, self.figures_dir / "time_split_families.png")
        print(table.round(3).to_string(index=False))
        print("wrote", self.tables_dir, "and", self.figures_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["sample", "full"], default="sample")
    Analysis(parser.parse_args().scope).run()
