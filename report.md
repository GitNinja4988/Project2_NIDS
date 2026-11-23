# Generalization Gap in Machine-Learning Network Intrusion Detection: Interim Update

**Course:** EAS 510 Basics of AI, Fall 2026, Project 2  
**Authors:** Arya Pravin Joshi and Aditya More, University at Buffalo  
**Date:** November 23, 2026  
**Repository:** <https://github.com/GitNinja4988/Project2_NIDS>

*Status: interim version. This document will be replaced by the final report on December 7, 2026.*

## 1. Research Question and Scope

Published machine-learning intrusion detectors frequently report detection rates above 99% on CIC-IDS2017. These figures are usually obtained on a random train/test split, in which training and test flows are drawn from the same days and the same attack campaigns. This project quantifies how much measured performance declines when the evaluation more closely resembles deployment: testing on a later day that contains attack types absent from training (CIC-IDS2017), and testing on the authors' official held-out file (UNSW-NB15). The task is binary flow classification (benign versus attack). The interim milestone covers data acquisition and cleaning, the evaluation splits, leakage safeguards, the metrics, a logistic regression baseline and two tree-ensemble comparison models.

## 2. Data

**Sources.** CIC-IDS2017 is published by the Canadian Institute for Cybersecurity, University of New Brunswick (<https://www.unb.ca/cic/datasets/ids-2017.html>); the project uses `MachineLearningCSV.zip` (MD5 `4f83860afbf29cac8163854095bf6cf7`). UNSW-NB15 is published by the UNSW Canberra Cyber Range Lab (<https://research.unsw.edu.au/projects/unsw-nb15-dataset>); the project uses `UNSW_NB15_training-set.csv` and `UNSW_NB15_testing-set.csv`. Both datasets are available for academic research with citation and were retrieved in November 2026. `data/download.py` downloads the files and verifies every MD5 checksum.

**Unit of observation, features and target.** In CIC-IDS2017 one observation is a bidirectional network flow described by 78 flow statistics, recorded Monday to Friday (3–7 July 2017) with different attacks on different days; it has 14 attack labels, grouped into 8 families. In UNSW-NB15 one observation is a connection record with 42 features and 9 attack categories, and no timestamps. The target is binary (benign = 0, attack = 1); the attack family is retained for per-family evaluation. IP addresses, flow identifiers, timestamps and port numbers are removed so that models cannot rely on host-identity shortcuts. After this step the models use 76 features on CIC-IDS2017 and 42 on UNSW-NB15.

**Cleaning.** `data/clean.py` converts infinite values to missing values (imputed later with the training median), removes exact duplicate rows, and removes rows whose identical feature vectors carry conflicting labels.

| Step | CIC-IDS2017 | UNSW-NB15 |
|---|---:|---:|
| Raw rows | 2,830,743 | 257,673 |
| Rows with ±infinity (set to NaN, rows kept) | 2,867 | 0 |
| Exact duplicate rows removed (same features and label) | 308,381 | 94,928 |
| Rows removed because identical features had different labels | 1,396 | 11,506 |
| Clean rows | **2,520,966** | **151,239** |

**Bundled sample.** `data/sample/` contains 40,000 CIC-IDS2017 flows and 10,000 UNSW-NB15 records, produced by `data/make_sample.py` with a fixed seed (42). Sampling is stratified by day and label, and every row of the rare labels is retained (CIC-IDS2017: Bot, Web Attack Brute Force, XSS, SQL Injection, Infiltration, Heartbleed; UNSW-NB15: Shellcode, Analysis, Backdoor, Worms), so that every split and attack family can be evaluated. Because rare labels are over-represented, sample AUPRC and recall are not comparable with full-data values. Per-label counts are listed in `data/sample/SAMPLE_README.md`.

## 3. Methodology

**Splits.**

- *Random* (both datasets): 70/15/15 train/validation/test, stratified by attack family. This reproduces the common evaluation practice and serves as the reference for both stricter splits.
- *Time* (CIC-IDS2017): training on Monday–Wednesday (1,527,133 flows), validation on Thursday (365,731) and testing on Friday (565,133). Botnet, DDoS and port-scan traffic never appears in training.
- *Official* (UNSW-NB15): the authors' training file, with 15% held out (stratified) for validation, evaluated on the authors' testing file.

**Models.** Logistic regression is the baseline: it is a simple, interpretable linear reference (class-weighted; signed-log transform and standardization). Random forest (class-weighted, no scaling) is the comparison most frequently reported in intrusion-detection studies, which makes the results comparable with prior work. HistGradientBoosting (class-weighted, no scaling) is a strong and efficient model for large tabular data. Including both a weak and two strong models tests whether any performance decline is attributable to the evaluation rather than to model capacity.

**Preprocessing and leakage safeguards.** All preprocessing (median imputation, signed-log transform, standardization, one-hot encoding of the UNSW-NB15 `proto`, `service` and `state` columns) is part of a scikit-learn pipeline fit on training rows only. Duplicates are removed before splitting. Because removing identifier columns creates additional identical rows, each split also removes validation and test rows that are identical to a training row (on the CIC-IDS2017 time split: 32,379 validation and 30,590 test rows). `LeakageChecker` in `src/splits.py` stops the run if any train/validation or train/test overlap remains.

**Metrics and threshold selection.** The metrics are AUROC, AUPRC and recall at a 1% false positive rate (higher is better for all three). The alert threshold is set on the validation set so that 1% of benign validation flows raise an alert and is applied unchanged to the test set; the resulting test false positive rate is reported alongside recall, as is recall per attack family. Recall at 1% FPR is the primary metric because a security operations team can investigate only a limited number of false alarms.

**Seeds.** Every configuration is run with seeds 0, 1 and 2, defined in `config.py`, and results are reported as the mean over seeds.

## 4. Progress

The interim target (data loaded, an initial pipeline working and a preliminary baseline evaluated) has been met. All 36 full-data runs (2 datasets × 2 splits × 3 models × 3 seeds) are complete.

| Component | Evidence in repository | Owner |
|---|---|---|
| Data download with MD5 verification | `data/download.py`, `config.py` | Arya Pravin Joshi |
| Cleaning and row-count log | `data/clean.py` | Arya Pravin Joshi |
| Bundled stratified sample | `data/make_sample.py`, `data/sample/` | Arya Pravin Joshi |
| Random, time and official splits; leakage checks | `src/splits.py`, `src/data_io.py` | Arya Pravin Joshi |
| Metrics and threshold selection | `src/metrics.py` | Arya Pravin Joshi |
| Logistic regression baseline | `src/models.py` | Arya Pravin Joshi |
| Random forest and HistGradientBoosting | `src/models.py` | Aditya More |
| Evaluation and single entry point (`python main.py`, `--full`) | `src/evaluate.py`, `main.py` | Arya Pravin Joshi |
| Synthetic-data smoke test | `tests/smoke_test.py` | Arya Pravin Joshi |
| Result tables and figures | `src/analysis.py`, `results/sample/`, `results/full/` | Aditya More |
| Local results dashboard | `dashboard/` | Both |

## 5. Preliminary Results

*Preliminary findings.* Evaluation conditions: full cleaned data; random, time (CIC-IDS2017) and official (UNSW-NB15) splits as defined in Section 3; threshold set at 1% FPR on validation; mean over seeds 0, 1 and 2. Table entries are recall at 1% FPR with AUROC in parentheses (higher is better). Source: [`results/full/analysis/main_table.csv`](results/full/analysis/main_table.csv) and [`results/full/gap_table.csv`](results/full/gap_table.csv).

| Split | Logistic Regression (baseline) | Random Forest | HistGradientBoosting |
|---|---:|---:|---:|
| CIC-IDS2017 random | 0.894 (0.994) | 1.000 (1.000) | 1.000 (1.000) |
| CIC-IDS2017 time (test = Friday) | 0.373 (0.831) | 0.382 (0.909) | 0.381 (0.922) |
| UNSW-NB15 random | 0.492 (0.960) | 0.757 (0.981) | 0.754 (0.980) |
| UNSW-NB15 official | 0.558 (0.930) | 0.777 (0.964) | 0.807 (0.968) |

![Bar chart of recall at 1% FPR for logistic regression, random forest and HistGradientBoosting on the random and stricter split of each dataset, full data](results/full/figures/recall_by_split.png)

*Figure 1. Recall at 1% FPR for each model on the random and stricter split of each dataset (full data).*

![Bar chart of recall at 1% FPR per Friday attack family (botnet, DDoS, port scan) for each model on the CIC-IDS2017 time split, full data](results/full/figures/time_split_families.png)

*Figure 2. Recall at 1% FPR per Friday attack family on the CIC-IDS2017 time split (full data).*

1. On CIC-IDS2017 the tree ensembles are nearly perfect on the random split (recall 1.000) but reach only about 0.38 on the Friday test. The test false positive rate also rises from the 1% target to 1.7–2.8%.
2. All three models converge to similar recall on the time split (0.373–0.382), which indicates that the decline is a property of the evaluation rather than of a particular model.
3. Per family on Friday, all models detect 63–64% of DDoS, 1–2% of port-scan and 0% of botnet flows; the missed attacks are those absent from training.
4. On UNSW-NB15 the official split does not reduce recall (it is higher than on the random split for every model), but AUROC decreases for every model and the validation threshold yields a 2.5–4.5% false positive rate on the official test file instead of 1%.
5. The bundled sample reproduces the same pattern at a smaller scale (random forest recall at 1% FPR: 0.991 on the CIC-IDS2017 random split, 0.232 on the time split; [`results/sample/gap_table.csv`](results/sample/gap_table.csv)). The sample run verifies the pipeline; conclusions rest on the full-data runs.

## 6. Challenges and Mitigations

| Challenge | Action taken | Status |
|---|---|---|
| The official CIC-IDS2017 download now requires a registration form. | A public copy was used; the official file was later obtained through the form and its MD5 checksum matched. | Resolved |
| Removing identifier columns (e.g. ports) made some validation and test rows identical to training rows. | Per-split overlap removal and a leakage check that stops the run if any overlap remains. | Resolved |
| Cleaning the full CIC-IDS2017 data needs about 9 GB of free memory; the 36 full runs take about 25–30 minutes on a laptop CPU. | Runs are saved individually and `--resume` continues an interrupted full run. | Resolved |
| On UNSW-NB15 the validation threshold does not transfer to the official test file (test FPR 2.5–4.5%). | The test FPR is reported next to every recall value. | To be analysed in the final report |
| Redistribution terms for the bundled sample must be confirmed before the repository is made public. | Repository kept private; the instructor has been invited. | Open |

## 7. Plan for Completion

| Priority | Task | Owner |
|---|---|---|
| 1 | Leave-one-attack-family-out splits on both datasets | Aditya More |
| 1 | Benign-only Isolation Forest as an anomaly-detection comparison | Aditya More |
| 1 | Final report (2,500–3,500 words), README and fresh-clone test | Both |
| 2 | Port-feature ablation and a check against the corrected CIC-IDS2017 release (Engelen et al. [3]) | Arya Pravin Joshi |
| 2 | Error analysis of the missed port-scan and botnet traffic | Both |
| 2 | Small validation-only tuning grid for each model | Aditya More |
| 3 | Fallback to an anomaly score when the supervised model is uncertain | Aditya More |
| 3 | Cross-dataset test between CIC-IDS2017 and UNSW-NB15 on shared features | Aditya More |

*Scope note.* The research question and datasets are unchanged from the proposal. The cross-dataset test is optional and will be dropped if time does not permit; priority-1 items will be completed first.

## 8. Individual Contributions

- **Arya Pravin Joshi:** data download and MD5 verification, cleaning, bundled sample, random/time/official splits, leakage controls, metrics, logistic regression baseline, `main.py`, smoke test, dashboard server.
- **Aditya More:** random forest and HistGradientBoosting experiments, analysis tables and figures, dashboard result charts.

## References

1. I. Sharafaldin, A. H. Lashkari, and A. A. Ghorbani, "Toward generating a new intrusion detection dataset and intrusion traffic characterization," in *Proc. 4th Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2018, pp. 108–116.
2. N. Moustafa and J. Slay, "UNSW-NB15: A comprehensive data set for network intrusion detection systems (UNSW-NB15 network data set)," in *Proc. Military Communications and Information Systems Conf. (MilCIS)*, 2015, pp. 1–6.
3. G. Engelen, V. Rimmer, and W. Joosen, "Troubleshooting an intrusion detection dataset: the CICIDS2017 case study," in *Proc. IEEE Security and Privacy Workshops (SPW)*, 2021, pp. 7–12.
4. F. Pedregosa et al., "Scikit-learn: Machine learning in Python," *J. Mach. Learn. Res.*, vol. 12, pp. 2825–2830, 2011.
