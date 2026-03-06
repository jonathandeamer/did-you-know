# Contributing

Thanks for taking a look! Bug reports, fixes, and ideas are all welcome — feel free to open an issue or a PR.

This project fetches from Wikipedia but never edits the encyclopedia, and I'd like to keep it that way.

If you're making changes that touch the Wikipedia API, please be mindful of the
[API etiquette](https://www.mediawiki.org/wiki/API:Etiquette). The script already includes
rate limiting and a descriptive User-Agent, and any changes should preserve that.

If you change `scripts/dyk.py`, please add or update tests as needed. The test suite in
`tests/test_dyk.py` covers parsing, caching, and the main flow.

Please use [Conventional Commits](https://www.conventionalcommits.org) for commit messages.

Glad to have you here.
