import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Cic, Columns, Paths, Unsw


class Cleaner:
    NAME = ""
    OUTPUT = None

    def __init__(self):
        self.log = {"dataset": self.NAME}

    @staticmethod
    def feature_columns(df):
        return [c for c in df.columns if c not in Columns.META]

    def replace_inf_with_nan(self, df):
        cols = df.select_dtypes(include=[np.number]).columns.difference(Columns.META)
        values = df[cols].to_numpy(dtype="float64")
        is_inf = np.isinf(values)
        self.log["cells_inf"] = int(is_inf.sum())
        self.log["rows_with_inf"] = int(is_inf.any(axis=1).sum())
        values[is_inf] = np.nan
        df[cols] = values
        is_nan = np.isnan(values)
        self.log["rows_with_nan_after_inf_replacement"] = int(is_nan.any(axis=1).sum())
        self.log["nan_by_column"] = {c: int(n) for c, n in zip(cols, is_nan.sum(axis=0)) if n}
        return df

    def remove_duplicates(self, df):
        features = self.feature_columns(df)
        n_before = len(df)
        df = df.drop_duplicates(subset=features + ["label"], keep="first")
        self.log["rows_dropped_exact_duplicates"] = n_before - len(df)
        conflict = df.duplicated(subset=features, keep=False)
        self.log["rows_dropped_label_conflicts"] = int(conflict.sum())
        self.log["label_conflicts_by_label"] = df.loc[conflict, "label"].value_counts().to_dict()
        return df[~conflict].copy()

    def save(self, df):
        path = self.OUTPUT
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        log_path = path.with_name(path.stem + "_log.json")
        log_path.write_text(json.dumps(self.log, indent=2, default=str))
        log = self.log
        print(f"wrote {path} ({len(df):,} rows)")
        print(f"  raw={log['rows_raw']:,}  duplicates={log['rows_dropped_exact_duplicates']:,}  "
              f"label conflicts={log['rows_dropped_label_conflicts']:,}  clean={log['rows_clean']:,}")


class CicCleaner(Cleaner):
    NAME = "CIC-IDS2017 MachineLearningCSV"
    OUTPUT = Paths.CIC_CLEAN

    @staticmethod
    def fix_label(label):
        label = str(label).strip()
        return re.sub(r"Web Attack\s*[^A-Za-z0-9]+\s*", "Web Attack - ", label)

    def read_files(self):
        parts = []
        self.log["rows_raw_by_file"] = {}
        for file_name, day in Cic.FILES:
            df = pd.read_csv(Paths.CIC_RAW / file_name, encoding="latin-1", low_memory=False)
            df.columns = df.columns.str.strip()
            df["source_file"] = file_name
            df["day"] = day
            df["row_in_file"] = np.arange(len(df), dtype=np.int64)
            self.log["rows_raw_by_file"][file_name] = len(df)
            parts.append(df)
        return pd.concat(parts, ignore_index=True)

    def fix_labels(self, df):
        df = df.rename(columns={"Label": "label"})
        df = df.dropna(subset=["label"])
        df = df.dropna(how="all", subset=self.feature_columns(df))
        self.log["rows_after_dropping_empty"] = len(df)
        df["label"] = df["label"].map(self.fix_label)
        unknown = set(df["label"]) - set(Cic.FAMILY)
        if unknown:
            raise ValueError(f"unknown CIC labels: {unknown}")
        return df

    def drop_duplicate_columns(self, df):
        for copy, original in Cic.DUPLICATE_COLUMNS.items():
            if copy in df.columns:
                identical = (df[copy].fillna(-1) == df[original].fillna(-1)).all()
                self.log[f"dropped_duplicate_column:{copy}"] = bool(identical)
                if identical:
                    df = df.drop(columns=copy)
        return df

    def check_days(self, df):
        for day, attacks in Cic.DAY_TO_ATTACKS.items():
            seen = set(df.loc[df["day"] == day, "label"]) - {"BENIGN"}
            if seen != set(attacks):
                self.log.setdefault("day_label_mismatch", {})[day] = sorted(seen ^ set(attacks))

    def run(self):
        df = self.read_files()
        self.log["rows_raw"] = len(df)
        df = self.fix_labels(df)
        df = self.drop_duplicate_columns(df)
        self.check_days(df)
        df = self.replace_inf_with_nan(df)
        self.log["label_counts_before_dedup"] = df["label"].value_counts().to_dict()
        df = self.remove_duplicates(df)
        df["family"] = df["label"].map(Cic.FAMILY)
        df["y"] = (df["family"] != "benign").astype(np.int8)
        df["part"] = "all"
        features = self.feature_columns(df)
        df[features] = df[features].astype("float32")
        self.log["rows_clean"] = len(df)
        self.log["label_counts_clean"] = df["label"].value_counts().to_dict()
        self.log["family_counts_clean"] = df["family"].value_counts().to_dict()
        self.log["rows_clean_by_day"] = df["day"].value_counts().reindex(Cic.DAY_ORDER).to_dict()
        self.save(df.reset_index(drop=True))


class UnswCleaner(Cleaner):
    NAME = "UNSW-NB15 official train/test partition"
    OUTPUT = Paths.UNSW_CLEAN

    def read_files(self):
        parts = []
        self.log["rows_raw_by_file"] = {}
        for file_name, part in Unsw.FILES:
            df = pd.read_csv(Paths.UNSW_RAW / file_name, low_memory=False)
            df.columns = df.columns.str.strip()
            df["part"] = part
            df["source_file"] = file_name
            df["row_in_file"] = np.arange(len(df), dtype=np.int64)
            self.log["rows_raw_by_file"][file_name] = len(df)
            parts.append(df)
        return pd.concat(parts, ignore_index=True)

    def fix_labels(self, df):
        df = df.drop(columns=[c for c in Columns.ID["unsw"] if c in df.columns])
        df["attack_cat"] = df["attack_cat"].fillna("Normal").astype(str).str.strip()
        df.loc[df["attack_cat"].isin(["", "-", "nan"]), "attack_cat"] = "Normal"
        unknown = set(df["attack_cat"]) - set(Unsw.FAMILY)
        if unknown:
            raise ValueError(f"unknown UNSW attack_cat values: {unknown}")
        df["family"] = df["attack_cat"].map(Unsw.FAMILY)
        consistent = (df["family"] == "benign") == (df["label"] == 0)
        self.log["rows_label_attack_cat_inconsistent_dropped"] = int((~consistent).sum())
        df = df[consistent]
        return df.drop(columns=["label"]).rename(columns={"attack_cat": "label"})

    def run(self):
        df = self.read_files()
        self.log["rows_raw"] = len(df)
        df = self.fix_labels(df)
        for col in Unsw.CATEGORICAL:
            df[col] = df[col].astype(str).str.strip().str.lower()
        df["day"] = "NA"
        df = self.replace_inf_with_nan(df)
        self.log["label_counts_before_dedup"] = df["label"].value_counts().to_dict()
        df = self.remove_duplicates(df)
        df["y"] = (df["family"] != "benign").astype(np.int8)
        numeric = [c for c in self.feature_columns(df) if c not in Unsw.CATEGORICAL]
        df[numeric] = df[numeric].astype("float32")
        self.log["rows_clean"] = len(df)
        self.log["rows_clean_by_part"] = df["part"].value_counts().to_dict()
        self.log["family_counts_clean"] = df["family"].value_counts().to_dict()
        self.save(df.reset_index(drop=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cic", action="store_true")
    parser.add_argument("--unsw", action="store_true")
    args = parser.parse_args()
    both = not (args.cic or args.unsw)
    if args.unsw or both:
        UnswCleaner().run()
    if args.cic or both:
        CicCleaner().run()
