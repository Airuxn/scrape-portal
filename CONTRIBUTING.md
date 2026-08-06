# Contributing to Scrape Portal

Thanks for your interest in **Scrape Portal**.

## Before you start

- Read [README.md](README.md) and [SECURITY.md](SECURITY.md).
- Search [existing issues](https://github.com/Airuxn/scrape-portal/issues) to avoid duplicates.
- Do **not** open public issues for security exploits — see SECURITY.md.

## Development setup

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Airuxn/scrape-portal.git
cd scrape-portal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest test_rate_limit.py -q
uvicorn main:app --reload
```

## Pull requests

1. Fork and branch from `main`.
2. One logical change per PR.
3. Run `pytest test_rate_limit.py` before opening.
4. Keep SSRF, robots, and quota behaviour intact unless the PR explicitly changes the security model.

## Commit messages

Use clear, imperative subjects:

```
Fix quota slot counting for www-prefixed hosts
Add path filter for /jobs/ listing pages
```

## License

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE).
