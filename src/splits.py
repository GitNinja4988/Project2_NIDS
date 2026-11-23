from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import Cic, Columns, Experiment, Unsw


@dataclass
class Split:
    name: str
    dataset: str
    scope: str
    X_train: pd.DataFrame
    y_train: np.ndarray
    fam_train: np.ndarray
    X_val: pd.DataFrame
    y_val: np.ndarray
    fam_val: np.ndarray
    X_test: pd.DataFrame
    y_test: np.ndarray
    fam_test: np.ndarray
    numeric_cols: list
    categorical_cols: list
    seed: int = 0
    meta: dict = field(default_factory=dict)

    @staticmethod
    def describe(y, fam):
        return {"n": int(len(y)), "n_attack": int(np.sum(y)),
                "families": pd.Series(fam).value_counts().to_dict()}

    def summary(self):
        return {"name": self.name, "dataset": self.dataset, "scope": self.scope,
                "seed": self.seed,
                "n_features": len(self.numeric_cols) + len(self.categorical_cols),
                "train": self.describe(self.y_train, self.fam_train),
                "val": self.describe(self.y_val, self.fam_val),
                "test": self.describe(self.y_test, self.fam_test), **self.meta}


class SplitMaker:
    @staticmethod
    def feature_columns(df, dataset):
        dropped = set(Columns.META) | set(Columns.ID[dataset]) | set(Columns.PORT[dataset])
        categorical = [c for c in Unsw.CATEGORICAL if dataset == "unsw" and c in df.columns]
        numeric = [c for c in df.columns if c not in dropped and c not in categorical]
        return numeric, categorical

    @staticmethod
    def row_hashes(X):
        return pd.util.hash_pandas_object(X, index=False).to_numpy()

    @staticmethod
    def stratified_indices(groups, fractions, rng):
        parts = [[] for _ in fractions]
        cut_points = np.cumsum(fractions)
        all_positive = min(fractions) > 0
        for group in pd.unique(groups):
            idx = np.flatnonzero(groups == group)
            rng.shuffle(idx)
            n = len(idx)
            cuts = np.floor(cut_points * n + 1e-9).astype(int)
            cuts[-1] = n
            if n >= 3 and all_positive:
                cuts[0] = min(max(cuts[0], 1), n - 2)
                cuts[1] = min(max(cuts[1], cuts[0] + 1), n - 1)
            elif n == 2 and all_positive:
                cuts = np.array([1, 1, 2])
            start = 0
            for k, end in enumerate(cuts):
                parts[k].append(idx[start:end])
                start = end
        return [np.sort(np.concatenate(p)) if p else np.array([], int) for p in parts]

    def build(self, df, dataset, name, train_idx, val_idx, test_idx, seed,
              drop_overlap=True, meta=None):
        numeric, categorical = self.feature_columns(df, dataset)
        X = df[numeric + categorical]
        meta = dict(meta or {})
        if drop_overlap:
            hashes = self.row_hashes(X)
            in_train = np.isin(hashes, hashes[train_idx])
            meta["val_rows_removed_overlap_with_train"] = int(in_train[val_idx].sum())
            meta["test_rows_removed_overlap_with_train"] = int(in_train[test_idx].sum())
            val_idx = val_idx[~in_train[val_idx]]
            test_idx = test_idx[~in_train[test_idx]]
        y = df["y"].to_numpy().astype(int)
        fam = df["family"].to_numpy()

        def rows(idx):
            return X.iloc[idx].reset_index(drop=True), y[idx], fam[idx]

        X_tr, y_tr, f_tr = rows(train_idx)
        X_va, y_va, f_va = rows(val_idx)
        X_te, y_te, f_te = rows(test_idx)
        return Split(name, dataset, df.attrs.get("scope", "?"), X_tr, y_tr, f_tr,
                     X_va, y_va, f_va, X_te, y_te, f_te, numeric, categorical,
                     seed=seed, meta=meta)

    def random(self, df, seed=0, drop_overlap=True, fractions=Experiment.SPLIT_FRACTIONS):
        rng = np.random.Generator(np.random.PCG64(seed))
        train, val, test = self.stratified_indices(df["family"].to_numpy(), fractions, rng)
        return self.build(df, df.attrs["dataset"], "random", train, val, test, seed, drop_overlap)

    def time(self, df, seed=0, days=Cic.TIME_SPLIT, drop_overlap=True):
        dataset = df.attrs["dataset"]
        if dataset != "cic":
            raise ValueError("time split needs CIC-IDS2017 (the UNSW CSVs have no timestamps)")
        day = df["day"].to_numpy()
        train = np.flatnonzero(np.isin(day, days["train"]))
        val = np.flatnonzero(np.isin(day, days["val"]))
        test = np.flatnonzero(np.isin(day, days["test"]))
        order = {d: i for i, d in enumerate(Cic.DAY_ORDER)}
        meta = {"days": days,
                "days_present": {name: sorted(set(day[idx]), key=order.get)
                                 for name, idx in [("train", train), ("val", val), ("test", test)]},
                "families_unseen_in_train": sorted(set(df["family"].iloc[test])
                                                   - set(df["family"].iloc[train]))}
        return self.build(df, dataset, "time", train, val, test, seed, drop_overlap, meta=meta)

    def predefined(self, df, seed=0, val_frac=0.15, drop_overlap=True):
        if df.attrs["dataset"] != "unsw":
            raise ValueError("predefined split is only for UNSW-NB15")
        part = df["part"].to_numpy()
        train_all = np.flatnonzero(part == "train")
        test = np.flatnonzero(part == "test")
        rng = np.random.Generator(np.random.PCG64(seed))
        a, b, _ = self.stratified_indices(df["family"].to_numpy()[train_all],
                                          (1 - val_frac, val_frac, 0.0), rng)
        return self.build(df, "unsw", "predefined", train_all[a], train_all[b], test, seed,
                          drop_overlap)

    def by_name(self, split_name, df, dataset, seed):
        if split_name == "random":
            return self.random(df, seed)
        if split_name == "time" and dataset == "cic":
            return self.time(df, seed)
        if split_name == "predefined" and dataset == "unsw":
            return self.predefined(df, seed)
        return None


class LeakageChecker:
    def report(self, split, raise_on_fail=True):
        train_hashes = SplitMaker.row_hashes(split.X_train)
        columns = set(split.X_train.columns)
        report = {
            "train_test_overlap_rows": int(np.isin(SplitMaker.row_hashes(split.X_test), train_hashes).sum()),
            "train_val_overlap_rows": int(np.isin(SplitMaker.row_hashes(split.X_val), train_hashes).sum()),
            "id_columns_present": sorted(columns & set(sum(Columns.ID.values(), []))),
            "port_columns_present": sorted(columns & set(sum(Columns.PORT.values(), []))),
            "meta_columns_present": sorted(columns & set(Columns.META)),
        }
        if split.name == "time":
            report["time_order_ok"] = self.days_in_order(split.meta["days_present"])
        report["passed"] = bool(report["train_test_overlap_rows"] == 0
                                and report["train_val_overlap_rows"] == 0
                                and not report["id_columns_present"]
                                and not report["port_columns_present"]
                                and not report["meta_columns_present"]
                                and report.get("time_order_ok", True))
        if raise_on_fail and not report["passed"]:
            raise AssertionError(f"leakage check failed for {split.name}: {report}")
        return report

    @staticmethod
    def days_in_order(days):
        order = {d: i for i, d in enumerate(Cic.DAY_ORDER)}
        return bool(
            max(order[d] for d in days["train"]) < min(order[d] for d in days["val"])
            <= max(order[d] for d in days["val"]) < min(order[d] for d in days["test"]))
