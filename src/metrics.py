import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from config import Experiment


class Metrics:
    @staticmethod
    def threshold_at_fpr(y_val, scores_val, fpr=Experiment.TARGET_FPR):
        benign = np.sort(np.asarray(scores_val, dtype=float)[np.asarray(y_val) == 0])
        if benign.size == 0:
            raise ValueError("validation set has no benign flows")
        allowed_above = int(np.floor(fpr * benign.size))
        return float(benign[benign.size - 1 - allowed_above])

    @staticmethod
    def recall_at_threshold(y, scores, threshold):
        attacks = np.asarray(y) == 1
        if not attacks.any():
            return float("nan")
        return float(np.mean(np.asarray(scores)[attacks] > threshold))

    @staticmethod
    def fpr_at_threshold(y, scores, threshold):
        benign = np.asarray(y) == 0
        if not benign.any():
            return float("nan")
        return float(np.mean(np.asarray(scores)[benign] > threshold))

    @staticmethod
    def per_family_recall(families, scores, threshold):
        families, scores = np.asarray(families), np.asarray(scores)
        result = {}
        for family in sorted(set(families) - {"benign"}):
            rows = families == family
            result[family] = {"recall": float(np.mean(scores[rows] > threshold)), "n": int(rows.sum())}
        return result

    @staticmethod
    def auroc(y, scores):
        return float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else float("nan")

    @staticmethod
    def auprc(y, scores):
        return float(average_precision_score(y, scores)) if len(np.unique(y)) == 2 else float("nan")

    @classmethod
    def compute(cls, y_test, scores_test, fam_test, threshold, y_val=None, scores_val=None):
        y_test = np.asarray(y_test)
        scores_test = np.asarray(scores_test, dtype=float)
        m = {
            "auroc": cls.auroc(y_test, scores_test),
            "auprc": cls.auprc(y_test, scores_test),
            "attack_prevalence_test": float(np.mean(y_test)),
            "threshold": float(threshold),
            "target_fpr": Experiment.TARGET_FPR,
            "recall_at_1pct_fpr": cls.recall_at_threshold(y_test, scores_test, threshold),
            "test_fpr_at_threshold": cls.fpr_at_threshold(y_test, scores_test, threshold),
            "per_family_recall": cls.per_family_recall(fam_test, scores_test, threshold),
        }
        if y_val is not None:
            m["val_fpr_at_threshold"] = cls.fpr_at_threshold(y_val, scores_val, threshold)
            m["val_auroc"] = cls.auroc(y_val, scores_val)
        return m
