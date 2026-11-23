from pathlib import Path


class Paths:
    ROOT = Path(__file__).resolve().parent
    RAW = ROOT / "data" / "raw"
    PROCESSED = ROOT / "data" / "processed"
    SAMPLE = ROOT / "data" / "sample"
    RESULTS_SAMPLE = ROOT / "results" / "sample"
    RESULTS_FULL = ROOT / "results" / "full"
    CIC_RAW = RAW / "cic-ids2017"
    UNSW_RAW = RAW / "unsw-nb15"
    CIC_CLEAN = PROCESSED / "cic_clean.parquet"
    UNSW_CLEAN = PROCESSED / "unsw_clean.parquet"
    CIC_SAMPLE = SAMPLE / "cic_sample.csv.gz"
    UNSW_SAMPLE = SAMPLE / "unsw_sample.csv.gz"

    @staticmethod
    def results(scope):
        return Paths.RESULTS_FULL if scope == "full" else Paths.RESULTS_SAMPLE

    @staticmethod
    def clean(dataset):
        return Paths.CIC_CLEAN if dataset == "cic" else Paths.UNSW_CLEAN

    @staticmethod
    def sample(dataset):
        return Paths.CIC_SAMPLE if dataset == "cic" else Paths.UNSW_SAMPLE


class Sources:
    CIC_OFFICIAL_ZIP = ("https://cicresearch.ca/CICDataset/CIC-IDS-2017/Dataset/"
                        "CIC-IDS-2017/CSVs/MachineLearningCSV.zip")
    CIC_MIRROR_ZIP = ("https://huggingface.co/datasets/bencorn/CICIDS2017/"
                      "resolve/main/csvs/MachineLearningCSV.zip")
    CIC_ZIP_MD5 = "4f83860afbf29cac8163854095bf6cf7"
    UNSW_SHARE_LINK = ("https://unsw-my.sharepoint.com/:f:/g/personal/"
                       "z5025758_ad_unsw_edu_au/EnuQZZn3XuNBjgfcUu4DIVMBLCHyoLHqOswirpOQifr1ag?e=gKWkLS")
    UNSW_SP_SITE = "https://unsw-my.sharepoint.com/personal/z5025758_ad_unsw_edu_au"
    UNSW_SP_FOLDER = ("/personal/z5025758_ad_unsw_edu_au/Documents/UNSW-NB15 dataset/"
                      "CSV Files/Training and Testing Sets")
    UNSW_MIRROR_BASE = "https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15/resolve/main/"
    UNSW_FILES_MD5 = {
        "UNSW_NB15_training-set.csv": "e55caabaa6cd4a8f1c06a227bcfababc",
        "UNSW_NB15_testing-set.csv": "e0beea40262e46168cdb81476dbc27b4",
    }


class Cic:
    FILES = [
        ("Monday-WorkingHours.pcap_ISCX.csv", "Mon"),
        ("Tuesday-WorkingHours.pcap_ISCX.csv", "Tue"),
        ("Wednesday-workingHours.pcap_ISCX.csv", "Wed"),
        ("Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv", "Thu"),
        ("Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv", "Thu"),
        ("Friday-WorkingHours-Morning.pcap_ISCX.csv", "Fri"),
        ("Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv", "Fri"),
        ("Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv", "Fri"),
    ]
    DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    DAY_TO_ATTACKS = {
        "Mon": [],
        "Tue": ["FTP-Patator", "SSH-Patator"],
        "Wed": ["DoS slowloris", "DoS Slowhttptest", "DoS Hulk", "DoS GoldenEye", "Heartbleed"],
        "Thu": ["Web Attack - Brute Force", "Web Attack - XSS", "Web Attack - Sql Injection",
                "Infiltration"],
        "Fri": ["Bot", "PortScan", "DDoS"],
    }
    TIME_SPLIT = {"train": ["Mon", "Tue", "Wed"], "val": ["Thu"], "test": ["Fri"]}
    FAMILY = {
        "BENIGN": "benign",
        "FTP-Patator": "brute_force",
        "SSH-Patator": "brute_force",
        "DoS slowloris": "dos",
        "DoS Slowhttptest": "dos",
        "DoS Hulk": "dos",
        "DoS GoldenEye": "dos",
        "Heartbleed": "heartbleed",
        "Web Attack - Brute Force": "web_attack",
        "Web Attack - XSS": "web_attack",
        "Web Attack - Sql Injection": "web_attack",
        "Infiltration": "infiltration",
        "Bot": "botnet",
        "PortScan": "portscan",
        "DDoS": "ddos",
    }
    DUPLICATE_COLUMNS = {"Fwd Header Length.1": "Fwd Header Length"}


class Unsw:
    FILES = [("UNSW_NB15_training-set.csv", "train"), ("UNSW_NB15_testing-set.csv", "test")]
    FAMILY = {
        "Normal": "benign",
        "Generic": "generic",
        "Exploits": "exploits",
        "Fuzzers": "fuzzers",
        "DoS": "dos",
        "Reconnaissance": "reconnaissance",
        "Analysis": "analysis",
        "Backdoor": "backdoor",
        "Backdoors": "backdoor",
        "Shellcode": "shellcode",
        "Worms": "worms",
    }
    CATEGORICAL = ["proto", "service", "state"]


class Columns:
    META = ["label", "family", "y", "day", "part", "source_file", "row_in_file"]
    ID = {
        "cic": ["Flow ID", "Source IP", "Destination IP", "Timestamp", "Src IP", "Dst IP"],
        "unsw": ["id", "srcip", "dstip", "stime", "ltime"],
    }
    PORT = {
        "cic": ["Destination Port", "Source Port", "Src Port", "Dst Port"],
        "unsw": ["sport", "dsport"],
    }


class Sampling:
    SEED = 42
    SIZE = {"cic": 40_000, "unsw": 10_000}
    RARE_CLASS_MAX = 2_000
    MIN_PER_STRATUM = 200


class Experiment:
    SEEDS = [0, 1, 2]
    SPLIT_FRACTIONS = (0.70, 0.15, 0.15)
    TARGET_FPR = 0.01
    LOG_TRANSFORM = True
    N_JOBS = 8
    MODEL_PARAMS = {
        "logreg": {"C": 1.0},
        "rf": {"n_estimators": 100, "max_depth": 20, "min_samples_leaf": 1},
        "hgb": {"learning_rate": 0.1, "max_leaf_nodes": 15},
    }
