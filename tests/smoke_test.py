import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.evaluate import Evaluator
from src.metrics import Metrics
from src.models import ModelFactory
from src.splits import LeakageChecker, SplitMaker


class SyntheticData:
    @staticmethod
    def cic(n=3000, seed=0):
        rng = np.random.default_rng(seed)
        attacks_by_day = {"Mon": ["benign"], "Tue": ["brute_force"], "Wed": ["dos"],
                          "Thu": ["web_attack"], "Fri": ["portscan", "ddos"]}
        shifts = {"benign": 0, "brute_force": 2, "dos": 3, "web_attack": 4, "portscan": 2, "ddos": 3}
        rows = []
        for day, families in attacks_by_day.items():
            for i in range(n // 5):
                family = "benign" if rng.random() < 0.7 else rng.choice(families)
                shift = shifts[family]
                rows.append({"Flow Duration": rng.exponential(1e5) * (1 + shift),
                             "Total Fwd Packets": rng.poisson(5 + shift),
                             "Flow Bytes/s": rng.lognormal(5 + shift / 2, 1),
                             "Destination Port": rng.choice([80, 443, 22]),
                             "label": family, "family": family, "y": int(family != "benign"),
                             "day": day, "part": "all", "source_file": "SYNTHETIC",
                             "row_in_file": i})
        df = pd.DataFrame(rows)
        df.loc[df.sample(20, random_state=seed).index, "Flow Bytes/s"] = np.nan
        df.attrs.update(dataset="cic", scope="synthetic")
        return df

    @staticmethod
    def unsw(n=1000, seed=0):
        rng = np.random.default_rng(seed)
        shifts = {"benign": 0, "exploits": 2, "dos": 3}
        rows = []
        for i in range(n):
            family = "benign" if rng.random() < 0.6 else rng.choice(["exploits", "dos"])
            shift = shifts[family]
            rows.append({"dur": rng.exponential(1.0) * (1 + shift), "spkts": rng.poisson(4 + shift),
                         "sport": rng.integers(1, 65535), "proto": rng.choice(["tcp", "udp"]),
                         "service": "-", "state": "FIN", "label": family, "family": family,
                         "y": int(family != "benign"), "day": "", "part": "train" if i < 0.7 * n else "test",
                         "source_file": "SYNTHETIC", "row_in_file": i})
        df = pd.DataFrame(rows)
        df.attrs.update(dataset="unsw", scope="synthetic")
        return df


class SmokeTest:
    def __init__(self):
        maker = SplitMaker()
        cic = SyntheticData.cic()
        self.splits = [maker.random(cic, 0), maker.time(cic), maker.predefined(SyntheticData.unsw(), 0)]

    @staticmethod
    def check_threshold():
        y_val = np.r_[np.zeros(1000), np.ones(10)]
        scores_val = np.r_[np.arange(1000), np.full(10, 2000)]
        t = Metrics.threshold_at_fpr(y_val, scores_val)
        assert np.mean(scores_val[y_val == 0] > t) <= 0.01

    def check_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            for split in self.splits:
                report = LeakageChecker().report(split)
                assert report["passed"] and not report["port_columns_present"]
                for name in ModelFactory.NAMES:
                    model = ModelFactory.build(name, split, seed=0)
                    r = Evaluator().run(model, split, results_dir=Path(tmp))
                    assert r["preprocessing_check"]["fit_on_train_only"]
                    print(f"[SYNTHETIC] {split.dataset:4s} {split.name:10s} {name:7s} "
                          f"AUROC={r['auroc']:.3f} R@1%={r['recall_at_1pct_fpr']:.3f}")
            assert (Path(tmp) / "summary.csv").exists()

    def check_time_order(self):
        assert set(self.splits[1].meta["days_present"]["test"]) == {"Fri"}

    def run(self):
        self.check_threshold()
        self.check_models()
        self.check_time_order()
        print("SYNTHETIC smoke test passed")


if __name__ == "__main__":
    SmokeTest().run()
