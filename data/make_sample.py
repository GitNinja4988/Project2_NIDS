import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Paths, Sampling


class SampleBuilder:
    JOBS = [("cic", Paths.CIC_CLEAN, Paths.CIC_SAMPLE, ["day", "label"]),
            ("unsw", Paths.UNSW_CLEAN, Paths.UNSW_SAMPLE, ["part", "label"])]

    def __init__(self, seed=Sampling.SEED):
        self.seed = seed
        self.infos = {}

    @staticmethod
    def allocate(group_sizes, budget, floor):
        sizes = group_sizes.astype(int)
        alloc = np.minimum(sizes, floor).astype(float)
        remaining = budget - alloc.sum()
        if remaining < 0:
            raise ValueError("budget is smaller than the floors; lower Sampling.MIN_PER_STRATUM")
        for _ in range(20):
            room = sizes - alloc
            has_room = room > 0
            if remaining <= 0 or not has_room.any():
                break
            share = remaining * sizes[has_room] / sizes[has_room].sum()
            alloc[has_room] += np.minimum(share, room[has_room])
            remaining = budget - alloc.sum()
        counts = np.floor(alloc).astype(int)
        leftover = int(budget - counts.sum())
        fractions = (alloc - counts).sort_values(ascending=False)
        for group in fractions.index[:leftover]:
            counts[group] += 1
        return counts.clip(upper=sizes)

    def stratified_sample(self, df, group_cols, size):
        rng = np.random.Generator(np.random.PCG64(self.seed))
        label_counts = df["label"].value_counts()
        rare_labels = label_counts[label_counts <= Sampling.RARE_CLASS_MAX].index.tolist()
        is_rare = df["label"].isin(rare_labels)
        others = df[~is_rare]
        group_sizes = others.groupby(group_cols, sort=True).size()
        counts = self.allocate(group_sizes, size - int(is_rare.sum()), Sampling.MIN_PER_STRATUM)
        keep = [df.index[is_rare].to_numpy()]
        for group, rows in others.groupby(group_cols, sort=True).groups.items():
            keep.append(rng.choice(np.asarray(rows), size=int(counts[group]), replace=False))
        sample = df.loc[np.sort(np.concatenate(keep))]
        info = {"seed": self.seed, "target_size": size, "actual_size": len(sample),
                "strata": group_cols, "rare_labels_kept_in_full": rare_labels,
                "rare_rows": int(is_rare.sum()),
                "per_label_full": label_counts.to_dict(),
                "per_label_sample": sample["label"].value_counts().to_dict()}
        return sample, info

    def write_readme(self):
        lines = ["# Bundled sample", "",
                 "Built by `data/make_sample.py` from the cleaned data. See report.md",
                 "for how rows are picked. Sample AUPRC is not comparable with",
                 "full-data AUPRC because rare labels are kept in full.", ""]
        for name, info in self.infos.items():
            lines += [f"## {name}: {info['actual_size']:,} flows ({info['file']})", "",
                      "| label | full (clean) | sample |", "|---|---:|---:|"]
            for label, n in info["per_label_full"].items():
                lines.append(f"| {label} | {n:,} | {info['per_label_sample'].get(label, 0):,} |")
            lines.append("")
        lines.append("Both datasets are free for academic research with citation. Check the "
                     "redistribution terms before pushing this sample to a public repo.")
        (Paths.SAMPLE / "SAMPLE_README.md").write_text("\n".join(lines) + "\n")

    def run(self):
        Paths.SAMPLE.mkdir(parents=True, exist_ok=True)
        for name, source, target, group_cols in self.JOBS:
            df = pd.read_parquet(source)
            sample, info = self.stratified_sample(df, group_cols, Sampling.SIZE[name])
            sample.to_csv(target, index=False,
                          compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
            info["file"] = str(target.relative_to(Paths.ROOT))
            info["bytes"] = target.stat().st_size
            self.infos[name] = info
            print(f"{name}: {len(sample):,} rows -> {target}")
        (Paths.SAMPLE / "sample_info.json").write_text(json.dumps(self.infos, indent=2))
        self.write_readme()


if __name__ == "__main__":
    SampleBuilder().run()
