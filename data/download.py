import argparse
import hashlib
import sys
import urllib.parse
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Cic, Paths, Sources


class Downloader:
    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) eas510-project2"}

    def __init__(self, force=False):
        self.force = force
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    @staticmethod
    def md5(path):
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def fetch(self, url, dest):
        with self.session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            if "text/html" in r.headers.get("content-type", ""):
                print(f"  got a web page instead of a file from {url}")
                return False
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            tmp.rename(dest)
        return True

    def fetch_first_working(self, urls, dest):
        for url in urls:
            print("downloading", url)
            try:
                if self.fetch(url, dest):
                    return
            except requests.RequestException as e:
                print("  failed:", e)
        raise RuntimeError(f"could not download {dest.name}; see README")


class CicDownload(Downloader):
    def run(self):
        Paths.CIC_RAW.mkdir(parents=True, exist_ok=True)
        zip_path = Paths.CIC_RAW / "MachineLearningCSV.zip"
        if self.force or not zip_path.exists():
            self.fetch_first_working([Sources.CIC_OFFICIAL_ZIP, Sources.CIC_MIRROR_ZIP], zip_path)
        ok = self.md5(zip_path) == Sources.CIC_ZIP_MD5
        print(f"[CIC] MD5 {'matches the official zip' if ok else 'DOES NOT MATCH'}")
        self.unzip(zip_path)

    def unzip(self, zip_path):
        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                name = Path(info.filename).name
                target = Paths.CIC_RAW / name
                if name.endswith(".csv") and (self.force or not target.exists()):
                    target.write_bytes(z.read(info))
        missing = [f for f, _ in Cic.FILES if not (Paths.CIC_RAW / f).exists()]
        if missing:
            raise RuntimeError(f"missing CSVs after unzipping: {missing}")
        print(f"[CIC] {len(Cic.FILES)} CSVs in {Paths.CIC_RAW}")


class UnswDownload(Downloader):
    def run(self):
        Paths.UNSW_RAW.mkdir(parents=True, exist_ok=True)
        try:
            self.session.get(Sources.UNSW_SHARE_LINK, timeout=60)
        except requests.RequestException as e:
            print("could not open the UNSW share link:", e)
        for name, expected_md5 in Sources.UNSW_FILES_MD5.items():
            dest = Paths.UNSW_RAW / name
            if self.force or not dest.exists():
                self.fetch_first_working(self.urls(name), dest)
            print(f"[UNSW] {name} MD5 {'OK' if self.md5(dest) == expected_md5 else 'MISMATCH'}")

    @staticmethod
    def urls(name):
        source = urllib.parse.quote(f"{Sources.UNSW_SP_FOLDER}/{name}")
        official = f"{Sources.UNSW_SP_SITE}/_layouts/15/download.aspx?SourceUrl={source}"
        mirror = Sources.UNSW_MIRROR_BASE + ("train.csv" if "training" in name else "test.csv")
        return [official, mirror]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cic", action="store_true")
    parser.add_argument("--unsw", action="store_true")
    parser.add_argument("--force", action="store_true", help="download again even if present")
    args = parser.parse_args()
    both = not (args.cic or args.unsw)
    if args.cic or both:
        CicDownload(args.force).run()
    if args.unsw or both:
        UnswDownload(args.force).run()
