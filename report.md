# How Much Does NIDS Evaluation Overestimate Performance? (Interim Update)

**EAS 510, Fall 2026, Project 2.** Arya Pravin Joshi and Aditya More. Interim update, November 23, 2026.

This is the milestone version of the report. It covers the first half of the project. The final
report replaces it by December 7.

## 1. Question

Papers on machine-learning intrusion detection often report 99%+ detection on CIC-IDS2017, usually on
a random train/test split where training and test flows come from the same days and the same attacks.
We measure how much the score drops when the test is closer to real use: a later day with attack types
the model has not seen (CIC-IDS2017), or the authors' official train/test files (UNSW-NB15). The task is
binary flow classification (benign vs attack).

## 2. Data

| | CIC-IDS2017 | UNSW-NB15 |
|---|---|---|
| Source | Canadian Institute for Cybersecurity, University of New Brunswick, <https://www.unb.ca/cic/datasets/ids-2017.html>, file `MachineLearningCSV.zip` (MD5 `4f83860afbf29cac8163854095bf6cf7`) | UNSW Canberra Cyber Range Lab, <https://research.unsw.edu.au/projects/unsw-nb15-dataset>, files `UNSW_NB15_training-set.csv` and `UNSW_NB15_testing-set.csv` |
| One row | One bidirectional network flow, 78 flow features and a label | One network connection record, 42 features and a label |
| Recorded | Monday to Friday, 3 to 7 July 2017, different attacks on different days | 2015, official train and test files, no timestamps |
| Attack labels | 14 labels grouped into 8 families | 9 attack categories |
| Retrieved | November 2026 | November 2026 |

Both datasets are free for academic research with citation. `data/download.py` fetches them and checks
the MD5 of every file. The official CIC link now asks for a registration form, so the script uses a
Hugging Face copy (`bencorn/CICIDS2017`) whose MD5 matches the official file.

Cleaning (`data/clean.py`):

| Step | CIC-IDS2017 | UNSW-NB15 |
|---|---:|---:|
| Raw rows | 2,830,743 | 257,673 |
| Rows with ±infinity (set to NaN, rows kept) | 2,867 | 0 |
| Exact duplicate rows removed (same features and label) | 308,381 | 94,928 |
| Rows removed because identical features had different labels | 1,396 | 11,506 |
| Clean rows | **2,520,966** | **151,239** |

Infinite values become missing and are filled later with the training median. Detailed labels are
grouped into families (for example DoS, DDoS, botnet, port scan, web attack). IP addresses, flow IDs,
timestamps and ports are dropped so the models cannot learn identity shortcuts.

**Bundled sample.** `data/sample/` holds 40,000 CIC flows and 10,000 UNSW records, built by
`data/make_sample.py` with a fixed seed. Rows are stratified by day and label, and every row of the rare
labels is kept (CIC: Bot, Web Attack Brute Force, XSS, SQL Injection, Infiltration, Heartbleed; UNSW:
Shellcode, Analysis, Backdoor, Worms), so every split and family can be scored on the sample. Because rare
labels are over-represented, sample AUPRC and recall are not comparable with full-data numbers. The
per-label counts are in `data/sample/SAMPLE_README.md`.

## 3. Method

**Splits.**
- *Random*: 70/15/15 train/validation/test, stratified by family. This is the usual setup in papers.
- *Time* (CIC): train Monday to Wednesday (1,527,133 flows), validate Thursday (365,731), test Friday
  (565,133). Botnet, DDoS and port scan never appear in training.
- *Official* (UNSW): the authors' training file (15% held out for validation) against their testing file.

**Leakage controls.** Duplicates are removed before splitting. Dropping ports creates new duplicates, so
each split also removes validation and test rows identical to a training row (on the CIC time split:
32,379 validation and 30,590 test rows). All preprocessing sits inside the model pipeline and is fit on
training rows only. `LeakageChecker` stops the run if any overlap or fit-on-test is found.

**Models.**
- Logistic regression (baseline): class-weighted, signed-log transform and standardization.
- Random forest: class-weighted, no scaling. The most common model in intrusion-detection papers.
- HistGradientBoosting: class-weighted, no scaling. Strong and fast on large tables.

UNSW's text columns (protocol, service, state) are one-hot encoded. Every run uses seeds 0, 1 and 2,
set in `config.py`.

**Metrics.** AUROC, AUPRC and **recall at 1% false positive rate** (higher is better for all three). The
alert threshold is chosen on validation so that 1% of benign validation flows alert, then used unchanged
on test. We also report the test FPR at that threshold and recall per attack family. Recall at 1% FPR is
the main metric because a security team can only follow up a small number of false alarms.

## 4. Progress

Done and in the repository:
- Download with MD5 checks, cleaning and the bundled sample: `data/`
- Random, time and official splits with leakage checks: `src/splits.py`
- Metrics: `src/metrics.py`; models: `src/models.py`; evaluation: `src/evaluate.py`
- Single entry point `main.py`: 36 runs (2 datasets, 2 splits each, 3 models, 3 seeds)
- Tables and figures: `src/analysis.py`, saved in `results/sample/` and `results/full/`
- Smoke test on synthetic data: `tests/smoke_test.py`
- A local dashboard that shows the goals, datasets and result charts and runs the commands:
  `dashboard/server.py`

## 5. Current results (preliminary)

Full data, mean of 3 seeds, recall at 1% FPR with AUROC in brackets. Higher is better.
Source: [`results/full/analysis/main_table.csv`](results/full/analysis/main_table.csv) and
[`results/full/gap_table.csv`](results/full/gap_table.csv).

| Split | LogReg (baseline) | Random forest | HistGradientBoosting |
|---|---:|---:|---:|
| CIC random | 0.894 (0.994) | 1.000 (1.000) | 1.000 (1.000) |
| CIC time, test = Friday | 0.373 (0.831) | 0.382 (0.909) | 0.381 (0.922) |
| UNSW random | 0.492 (0.960) | 0.757 (0.981) | 0.754 (0.980) |
| UNSW official split | 0.558 (0.930) | 0.777 (0.964) | 0.807 (0.968) |

![Recall at 1% FPR for each model on the random and stricter split of each dataset, full data](results/full/figures/recall_by_split.png)

- On CIC the tree models catch almost every attack on a random split but only about 38% when tested on a
  later day. The test FPR also drifts from 1% to 1.7–2.8%. All three models end up close together, so the
  drop comes from the evaluation, not from one weak model.
- Per Friday family on the time split, all three models catch 63–64% of DDoS, 1–2% of port scans and 0% of
  botnet flows. The attack types not seen in training are the ones missed.

![Recall per Friday attack family on the CIC time split, full data](results/full/figures/time_split_families.png)

- On UNSW the official split does not lower recall, but AUROC falls a little for every model and the
  threshold chosen on validation gives a 2.5–4.5% FPR on the test file instead of 1%.

The sample run (`results/sample/`) shows the same pattern at a smaller scale (for example random forest
recall at 1% FPR 0.991 on the CIC random split and 0.232 on the time split). It checks that the pipeline
works; the conclusions rest on the full-data runs.

## 6. Challenges

- The official CIC-IDS2017 download now requires a registration form. We used a public copy and confirmed
  through the form that its MD5 is identical.
- Dropping ports made some validation and test rows identical to training rows. We added a per-split
  overlap removal and a check that stops the run if overlap remains.
- Cleaning the full CIC data needs about 9 GB of free memory, and the 36 full runs take about 25–30
  minutes on a laptop CPU. We added `--resume` so an interrupted full run continues where it stopped.
- On UNSW the validation threshold does not transfer well to the official test file (FPR 2.5–4.5%). We
  report the test FPR next to every recall value so this is visible.
- We still need to confirm that the dataset terms allow sharing the bundled sample before the repository
  is made public.

## 7. Plan for December 7

- Leave-one-attack-family-out splits on both datasets and a benign-only Isolation Forest (Aditya).
- Port-feature ablation and a check against the corrected CIC-IDS2017 release of Engelen et al. (Arya).
- Cross-dataset test between CIC and UNSW on shared features, if time allows (Aditya).
- Small validation-only tuning grid for every model (Aditya).
- A fallback to an anomaly score when the supervised model is unsure (Aditya).
- Error analysis of why port scans and botnet are missed on the time split (both).
- Final report (2,500–3,500 words), README and fresh-clone test (both).

## 8. Who did what

- **Arya Pravin Joshi:** data download and MD5 checks, cleaning, bundled sample, random/time/official
  splits, leakage controls, metrics, logistic regression baseline, `main.py`, smoke test, dashboard server.
- **Aditya More:** random forest and HistGradientBoosting runs, analysis tables and figures, dashboard
  result charts.

## References

- I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani. "Toward Generating a New Intrusion Detection Dataset and
  Intrusion Traffic Characterization." ICISSP, 2018.
- N. Moustafa, J. Slay. "UNSW-NB15: A comprehensive data set for network intrusion detection systems."
  MilCIS, 2015.
- G. Engelen, V. Rimmer, W. Joosen. "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case
  Study." IEEE Security and Privacy Workshops, 2021.
- F. Pedregosa et al. "Scikit-learn: Machine Learning in Python." JMLR 12, 2011.
