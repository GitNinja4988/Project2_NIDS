# Bundled sample

Built by `data/make_sample.py` from the cleaned data. See report.md
for how rows are picked. Sample AUPRC is not comparable with
full-data AUPRC because rare labels are kept in full.

## cic: 40,000 flows (data/sample/cic_sample.csv.gz)

| label | full (clean) | sample |
|---|---:|---:|
| BENIGN | 2,095,786 | 28,693 |
| DoS Hulk | 172,719 | 2,482 |
| DDoS | 128,013 | 1,892 |
| PortScan | 90,255 | 1,393 |
| DoS GoldenEye | 10,286 | 336 |
| FTP-Patator | 5,933 | 278 |
| DoS slowloris | 5,384 | 271 |
| DoS Slowhttptest | 5,228 | 269 |
| SSH-Patator | 3,219 | 243 |
| Bot | 1,953 | 1,953 |
| Web Attack - Brute Force | 1,470 | 1,470 |
| Web Attack - XSS | 652 | 652 |
| Infiltration | 36 | 36 |
| Web Attack - Sql Injection | 21 | 21 |
| Heartbleed | 11 | 11 |

## unsw: 10,000 flows (data/sample/unsw_sample.csv.gz)

| label | full (clean) | sample |
|---|---:|---:|
| Normal | 85,308 | 3,378 |
| Exploits | 25,451 | 1,288 |
| Fuzzers | 18,749 | 1,055 |
| Reconnaissance | 8,419 | 694 |
| Generic | 7,283 | 654 |
| DoS | 3,624 | 526 |
| Shellcode | 1,446 | 1,446 |
| Analysis | 450 | 450 |
| Backdoor | 350 | 350 |
| Worms | 159 | 159 |

Both datasets are free for academic research with citation. Check the redistribution terms before pushing this sample to a public repo.
