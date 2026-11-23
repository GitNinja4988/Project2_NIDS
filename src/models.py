import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from config import Experiment


class RowCounter(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        self.n_samples_seen_ = len(X)
        return self

    def transform(self, X):
        return X

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features, dtype=object)


class Preprocessor:
    @staticmethod
    def signed_log1p(x):
        return np.sign(x) * np.log1p(np.abs(x))

    @classmethod
    def build(cls, numeric_cols, categorical_cols, log_transform=Experiment.LOG_TRANSFORM, scale=True):
        steps = [("rows", RowCounter()), ("impute", SimpleImputer(strategy="median"))]
        if log_transform:
            steps.append(("log", FunctionTransformer(cls.signed_log1p, feature_names_out="one-to-one")))
        if scale:
            steps.append(("scale", StandardScaler()))
        parts = [("num", Pipeline(steps), list(numeric_cols))]
        if categorical_cols:
            parts.append(("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10,
                                               sparse_output=False), list(categorical_cols)))
        return ColumnTransformer(parts, remainder="drop", verbose_feature_names_out=False)


class SupervisedPipeline:
    def __init__(self, name, estimator, split, log_transform=True, scale=True):
        self.name = name
        prep = Preprocessor.build(split.numeric_cols, split.categorical_cols, log_transform, scale)
        self.pipe = Pipeline([("prep", prep), ("clf", estimator)])

    def fit(self, X, y, X_val=None, y_val=None):
        self.pipe.fit(X, y)
        return self

    def score(self, X):
        return self.pipe.predict_proba(X)[:, 1]

    def pipelines(self):
        return [self.pipe]

    def params(self):
        clf = self.pipe.named_steps["clf"]
        p = {k: v for k, v in clf.get_params().items()
             if isinstance(v, (int, float, str, bool, type(None)))}
        if hasattr(clf, "n_iter_"):
            p["n_iter"] = int(np.max(clf.n_iter_))
            p["converged"] = bool(np.max(clf.n_iter_) < clf.max_iter)
        return p


class ModelFactory:
    NAMES = ["logreg", "rf", "hgb"]

    @staticmethod
    def logreg(split, seed=0, **params):
        params = {**Experiment.MODEL_PARAMS["logreg"], **params}
        model = LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=2000,
                                   random_state=seed, **params)
        return SupervisedPipeline("logreg", model, split)

    @staticmethod
    def rf(split, seed=0, **params):
        params = {**Experiment.MODEL_PARAMS["rf"], **params}
        model = RandomForestClassifier(class_weight="balanced_subsample", n_jobs=Experiment.N_JOBS,
                                       random_state=seed, **params)
        return SupervisedPipeline("rf", model, split, log_transform=False, scale=False)

    @staticmethod
    def hgb(split, seed=0, **params):
        params = {**Experiment.MODEL_PARAMS["hgb"], **params}
        model = HistGradientBoostingClassifier(class_weight="balanced", max_iter=300,
                                               early_stopping=True, random_state=seed, **params)
        return SupervisedPipeline("hgb", model, split, log_transform=False, scale=False)

    @classmethod
    def build(cls, name, split, seed=0, **params):
        if name not in cls.NAMES:
            raise KeyError(f"unknown model {name!r}; choose from {cls.NAMES}")
        return getattr(cls, name)(split, seed=seed, **params)
