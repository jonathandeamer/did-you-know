# Contributing

Thanks for taking a look! Bug reports, fixes, and ideas are all welcome — feel free to open an issue or a PR.

- **Standard library only** — scripts run on pure Python with no third-party packages. I'd love to keep it that way for as long as possible! If you hit something that really seems to need a dependency, open an issue and let's figure it out together.
- **Read-only Wikipedia** — this project fetches from the encyclopedia but never edits it, and I'd like to keep it that way.
- **API etiquette** — if you're touching the Wikipedia API, please be mindful of the [API etiquette](https://www.mediawiki.org/wiki/API:Etiquette). The scripts already include rate limiting and a descriptive User-Agent, and any changes should preserve that.
- **Tests** — if you change a script, please add or update tests as needed. The test suite in `tests/` covers parsing, caching, and the main flow.
- **Conventional Commits** — please use [Conventional Commits](https://www.conventionalcommits.org) for commit messages.

Glad to have you here!
