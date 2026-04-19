# CHANGELOG

<!-- version list -->

## v1.7.0 (2026-04-19)

### Chores

- Add diagnostic scripts for database migration verification and code validation
  ([`3198b4b`](https://github.com/ayato-labs/SharedMemoryServer/commit/3198b4b3228910aaec8964e0d974b8db1f5ce8a3))

### Code Style

- Fix ruff linting errors (import sort, line length, whitespace)
  ([`69c5f95`](https://github.com/ayato-labs/SharedMemoryServer/commit/69c5f95ef94119bca099167a2232d6563943ef5c))

### Documentation

- Rebrand README to emphasize state governance, architectural determinism, and intelligence
  provenance
  ([`0b71716`](https://github.com/ayato-labs/SharedMemoryServer/commit/0b71716cec4170a678d47282411a0410d8872a50))

### Features

- Enhance system observability and improve memory saving robustness
  ([`36ccd77`](https://github.com/ayato-labs/SharedMemoryServer/commit/36ccd77841b435b89441b38a1f51a2bad6dfe119))

- Implement core memory logic, database connection management, and comprehensive unit test suite
  ([`f310537`](https://github.com/ayato-labs/SharedMemoryServer/commit/f310537ff8f646263b7ec5314fbb42778dbc2c19))

- Implement graph-based entity, relation, and observation management with conflict detection and
  audit logging
  ([`a94a82e`](https://github.com/ayato-labs/SharedMemoryServer/commit/a94a82e861a4d4b71cf1da6a1d7d2ff854ed2687))

- Implement knowledge lifecycle management with activation, deactivation, and garbage collection
  modules and tests
  ([`409b6f4`](https://github.com/ayato-labs/SharedMemoryServer/commit/409b6f40fe31eda150eb6550e7e6a3007bf07a02))

- Implement memory logic normalization, database migration system, and robustness testing for bank
  file handling.
  ([`eb70bc3`](https://github.com/ayato-labs/SharedMemoryServer/commit/eb70bc3251766b091f639635868198db525849c3))

- Implement robust async SQLite connection management with retry logic and schema initialization
  ([`a23734a`](https://github.com/ayato-labs/SharedMemoryServer/commit/a23734ab0fdaa3570ce818e31ae844c0c9f354be))

- Implement robust database connection management with retry logic and add chaos testing suite
  ([`2d46568`](https://github.com/ayato-labs/SharedMemoryServer/commit/2d4656855adef878322d89378a91e69f0abdcf14))

- Implement shared memory bank system with cascading lifecycle management and search filtering
  ([`a7b4ede`](https://github.com/ayato-labs/SharedMemoryServer/commit/a7b4ede2ee12d4e54a4b026b5871bd8e13375a4b))

- Implement singleton database connection management with WAL mode and add migration infrastructure
  ([`08f39a7`](https://github.com/ayato-labs/SharedMemoryServer/commit/08f39a701e1d6b8469049f4d697215263b58aa27))

### Refactoring

- Harden error handling and optimize resource diagnostics
  ([`96c453d`](https://github.com/ayato-labs/SharedMemoryServer/commit/96c453dc5f3245533864d421cb68b6a5f7eedf75))

### Testing

- Add normalization logic tests and error handling verification scripts
  ([`f5e4ab6`](https://github.com/ayato-labs/SharedMemoryServer/commit/f5e4ab6d168064df23b2e391fc3690e61f7c0b5b))

- Implement comprehensive unit, integration, and system test suites with automated database
  lifecycle management and LLM mocking.
  ([`51002f3`](https://github.com/ayato-labs/SharedMemoryServer/commit/51002f361bf3a6c03cb64a80a1cf445589f81150))


## v1.6.0 (2026-04-19)

### Features

- Implement core graph, embedding, and search modules for shared memory service
  ([`3b5ea4a`](https://github.com/ayato-labs/SharedMemoryServer/commit/3b5ea4a43b3f609e844dc08a26bc553c3fb561c1))

- Implement core shared memory logic and add comprehensive unit, integration, and chaos test suites
  ([`a1e0914`](https://github.com/ayato-labs/SharedMemoryServer/commit/a1e09142f8a0b5b5f6ef4ec5a2bcf461b81c87ad))

- Implement hybrid search logic with keyword and vector-based retrieval capabilities
  ([`3fc1f4b`](https://github.com/ayato-labs/SharedMemoryServer/commit/3fc1f4b05f27240a861c56832e5737d2d18c86f9))

### Testing

- Add integration tests for severe fault scenarios including concurrency, large payloads, and error
  handling
  ([`8067e60`](https://github.com/ayato-labs/SharedMemoryServer/commit/8067e60ae0882ad603a6f37eb7e58c28ab8728a7))


## v1.5.0 (2026-04-17)

### Features

- Add simulation script to test memory core logic and retrieval flow
  ([`fc8161e`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/fc8161ef3542cbe30ef732207a7c23842980a998))


## v1.4.0 (2026-04-17)

### Chores

- Archive legacy tests and scratch scripts while initializing database and documentation structures
  ([`1f20440`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/1f204405009883f127a21015cfcccbe8624f4aba))

### Documentation

- Add design philosophy documentation for SharedMemoryServer
  ([`22ac76b`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/22ac76b261bc9a6e3f1e362bf3e0972078e7f9fe))

### Features

- Add utility scripts for database inspection, knowledge verification, legacy data migration, and
  trace visualization
  ([`d160066`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/d1600664e6ff208c9f189f7211e0d6a59f941526))

- Implement core database schema, logic modules, and comprehensive test suite for shared memory
  management
  ([`b479485`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/b47948598ad8b658ea94afb3caa31f280da3cf13))

- Implement Gemini-based text embedding generation with persistent caching and add path resolution
  utilities
  ([`612614a`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/612614a33432e9fbccf1064484e0eb2b284a8984))

- Implement graph-based entity management with conflict detection and add diagnostic trace/rescue
  tools
  ([`e5dd753`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/e5dd7537cde2c730ae2b5e77b714bab6a7137382))

- Implement graph-based knowledge management with conflict detection and audit logging
  ([`433e2bd`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/433e2bd20387d81115d194dee53f7c7c72c9ec99))

- Implement keyword and hybrid search logic with verification script
  ([`6bb2842`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/6bb2842eecdf305fff06bb3752ea2afb7649868a))

### Testing

- Add comprehensive integration, system, and unit test suites for memory workflows, search logic,
  and fault resilience.
  ([`659285e`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/659285eabd44524c8b94ce8fe5dfc51313cd7116))


## v1.3.0 (2026-04-13)

### Bug Fixes

- **mcp**: Ensure robust lazy database initialization for sequential_thinking
  ([`cca39dc`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/cca39dcbf0722dd08ffd73c92c3e4352058d8e44))

- **mcp**: Implement deep initialization hardening for database access
  ([`9d23fb5`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/9d23fb523cd57b5390b091c1becfffae4c0ea7c3))

### Code Style

- Final ruff cleanup and linting fixes for code and tests
  ([`cdce2e9`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/cdce2e9ac28e052e9a250429fd1a79ab6fef45fd))

- Fix linting errors in insights.py and synchronize updates
  ([`79f1254`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/79f125452833df0b00fdf2a443e37dae7af30d53))

- Fix syntax errors and initial ruff formatting issues in insights and tests
  ([`6af9716`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/6af971684d747a021f0f63931fbfbbb3c7b71359))

### Continuous Integration

- Add GitHub Actions workflow for linting, testing, semantic release, and Windows binary builds
  ([`251fd24`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/251fd24ab53cbd03e896feca68b75867ccb48be3))

- Add GitHub Actions workflow for linting, testing, semantic release, and Windows binary builds
  ([`743e274`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/743e274137c29a0f649b65982bba0fbded9d3ff7))

### Documentation

- Balance strategic positioning with hand-on technical depth
  ([`41537f8`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/41537f8cc639e3b2ab9bb44173bc41425e79c3ea))

- Document design decision for Knowledge Age vs Session ID in design_philosophy.md
  ([`9ceea1a`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/9ceea1a779ac40eb6fc5a0bdc0dcaa01b179a35d))

- Reform README for strategic AI architect positioning
  ([`2808aac`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/2808aac4d7100fca28c2458d26f8645a8064b7bb))

### Features

- Add CI/CD pipeline for linting, testing, semantic releases, and Windows binary builds
  ([`b5dc96c`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/b5dc96c799fbdf22644effc9c401db021fbf9bf6))

- Add CI/CD pipeline with linting, testing, semantic release, and Windows binary builds
  ([`c1b733e`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/c1b733e23e11164c45121b951499a11a3dd90126))

- Add CI/CD pipeline with linting, testing, semantic release, and Windows binary builds
  ([`63a0788`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/63a0788390c8e488095656ee03808931974f2a29))

- Add GitHub Actions CI/CD pipeline for linting, testing, semantic releases, and Windows binary
  builds
  ([`9ca5f42`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/9ca5f42cd1460107e26b4a4bdf9f4d911d71f606))

- Extend search_stats schema to support knowledge maturity metrics
  ([`1ce832d`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/1ce832d6873792243da9c8d12b4762f737fcddad))

- Implement 2nd Gen Insight Engine with Knowledge Maturity & Precision metrics
  ([`9416d3c`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/9416d3c6ba710727bf1f5d580976fb7284a9c4b0))

- Implement core shared memory server architecture including database, embeddings, and bank file
  management modules
  ([`0159b5f`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/0159b5f61effea580d85d6a5dbe1f3e8c2c1b776))

- Implement Fact-Based Insight Engine and comprehensive 3-tier testing suite
  ([`128dc37`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/128dc37aca1c09ce7cfa42029d4879a1271a53f5))

- Implement InsightEngine metrics and add integration test suite for memory search flow
  ([`73c1756`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/73c175679a87977786172d37d5b54f713a4b8a9d))

- Implement persistent thought logging and automated knowledge distillation system
  ([`d058800`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/d058800a8fb0592f1581a74ac2282a3922a88992))

- Implement semantic and keyword search systems with Gemini embedding support and persistent caching
  ([`c8ba107`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/c8ba107fff6caa58358878a5e5b84c1ea710edbc))

- Integrate Insight Engine with Admin MCP Server for external UI data provision
  ([`f31a346`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/f31a3469bcf7cb75e004b54e51ab9e03649ae38f))

- Record hit IDs and similarity scores in search stats
  ([`1135b30`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/1135b30661970337305457db7f6c4c740e9a0f9b))

### Refactoring

- Harden database connection management for tests and add diagnostic logging
  ([`e8646c1`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/e8646c16a33fe26e22e2272eb7b763a72302b344))

### Testing

- Add integration test for admin insight logic flow
  ([`a18de3e`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/a18de3e7763a0b727db1849dd165242e8433ae8b))

- Add unit test for markdown report generation
  ([`6a676bb`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/6a676bb9c26a1aaef7c2c4507ae3ca3f43dd7edf))

- Fix unused variables and localized keyword assertions in insight tests
  ([`371a16d`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/371a16d8cb429a6ce7b369f4abdc0e5ea6fff91d))

- Update system test to verify value report via logic layer
  ([`d3e0258`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/d3e025805bdbad71ed40f5b89863caf6d17e85c8))

- **system**: Add regression test for robust database initialization
  ([`04f0538`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/04f053806d4e99e655787097deacc150d50bcb12))


## v1.2.0 (2026-04-10)

### Code Style

- Fix trailing whitespace in server.py docstring
  ([`036b156`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/036b156b0207fa752fd59d4391f4d5720e266e26))

### Features

- **mcp**: Add commit advisory to sequential_thinking tool to encourage traceability
  ([`d0b379f`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/d0b379f1cc8cbb8972bb5aeecfba0b5d369a3b26))


## v1.1.2 (2026-04-10)

### Bug Fixes

- Resolve ruff lint errors (E501, I001, W293)
  ([`66b6ae8`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/66b6ae851dbaa0f3481cf60bcee1c00c1c1ce850))

- **ci**: Forcibly terminate OS process after tests pass to completely bypass thread hangs
  ([`20e72ab`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/20e72ab5890056e31a34dfa2c5a20b5c560e86bd))

- **ci**: Switch to pytest-timeout and remove external timeout to prevent job hangs
  ([`8e9a7db`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/8e9a7db2612f125e47d5270e47abcb0601658fb7))

- **test**: Aggressively prevent event loop hangs in CI by shortening cleanup timeout
  ([`c1a9ebe`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/c1a9ebe6d1f19f0e53b30efb4ddf8af9ef58dd76))

- **test**: Harden task cleanup in conftest to prevent CI hangs
  ([`2f13157`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/2f13157d03f79d2b409bd6a13b8b140f1af54ab4))

### Code Style

- Fix remaining ruff lint errors including import sorting
  ([`a243b8f`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/a243b8fba5b4aafc7a11439864deae7b389b01dc))

- Replace aliased asyncio.TimeoutError with builtin TimeoutError (UP041)
  ([`ee7c649`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/ee7c64942a61c52b982028dfc20c902fb14538f7))

- Sort imports in tests and scratch scripts to satisfy ruff
  ([`293f8bf`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/293f8bff99ca0e2c96a9bf99a69cdefe607f52f4))

### Refactoring

- Semantic naming alignment and database resilience hardening
  ([`6e47cf7`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/6e47cf7bec74192b1800573c958b5a991631290f))


## v1.1.1 (2026-04-09)

### Bug Fixes

- **ci**: Only build assets when a new release is published to avoid tag missing error
  ([`2c13060`](https://github.com/Ayato-AI-for-Auto/SharedMemoryServer/commit/2c130609bad46d5ecc4546dcc30317e3237280c6))


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
