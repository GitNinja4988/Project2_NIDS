# Generalization Gap in Machine-Learning Network Intrusion Detection: Interim Update

**Arya Pravin Joshi and Aditya More**, University at Buffalo  
EAS 510 Basics of AI, Fall 2026, Project 2  
November 23, 2026  
Repository: <https://github.com/GitNinja4988/Project2_NIDS>

## 1 Research Question, Data and Method

### 1.1 Research Question

Usually, published machine-learning intrusion detectors can achieve detection rates better than 99% on CIC-IDS2017 under a random train/test split that shares days as well as attack campaigns. This project measures how much of that performance remains under deployment-like evaluation: testing on a later day containing attack types absent from training (CIC-IDS2017 [1]) or on the authors' official held-out file (UNSW-NB15 [2]). The task is a binary classification problem of network flows: benign or attack.

### 1.2 Data

Each observation is a network flow (78 features in CIC-IDS2017, 42 in UNSW-NB15). Duplicate rows (308,381 in CIC-IDS2017 and 94,928 in UNSW-NB15) and label-conflicting rows (1,396 and 11,506) were removed by cleaning, reducing CIC-IDS2017 from 2,830,743 to 2,520,966 rows and UNSW-NB15 from 257,673 to 151,239 rows. IP addresses, flow identifiers, timestamps and ports were removed so that models cannot memorise hosts.

### 1.3 Splits

Each dataset is tested when divided in a random way (70/15/15, with stratification by attack family) and under a stricter division. For CIC-IDS2017, the training takes place on Monday–Wednesday, the validation on Thursday and the testing on Friday; the botnet, DDoS and port-scan traffic appears only on Friday, so it is never observed during training. For UNSW-NB15, the stricter division is the authors' official partition: their training file, with 15% held out for validation, is tested on their testing file.

### 1.4 Models

The interpretable baseline is logistic regression. The comparisons are with the most commonly reported model in this field, random forest, and the strong tabular learner HistGradientBoosting.

### 1.5 Leakage Safeguards and Metrics

Only training rows are used to fit the preprocessing; validation and test rows that are the same as training rows are deleted; and a leakage check stops any run if there is residual overlap. The main measure is recall at a 1% false positive rate (FPR) because analysts can investigate only a limited number of alarms. The threshold is set on benign validation flows, and AUROC and test FPR are also shown. Seeds 0, 1 and 2 are used.

## 2 Progress

### 2.1 Data Pipeline

The milestone goal of loaded data, a working pipeline and an evaluated baseline has been attained. Both datasets are downloaded, verified against their MD5 checksums and cleaned (`data/`). A stratified 50,000-row sample (40,000 CIC-IDS2017 and 10,000 UNSW-NB15 rows) is bundled in `data/sample/`.

### 2.2 Experiments and Code

The splits and leakage checks (`src/splits.py`), metrics (`src/metrics.py`), models (`src/models.py`) and evaluation (`src/evaluate.py`) are implemented, and all 36 configurations (two datasets, two splits, three models, three seeds) are run by the single entry point `main.py`, on the sample in under a minute or on the full data with `--full`. All 36 full-data runs are finished; tables and figures are created by `src/analysis.py` in `results/`, and a smoke test and a local dashboard are included.

## 3 Current Results (Preliminary)

### 3.1 Main Results

**Table 1.** Recall at 1% FPR (AUROC in parentheses); full data, mean of three seeds; higher is better.

| Split | Logistic Regression (baseline) | Random Forest | HistGradientBoosting |
|---|---:|---:|---:|
| CIC-IDS2017 random | 0.894 (0.994) | 1.000 (1.000) | 1.000 (1.000) |
| CIC-IDS2017 time (test = Friday) | 0.373 (0.831) | 0.382 (0.909) | 0.381 (0.922) |
| UNSW-NB15 random | 0.492 (0.960) | 0.757 (0.981) | 0.754 (0.980) |
| UNSW-NB15 official | 0.558 (0.930) | 0.777 (0.964) | 0.807 (0.968) |

The tree ensembles are able to identify almost all attacks under the random split, while they are able to identify only about 38% under the chronological split. The realised test FPR increases from 1% to 1.7–2.8% under the time split. All three models agree at similar levels of recall on Friday (0.373–0.382), which means that the drop is not due to a weak model, but rather due to the evaluation. Source: [`results/full/analysis/main_table.csv`](results/full/analysis/main_table.csv).

![Bar chart of recall at 1% FPR for logistic regression, random forest and HistGradientBoosting on the random and stricter split of each dataset, full data](results/full/figures/recall_by_split.png)

*Figure 1. Recall at 1% FPR for each model on the random and stricter split of each dataset (full data).*

### 3.2 Per-Family Analysis

The models are able to detect 63–64% of DDoS flows per family. Port-scan and botnet traffic are largely missed: only 1–2% of the port scans and none of the botnet flows are detected. Like DDoS, these families are absent from the training set, meaning that the attacks missed are those not present in training.

![Bar chart of recall at 1% FPR per Friday attack family (botnet, DDoS, port scan) for each model on the CIC-IDS2017 time split, full data](results/full/figures/time_split_families.png)

*Figure 2. Recall at 1% FPR per Friday attack family on the CIC-IDS2017 time split (full data).*

### 3.3 UNSW-NB15

On UNSW-NB15 the official split does not reduce recall, which is in fact higher than under the random split for every model, but AUROC is lowered and the validation threshold results in a test FPR of 2.5–4.5% instead of 1%.

## 4 Challenges

### 4.1 Resolved

The official CIC-IDS2017 download now requires registration; a public copy was used and later confirmed to have the same MD5 checksum as the official file. Some test rows matched training rows as a result of removing the port columns, which was resolved by per-split overlap removal and a leakage check. Because full cleaning needs about 9 GB of memory and the full runs take 25–30 minutes, runs are saved individually and can be resumed.

### 4.2 Outstanding

Two outstanding issues remain: the UNSW-NB15 threshold does not transfer to the official test file (reported as test FPR), and the redistribution terms of the sample must be verified prior to the public release of the repository.

## 5 Plan for Completion

The following work is due on December 7 and has not yet been done.

### 5.1 First Priority

The primary consideration is a leave-one-attack-family-out evaluation on both datasets, together with a benign-only Isolation Forest to see whether it generalises to unseen families (Aditya More), followed by the results, the report and a fresh-clone test (both).

### 5.2 Second Priority

The second priority is a port-feature ablation and a check of the corrected CIC-IDS2017 release [3] (Arya Pravin Joshi), an error analysis of missed port-scan and botnet traffic (both) and validation-only tuning (Aditya More).

### 5.3 Lower Priority

The least important are the anomaly-score fallback and the cross-dataset test; the latter will be dropped if time does not allow.

## 6 Individual Contributions

### 6.1 Arya Pravin Joshi

Arya Pravin Joshi was involved with data acquisition and cleaning, the sample, splits and leakage controls, metrics, the logistic regression baseline, the smoke test, `main.py` and the dashboard server.

### 6.2 Aditya More

Aditya More was responsible for the random forest and HistGradientBoosting experiments, the analysis tables and figures, and the dashboard result charts.

## References

[1] I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization," *Proc. ICISSP*, 2018.  
[2] N. Moustafa, J. Slay, "UNSW-NB15: A comprehensive data set for network intrusion detection systems," *Proc. MilCIS*, 2015.  
[3] G. Engelen, V. Rimmer, W. Joosen, "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study," *Proc. IEEE SPW*, 2021.
