# Project2_NIDS: How Much Does NIDS Evaluation Overestimate Performance?

EAS 510 (Basics of AI), Fall 2026, Project 2. **Arya Pravin Joshi and Aditya More.**
Milestone (interim) version, November 23, 2026.

We measure the generalization gap of flow-based network intrusion detectors: the same model is scored
on a random train/test split and on a stricter split (CIC-IDS2017: train Monday to Wednesday, test
Friday; UNSW-NB15: the authors' official train/test files). Models: logistic regression (baseline),
random forest and HistGradientBoosting. Main metric: recall at 1% false positive rate, with the threshold
chosen on validation.

Report: [report.md](report.md)

## Results so far

Full data, recall at 1% FPR, mean of 3 seeds (higher is better). Source:
[results/full/gap_table.csv](results/full/gap_table.csv).

| Split | LogReg | Random forest | HistGradientBoosting |
|---|---:|---:|---:|
| CIC random | 0.894 | 1.000 | 1.000 |
| CIC time (test = Friday) | 0.373 | 0.382 | 0.381 |
| UNSW random | 0.492 | 0.757 | 0.754 |
| UNSW official split | 0.558 | 0.777 | 0.807 |

On CIC, detection falls from about 100% to about 38% when the test is a later day with unseen attack types.

## Environment

- Tested with Python 3.9.25 on Debian GNU/Linux 13 (x86-64, 8 CPU cores, 15 GB RAM) and Python 3.9.6 on
  macOS 27.2 (Apple M5 Pro), CPU only.
- Pinned packages in [requirements.txt](requirements.txt): numpy, pandas, scikit-learn, scipy, joblib,
  threadpoolctl, pyarrow, requests, matplotlib.
- No system packages, GPU, credentials or paid services are needed.

## Run the sample

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

`python main.py` runs 36 experiments (2 datasets x 2 splits x 3 models x 3 seeds) on the bundled sample in
`data/sample/`, with no network access. It prints one metrics line per run and the gap table, then writes:

- [results/sample/summary.csv](results/sample/summary.csv): every run's metrics
- [results/sample/gap_table.csv](results/sample/gap_table.csv): mean over seeds and the random-minus-strict gap
- [results/sample/per_family_recall.csv](results/sample/per_family_recall.csv): recall per attack family
- `results/sample/runs/*.json`: one file per run
- [results/sample/runtime.json](results/sample/runtime.json): arguments and run time

Tables and figures from the saved runs:

```bash
python -m src.analysis --scope sample
```

These go to `results/sample/analysis/` and `results/sample/figures/`.

Quick check on synthetic data: `python tests/smoke_test.py` (ends with `SYNTHETIC smoke test passed`).

### Expected sample output

Mean of 3 seeds, from [results/sample/gap_table.csv](results/sample/gap_table.csv):

| Dataset | Split | Model | AUROC | Recall at 1% FPR |
|---|---|---|---:|---:|
| cic | random | logreg | 0.973 | 0.578 |
| cic | random | rf | 0.999 | 0.991 |
| cic | random | hgb | 1.000 | 0.997 |
| cic | time | logreg | 0.724 | 0.227 |
| cic | time | rf | 0.709 | 0.232 |
| cic | time | hgb | 0.842 | 0.229 |
| unsw | random | logreg | 0.962 | 0.519 |
| unsw | random | rf | 0.976 | 0.656 |
| unsw | random | hgb | 0.975 | 0.701 |
| unsw | predefined | logreg | 0.920 | 0.619 |
| unsw | predefined | rf | 0.943 | 0.731 |
| unsw | predefined | hgb | 0.958 | 0.734 |

Tolerance: with the pinned packages on Linux, two runs gave identical metrics. On another OS, CPU or
library build, tree splits and solver steps can differ slightly, so we accept AUROC within ±0.01 and
recall at 1% FPR within ±0.05 of the table. The seed-to-seed standard deviation of recall is up to 0.14
(`recall_sd` in the gap table), so smaller differences do not change any conclusion.

Runtime and memory: about 26 seconds and 330 MB peak memory on the Linux machine above. No network access
is needed after installing the packages.

## Full data

```bash
python data/download.py --cic
python data/download.py --unsw
python data/clean.py
python main.py --full
python -m src.analysis --scope full
```

- `download.py` saves the raw files to `data/raw/` and checks their MD5. The CIC zip is about 235 MB and the
  two UNSW CSVs about 46 MB.
- `clean.py` writes `data/processed/*.parquet` in about a minute and needs about 9 GB of free memory.
- `main.py --full` (same as `--scope full`) runs the 36 experiments on the full data in about 25 to 30
  minutes on a laptop CPU. Add `--resume` to continue after a stop.
- Outputs go to [results/full/](results/full/). Raw and processed data are not committed.

## Data

- **CIC-IDS2017**, Canadian Institute for Cybersecurity, University of New Brunswick:
  <https://www.unb.ca/cic/datasets/ids-2017.html>. File `MachineLearningCSV.zip`, MD5
  `4f83860afbf29cac8163854095bf6cf7`. The official link needs a registration form, so `download.py` uses the
  Hugging Face copy `bencorn/CICIDS2017`, which has the same MD5.
- **UNSW-NB15**, UNSW Canberra: <https://research.unsw.edu.au/projects/unsw-nb15-dataset>. Files
  `UNSW_NB15_training-set.csv` and `UNSW_NB15_testing-set.csv` from the "Training and Testing Sets" folder,
  with a Hugging Face copy (`Mireu-Lab/UNSW-NB15`) as backup.
- Both datasets are free for academic research with citation. Retrieved November 2026.
- One row is one network flow. Rows after cleaning: CIC 2,830,743 to 2,520,966; UNSW 257,673 to 151,239.
- **Sample**: 40,000 CIC flows and 10,000 UNSW records, made by `data/make_sample.py` (seed 42), stratified by
  day and label, with every row of the rare labels kept. Counts per label are in
  [data/sample/SAMPLE_README.md](data/sample/SAMPLE_README.md). Rare labels are over-represented, so sample
  numbers are not comparable with full-data numbers.

## Dashboard

```bash
python dashboard/server.py
```

Opens <http://127.0.0.1:8765/> (localhost only). It shows the milestone goals, the datasets, charts from
`results/` and a panel that runs the commands above with live output.

## Layout

```
README.md  report.md  main.py  config.py  requirements.txt  .gitignore
src/        data loading, splits, metrics, models, evaluation, analysis
data/       download.py, clean.py, make_sample.py, sample/
results/    sample/ and full/
tests/      smoke_test.py
dashboard/  server.py, static/
```
