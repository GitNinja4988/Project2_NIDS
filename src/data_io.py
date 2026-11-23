import pandas as pd

from config import Paths, Unsw


class DatasetLoader:
    TEXT_COLUMNS = ["label", "family", "day", "part", "source_file"]

    def load(self, dataset, scope="sample"):
        if dataset not in ("cic", "unsw"):
            raise ValueError(dataset)
        if scope == "full":
            df = self.read_full(dataset)
        elif scope == "sample":
            df = self.read_sample(dataset)
        else:
            raise ValueError(scope)
        df.attrs["dataset"] = dataset
        df.attrs["scope"] = scope
        return df.reset_index(drop=True)

    def read_full(self, dataset):
        path = Paths.clean(dataset)
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run data/download.py then data/clean.py")
        return pd.read_parquet(path)

    def read_sample(self, dataset):
        text_cols = list(self.TEXT_COLUMNS)
        if dataset == "unsw":
            text_cols += Unsw.CATEGORICAL
        df = pd.read_csv(Paths.sample(dataset), dtype={c: str for c in text_cols})
        numeric = df.columns.difference(text_cols + ["y", "row_in_file"])
        df[numeric] = df[numeric].astype("float32")
        return df
