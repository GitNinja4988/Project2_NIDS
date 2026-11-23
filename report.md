# Generalization Gap in Machine-Learning Network Intrusion Detection: Interim Update

**Arya Pravin Joshi and Aditya More**, University at Buffalo  
EAS 510 Basics of AI, Fall 2026, Project 2 · November 23, 2026  
Repository: <https://github.com/GitNinja4988/Project2_NIDS>

*Interim milestone update. This document will be replaced by the final report on December 7, 2026.*

## 1. Research Question and Scope

Published machine-learning intrusion detectors frequently report detection rates above 99% on the CIC-IDS2017 benchmark. Most of these figures come from a random train/test split, in which training and test flows are drawn from the same days and the same attack campaigns, so the test set contains little that the model has not already seen. This project measures how much of that performance remains when the evaluation resembles deployment: a model trained on earlier traffic is tested on a later day that contains attack types absent from training (CIC-IDS2017), or on the authors' official held-out file (UNSW-NB15). The task is the binary classification of network flows as benign or attack. This interim report covers only the milestone work, namely data preparation, the evaluation splits, leakage safeguards, the metrics, a logistic regression baseline and two tree-ensemble comparison models.

## 2. Data

CIC-IDS2017, published by the Canadian Institute for Cybersecurity [1], was recorded over five working days in July 2017, with different attacks on different days. Each observation is a bidirectional network flow described by 78 statistics, such as duration, packet counts and byte rates. UNSW-NB15, published by UNSW Canberra [2], is used through its official training and testing files; each observation is a connection record with 42 features. In both datasets the target is binary (benign or attack), and the attack family is retained so that recall can be computed per family. The files are downloaded by `data/download.py` and verified against their MD5 checksums.

Cleaning (`data/clean.py`) converted 2,867 rows containing infinite values in CIC-IDS2017 (0 in UNSW-NB15) to missing values, then removed 308,381 and 94,928 exact duplicate rows and 1,396 and 11,506 rows whose identical features carried different labels, reducing CIC-IDS2017 from 2,830,743 to 2,520,966 rows and UNSW-NB15 from 257,673 to 151,239 rows. IP addresses, flow identifiers, timestamps and ports are removed because they identify hosts rather than behaviour and would allow a model to memorise the attacker. A stratified sample of 40,000 CIC-IDS2017 and 10,000 UNSW-NB15 rows, which keeps every row of the rare labels, is bundled in `data/sample/` so that the complete pipeline can be run without downloading the data; because rare labels are over-represented, its scores are not comparable with full-data scores.

## 3. Methodology

Each dataset is evaluated under two splits. The random split (70% training, 15% validation and 15% testing, stratified by attack family) reproduces common practice and serves as the reference. The stricter split for CIC-IDS2017 is chronological: models are trained on Monday to Wednesday, validated on Thursday and tested on Friday, so botnet, DDoS and port-scan traffic is never seen during training. For UNSW-NB15 the stricter split is the authors' own partition, with 15% of the training file held out for validation. Logistic regression is the baseline because it is simple, interpretable and widely used as a reference; random forest is the comparison most often reported in intrusion-detection studies, and HistGradientBoosting is a strong and efficient learner for large tabular data. All three models are class-weighted, and every configuration is run with seeds 0, 1 and 2.

To prevent leakage, all preprocessing (median imputation, a signed-log transform and standardisation for logistic regression, and one-hot encoding of the categorical UNSW-NB15 columns) is fitted on training rows only. Because removing identifiers creates further identical rows, validation and test rows identical to a training row are removed, and a leakage check stops any run in which overlap remains. The primary metric is recall at a 1% false positive rate (FPR): the alert threshold is chosen on the validation set so that 1% of benign flows raise an alert, and it is then applied unchanged to the test set. This reflects the limited number of false alarms that a security team can investigate. AUROC, AUPRC, the realised test FPR and recall per attack family are also reported.

## 4. Progress

The milestone target of loaded data, a working initial pipeline and an evaluated preliminary baseline has been met. Both datasets are downloaded, verified and cleaned (`data/`); the splits and leakage checks are implemented in `src/splits.py`, the metrics in `src/metrics.py`, the three models in `src/models.py` and the evaluation in `src/evaluate.py`. A single entry point, `main.py`, runs all 36 configurations (two datasets, two splits, three models and three seeds) on the bundled sample in under a minute, and on the complete data with `--full`; all 36 full-data runs have been completed. Tables and figures are generated by `src/analysis.py` and stored in `results/`, a synthetic-data smoke test is provided in `tests/smoke_test.py`, and a local dashboard (`dashboard/`) displays the results and runs the commands.

## 5. Preliminary Results

Table 1 reports preliminary results on the full cleaned data, averaged over three seeds, using recall at 1% FPR with AUROC in parentheses; higher values are better for both. The underlying files are [`results/full/analysis/main_table.csv`](results/full/analysis/main_table.csv) and [`results/full/gap_table.csv`](results/full/gap_table.csv).

**Table 1.** Recall at 1% FPR (AUROC), full data, mean of three seeds.

| Split | Logistic Regression (baseline) | Random Forest | HistGradientBoosting |
|---|---:|---:|---:|
| CIC-IDS2017 random | 0.894 (0.994) | 1.000 (1.000) | 1.000 (1.000) |
| CIC-IDS2017 time (test = Friday) | 0.373 (0.831) | 0.382 (0.909) | 0.381 (0.922) |
| UNSW-NB15 random | 0.492 (0.960) | 0.757 (0.981) | 0.754 (0.980) |
| UNSW-NB15 official | 0.558 (0.930) | 0.777 (0.964) | 0.807 (0.968) |

On CIC-IDS2017 the tree ensembles detect virtually every attack under the random split (recall 1.000) but only about 38% under the chronological split, and the realised test FPR rises from 1% to 1.7–2.8%. The three models converge to similar recall on the Friday test (0.373–0.382), which indicates that the decline is caused by the evaluation rather than by a weak model. Per family, all models detect 63–64% of DDoS flows, 1–2% of port scans and none of the botnet traffic, so the attacks that are missed are those absent from training (Figures 1 and 2). On UNSW-NB15 the official split does not reduce recall, which is higher than under the random split for every model, but AUROC decreases and the validation threshold produces a test FPR of 2.5–4.5% instead of 1%. The bundled sample shows the same pattern at a smaller scale (random forest recall of 0.991 on the random split and 0.232 on the time split); it verifies the pipeline, while the conclusions rest on the full data.

![Bar chart of recall at 1% FPR for logistic regression, random forest and HistGradientBoosting on the random and stricter split of each dataset, full data](results/full/figures/recall_by_split.png)

*Figure 1. Recall at 1% FPR for each model on the random and stricter split of each dataset (full data).*

![Bar chart of recall at 1% FPR per Friday attack family (botnet, DDoS, port scan) for each model on the CIC-IDS2017 time split, full data](results/full/figures/time_split_families.png)

*Figure 2. Recall at 1% FPR per Friday attack family on the CIC-IDS2017 time split (full data).*

## 6. Challenges

Several practical obstacles arose during the milestone. The official CIC-IDS2017 download now requires a registration form, so a public copy was used initially; the official file was later obtained through the form and its MD5 checksum matched. Removing the port columns made some validation and test rows identical to training rows, which was addressed by the per-split overlap removal and the leakage check described above. Cleaning the full CIC-IDS2017 data requires about 9 GB of free memory and the 36 full runs take roughly 25–30 minutes on a laptop CPU, so every run is saved individually and an interrupted job can be continued with `--resume`. Two issues remain open: the UNSW-NB15 validation threshold does not transfer to the official test file, which is currently made visible by reporting the test FPR next to every recall value, and the redistribution terms for the bundled sample must be confirmed before the repository is made public.

## 7. Plan for Completion

The following work is planned for the final report and is not yet implemented. The highest priority is a leave-one-attack-family-out evaluation on both datasets together with a benign-only Isolation Forest, which will test whether an anomaly detector generalises better to unseen attack families (Aditya More), followed by the final report, README and a fresh-clone test (both authors). The second priority comprises a port-feature ablation and a check against the corrected CIC-IDS2017 release of Engelen et al. [3] (Arya Pravin Joshi), an error analysis of the missed port-scan and botnet traffic (both authors), and a small validation-only tuning grid (Aditya More). An anomaly-score fallback for uncertain predictions and a cross-dataset test have the lowest priority, and the cross-dataset test will be dropped if time does not permit. The research question and datasets are unchanged from the proposal.

## 8. Individual Contributions

Arya Pravin Joshi was responsible for data acquisition and cleaning, the bundled sample, the three splits and leakage controls, the metrics, the logistic regression baseline, `main.py`, the smoke test and the dashboard server. Aditya More was responsible for the random forest and HistGradientBoosting experiments, the analysis tables and figures, and the dashboard result charts.

## References

[1] I. Sharafaldin, A. H. Lashkari, and A. A. Ghorbani, "Toward generating a new intrusion detection dataset and intrusion traffic characterization," in *Proc. 4th Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2018, pp. 108–116.  
[2] N. Moustafa and J. Slay, "UNSW-NB15: A comprehensive data set for network intrusion detection systems (UNSW-NB15 network data set)," in *Proc. Military Communications and Information Systems Conf. (MilCIS)*, 2015, pp. 1–6.  
[3] G. Engelen, V. Rimmer, and W. Joosen, "Troubleshooting an intrusion detection dataset: the CICIDS2017 case study," in *Proc. IEEE Security and Privacy Workshops (SPW)*, 2021, pp. 7–12.
