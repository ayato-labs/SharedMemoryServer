# CHANGELOG

<!-- version list -->

## v1.1.0 (2026-04-09)

### Bug Fixes

- Resolve CI/CD test regressions and environment conflicts
  ([`570e616`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/570e616ebdf28c89bf2b22bf91a14b08a13233ea))

- Resolve GitHub Actions hang by improving asyncio task management and test cleanup
  ([`bb77503`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/bb77503e4f6cafe1ebe2b49569cd006862597b7c))

- Resolve test regressions and mock logic bugs
  ([`03032f4`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/03032f42a5f1190db080e289863c203aebe62cf5))

- **ci**: Resolve GHA hang by isolating curated tests and enhancing task cleanup
  ([`7fb3fc1`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/7fb3fc100d2279ca23291f7ec2fc2edc66736d6d))

- **lint**: Fix E501 and I001 lint errors in conftest.py
  ([`1622b0c`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/1622b0cb823f9fe65dc1b1d098fd45b4715acc75))

- **test**: Make DB teardown robust to handle corrupted databases in resilience tests
  ([`604febc`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/604febc2da926a913cbc5355251a95da9fde6039))

### Chores

- Final manual linting cleanup and repository stabilization
  ([`33e5fd9`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/33e5fd978a58eb36184d6bd718e7dc50db498e6f))

- Global linting cleanup for tests and scratch
  ([`0546822`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/0546822f5331b43229ed6e0d692e585268410ba3))

### Code Style

- Fix remaining ruff lint errors in tests
  ([`f6edda0`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/f6edda0d9107872e79173e1d27c068947a86be86))

- Fix ruff lint errors in conftest.py
  ([`5319f73`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/5319f73265db96373567b132a2ef391b8cf68ade))

### Features

- Consolidate CI/CD into unified pipeline
  ([`512d892`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/512d892f3f9599358a633d0ad8dbf772bfe62716))

### Testing

- Reorganize test suite into unit, integration, and system layers with fake LLM client
  ([`ea46e22`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/ea46e220e904ec58d0abda352008efcf247941fe))


## v1.0.0 (2026-04-09)

### Bug Fixes

- Remove redundant build_command from semantic-release
  ([`dc7b868`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/dc7b8686cb465717ff4c4e83b96e1da8faf0647f))

### Features

- High-concurrency architecture and tool separation
  ([`321b290`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/321b290de8e63f3ea2fd241526abf611a3e033c6))

- Integrate knowledge injection into sequential thinking and code cleanup
  ([`dcd6e4d`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/dcd6e4d6c9d7f7ca6e199409be737a80d0172e20))

- Integrate semantic-release and ci/cd
  ([`c8239e3`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/c8239e389e7c7497e1fcd7d11c0ea4e9bb1b099e))

- Switch default branch back to master
  ([`7d764ef`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/7d764ef4daa965c226f2550150a5455b329b4f39))


## v0.1.1 (2026-03-19)

### Bug Fixes

- Add write permissions for releases
  ([`689381e`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/689381ee8352cdb52a56a8411bb1de0802420c71))


## v0.1.0 (2026-03-19)

### Features

- Add github action for release and enhance registration scripts
  ([`7ce04ac`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/7ce04ac3e88d5d3a9231c31660ee3c23f18cea48))


## v0.5.0 (2026-03-18)

- Initial Release
