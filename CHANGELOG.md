# CHANGELOG

<!-- version list -->

## v1.13.5 (2026-05-17)

### Bug Fixes

- Extend Gemini API timeout to 120s
  ([`a7a0737`](https://github.com/ayato-labs/ripen/commit/a7a0737159e5e8ed5026b60c9a31a6a7a9fe6319))

- Remove unused history argument from salvage_related_knowledge call
  ([#131](https://github.com/ayato-labs/ripen/pull/131),
  [`b66ca8e`](https://github.com/ayato-labs/ripen/commit/b66ca8e152826770ee2096c4f3445325490ce8ac))


## v1.13.4 (2026-05-17)

### Bug Fixes

- Consolidated pipeline fixes and model change to gemma4:e2b
  ([#129](https://github.com/ayato-labs/ripen/pull/129),
  [`53827ef`](https://github.com/ayato-labs/ripen/commit/53827efe2904cbc0d1168a8748b5400f0bcc1f10))


## v1.13.3 (2026-05-17)

### Bug Fixes

- Run Windows tests on native .exe to fix Docker platform error
  ([`59fa1fd`](https://github.com/ayato-labs/ripen/commit/59fa1fd9aa585283f7b41e80243f6931b6bf6041))


## v1.13.2 (2026-05-17)


## v1.13.1 (2026-05-17)

### Bug Fixes

- Allow Trivy scan to report without failing the build
  ([`f305690`](https://github.com/ayato-labs/ripen/commit/f305690c4b502ac542b5c32d1c93383f2d1cf299))

- Fetch tags and add fallback for release job
  ([`a2ef116`](https://github.com/ayato-labs/ripen/commit/a2ef116aa9850e33d69513148ffb39edadf74367))


## v1.13.0 (2026-05-17)

### Bug Fixes

- Drop support for Python 3.10 and update matrix tests
  ([`b4be804`](https://github.com/ayato-labs/ripen/commit/b4be804e9bb241699db595503859bae1145965a1))


## v1.12.0 (2026-05-16)


## v1.11.0 (2026-05-16)

### Bug Fixes

- Remove blank lines in dashboard.html to satisfy linter
  ([`e17f7fd`](https://github.com/ayato-labs/ripen/commit/e17f7fda4eb5d562ab400b8370214d1bdf4b7cbd))

### Documentation

- Add AGPL clarification and formalize trial in COMMERCIAL.md
  ([`5e22311`](https://github.com/ayato-labs/ripen/commit/5e22311627ed72b21ca51699a48a2579e520ea66))

- Add Keygen.sh 100 license limit warning to COMMERCIAL.md
  ([`0fdc3fd`](https://github.com/ayato-labs/ripen/commit/0fdc3fdf9b4ff623c2f9cd838ca5f41ed3518e50))

- Add update instructions for Docker in README
  ([`b54ec5e`](https://github.com/ayato-labs/ripen/commit/b54ec5e026b12de24d0146bb71c7f315dc859216))

- Clarify manual license fallback and mention Keygen.sh in COMMERCIAL.md
  ([`293d572`](https://github.com/ayato-labs/ripen/commit/293d57272c7b787b06c136f006c4eae9c7ca29a9))

- Use foreground execution as default in README Docker commands
  ([`41863bf`](https://github.com/ayato-labs/ripen/commit/41863bfc57176ee69bb400495a2b52ee65efd384))

- Use self-declaration flow and remove Keygen.sh in COMMERCIAL.md
  ([`6f6d3a3`](https://github.com/ayato-labs/ripen/commit/6f6d3a3fb5d9905d13e1c8ef350de43bf92f22f7))

### Features

- Implement MCP server with knowledge management tools and permissive handshake protocol patching
  ([`2b52df8`](https://github.com/ayato-labs/ripen/commit/2b52df8a30f11aefbebde157adecd7ae900cb65a))

- Remove license activation UI and JS from dashboard
  ([`29b6b2e`](https://github.com/ayato-labs/ripen/commit/29b6b2eb79fd6bb6f951a06ca6008b5705496e4f))


## v1.10.1 (2026-05-16)

### Bug Fixes

- Mount dashboard routes in server.py using custom_route
  ([`d87531f`](https://github.com/ayato-labs/ripen/commit/d87531fc0d5da468f8b7df9a53074a9f476b15d4))

- Resolve Ruff import sorting error in server.py
  ([`164cc97`](https://github.com/ayato-labs/ripen/commit/164cc9774418e4cf412e4990f1c2db765189d6ce))


## v1.10.0 (2026-05-16)

### Features

- Log version at startup and expand Docker docs in README
  ([`da1639f`](https://github.com/ayato-labs/ripen/commit/da1639fe39eb51bb52bc02dd845e47a34c892430))


## v1.9.2 (2026-05-16)

### Bug Fixes

- Remove unsupported --sse flag from Dockerfile entrypoint
  ([`d857a3f`](https://github.com/ayato-labs/ripen/commit/d857a3f10299afba7fa1bfe1a26cdbf4b34eec5d))

### Documentation

- Remove Stdio connection instructions from README
  ([`16db705`](https://github.com/ayato-labs/ripen/commit/16db70587484e265ec15acd2596491ca71c92ad2))

- Update README to prioritize Docker installation
  ([`25d0ca2`](https://github.com/ayato-labs/ripen/commit/25d0ca2026b39fc68cf4d045374c81a1da8c6038))


## v1.9.1 (2026-05-16)

### Bug Fixes

- Use PAT_TOKEN for Docker login to fix GHCR permission error
  ([`ae47063`](https://github.com/ayato-labs/ripen/commit/ae4706369c50ce376c435ee2fca2461ee97852e7))


## v1.9.0 (2026-05-16)

### Features

- Add Docker build and push to GHCR in main.yml
  ([`4c4701e`](https://github.com/ayato-labs/ripen/commit/4c4701e6ee3f156bd12b693596cc153651507eec))


## v1.8.4 (2026-05-16)

### Bug Fixes

- Add --copy-metadata for fastmcp and ripen to PyInstaller
  ([`37051b5`](https://github.com/ayato-labs/ripen/commit/37051b554cde7263acbb3fbc2c4883ab314de881))

- Rename SharedMemoryRegister to RipenInstaller
  ([`79517ce`](https://github.com/ayato-labs/ripen/commit/79517ce416a92bba9b10e324e4f5e8dd2de68622))


## v1.8.3 (2026-05-16)

### Bug Fixes

- Pass tag_name explicitly to action-gh-release to fix tag missing error
  ([`32c0475`](https://github.com/ayato-labs/ripen/commit/32c0475bb3f67ea4d1f9b60d2605d3a862ad4273))

- Remove duplicate env block in main.yml
  ([`a0affa6`](https://github.com/ayato-labs/ripen/commit/a0affa616a532c630db8f88ff8bbcc68ec780dcf))


## v1.8.2 (2026-05-16)

### Bug Fixes

- Correct PyInstaller script paths in main.yml
  ([`69548aa`](https://github.com/ayato-labs/ripen/commit/69548aaa9751fee77199c00f411cbdc8641ba712))


## v1.8.1 (2026-05-16)

### Bug Fixes

- Trigger release v1.8.1
  ([`df3bbe5`](https://github.com/ayato-labs/ripen/commit/df3bbe574b62b6e4df04a23e967fd2c59ebdb328))


## v1.8.0 (2026-04-22)

### Features

- Implement automated knowledge distillation and LLM-driven retrieval salvage for memory management.
  ([`71a7e8a`](https://github.com/ayato-labs/Ripen/commit/71a7e8a67109fbb51cb3b92e461fd0e61b9d8c42))


## v1.7.0 (2026-04-19)

### Chores

- Add diagnostic scripts for database migration verification and code validation
  ([`3198b4b`](https://github.com/ayato-labs/Ripen/commit/3198b4b3228910aaec8964e0d974b8db1f5ce8a3))

### Code Style

- Fix ruff linting errors (import sort, line length, whitespace)
  ([`69c5f95`](https://github.com/ayato-labs/Ripen/commit/69c5f95ef94119bca099167a2232d6563943ef5c))

### Documentation

- Rebrand README to emphasize state governance, architectural determinism, and intelligence
  provenance
  ([`0b71716`](https://github.com/ayato-labs/Ripen/commit/0b71716cec4170a678d47282411a0410d8872a50))

### Features

- Enhance system observability and improve memory saving robustness
  ([`36ccd77`](https://github.com/ayato-labs/Ripen/commit/36ccd77841b435b89441b38a1f51a2bad6dfe119))

- Implement core memory logic, database connection management, and comprehensive unit test suite
  ([`f310537`](https://github.com/ayato-labs/Ripen/commit/f310537ff8f646263b7ec5314fbb42778dbc2c19))

- Implement graph-based entity, relation, and observation management with conflict detection and
  audit logging
  ([`a94a82e`](https://github.com/ayato-labs/Ripen/commit/a94a82e861a4d4b71cf1da6a1d7d2ff854ed2687))

- Implement knowledge lifecycle management with activation, deactivation, and garbage collection
  modules and tests
  ([`409b6f4`](https://github.com/ayato-labs/Ripen/commit/409b6f40fe31eda150eb6550e7e6a3007bf07a02))

- Implement memory logic normalization, database migration system, and robustness testing for bank
  file handling.
  ([`eb70bc3`](https://github.com/ayato-labs/Ripen/commit/eb70bc3251766b091f639635868198db525849c3))

- Implement robust async SQLite connection management with retry logic and schema initialization
  ([`a23734a`](https://github.com/ayato-labs/Ripen/commit/a23734ab0fdaa3570ce818e31ae844c0c9f354be))

- Implement robust database connection management with retry logic and add chaos testing suite
  ([`2d46568`](https://github.com/ayato-labs/Ripen/commit/2d4656855adef878322d89378a91e69f0abdcf14))

- Implement shared memory bank system with cascading lifecycle management and search filtering
  ([`a7b4ede`](https://github.com/ayato-labs/Ripen/commit/a7b4ede2ee12d4e54a4b026b5871bd8e13375a4b))

- Implement singleton database connection management with WAL mode and add migration infrastructure
  ([`08f39a7`](https://github.com/ayato-labs/Ripen/commit/08f39a701e1d6b8469049f4d697215263b58aa27))

### Refactoring

- Harden error handling and optimize resource diagnostics
  ([`96c453d`](https://github.com/ayato-labs/Ripen/commit/96c453dc5f3245533864d421cb68b6a5f7eedf75))

### Testing

- Add normalization logic tests and error handling verification scripts
  ([`f5e4ab6`](https://github.com/ayato-labs/Ripen/commit/f5e4ab6d168064df23b2e391fc3690e61f7c0b5b))

- Implement comprehensive unit, integration, and system test suites with automated database
  lifecycle management and LLM mocking.
  ([`51002f3`](https://github.com/ayato-labs/Ripen/commit/51002f361bf3a6c03cb64a80a1cf445589f81150))


## v1.6.0 (2026-04-19)

### Features

- Implement core graph, embedding, and search modules for shared memory service
  ([`3b5ea4a`](https://github.com/ayato-labs/Ripen/commit/3b5ea4a43b3f609e844dc08a26bc553c3fb561c1))

- Implement core shared memory logic and add comprehensive unit, integration, and chaos test suites
  ([`a1e0914`](https://github.com/ayato-labs/Ripen/commit/a1e09142f8a0b5b5f6ef4ec5a2bcf461b81c87ad))

- Implement hybrid search logic with keyword and vector-based retrieval capabilities
  ([`3fc1f4b`](https://github.com/ayato-labs/Ripen/commit/3fc1f4b05f27240a861c56832e5737d2d18c86f9))

### Testing

- Add integration tests for severe fault scenarios including concurrency, large payloads, and error
  handling
  ([`8067e60`](https://github.com/ayato-labs/Ripen/commit/8067e60ae0882ad603a6f37eb7e58c28ab8728a7))


## v1.5.0 (2026-04-17)

### Features

- Add simulation script to test memory core logic and retrieval flow
  ([`fc8161e`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/fc8161ef3542cbe30ef732207a7c23842980a998))


## v1.4.0 (2026-04-17)

### Chores

- Archive legacy tests and scratch scripts while initializing database and documentation structures
  ([`1f20440`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/1f204405009883f127a21015cfcccbe8624f4aba))

### Documentation

- Add design philosophy documentation for Ripen
  ([`22ac76b`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/22ac76b261bc9a6e3f1e362bf3e0972078e7f9fe))

### Features

- Add utility scripts for database inspection, knowledge verification, legacy data migration, and
  trace visualization
  ([`d160066`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/d1600664e6ff208c9f189f7211e0d6a59f941526))

- Implement core database schema, logic modules, and comprehensive test suite for shared memory
  management
  ([`b479485`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/b47948598ad8b658ea94afb3caa31f280da3cf13))

- Implement Gemini-based text embedding generation with persistent caching and add path resolution
  utilities
  ([`612614a`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/612614a33432e9fbccf1064484e0eb2b284a8984))

- Implement graph-based entity management with conflict detection and add diagnostic trace/rescue
  tools
  ([`e5dd753`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/e5dd7537cde2c730ae2b5e77b714bab6a7137382))

- Implement graph-based knowledge management with conflict detection and audit logging
  ([`433e2bd`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/433e2bd20387d81115d194dee53f7c7c72c9ec99))

- Implement keyword and hybrid search logic with verification script
  ([`6bb2842`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/6bb2842eecdf305fff06bb3752ea2afb7649868a))

### Testing

- Add comprehensive integration, system, and unit test suites for memory workflows, search logic,
  and fault resilience.
  ([`659285e`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/659285eabd44524c8b94ce8fe5dfc51313cd7116))


## v1.3.0 (2026-04-13)

### Bug Fixes

- **mcp**: Ensure robust lazy database initialization for sequential_thinking
  ([`cca39dc`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/cca39dcbf0722dd08ffd73c92c3e4352058d8e44))

- **mcp**: Implement deep initialization hardening for database access
  ([`9d23fb5`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/9d23fb523cd57b5390b091c1becfffae4c0ea7c3))

### Code Style

- Final ruff cleanup and linting fixes for code and tests
  ([`cdce2e9`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/cdce2e9ac28e052e9a250429fd1a79ab6fef45fd))

- Fix linting errors in insights.py and synchronize updates
  ([`79f1254`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/79f125452833df0b00fdf2a443e37dae7af30d53))

- Fix syntax errors and initial ruff formatting issues in insights and tests
  ([`6af9716`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/6af971684d747a021f0f63931fbfbbb3c7b71359))

### Continuous Integration

- Add GitHub Actions workflow for linting, testing, semantic release, and Windows binary builds
  ([`251fd24`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/251fd24ab53cbd03e896feca68b75867ccb48be3))

- Add GitHub Actions workflow for linting, testing, semantic release, and Windows binary builds
  ([`743e274`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/743e274137c29a0f649b65982bba0fbded9d3ff7))

### Documentation

- Balance strategic positioning with hand-on technical depth
  ([`41537f8`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/41537f8cc639e3b2ab9bb44173bc41425e79c3ea))

- Document design decision for Knowledge Age vs Session ID in design_philosophy.md
  ([`9ceea1a`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/9ceea1a779ac40eb6fc5a0bdc0dcaa01b179a35d))

- Reform README for strategic AI architect positioning
  ([`2808aac`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/2808aac4d7100fca28c2458d26f8645a8064b7bb))

### Features

- Add CI/CD pipeline for linting, testing, semantic releases, and Windows binary builds
  ([`b5dc96c`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/b5dc96c799fbdf22644effc9c401db021fbf9bf6))

- Add CI/CD pipeline with linting, testing, semantic release, and Windows binary builds
  ([`c1b733e`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/c1b733e23e11164c45121b951499a11a3dd90126))

- Add CI/CD pipeline with linting, testing, semantic release, and Windows binary builds
  ([`63a0788`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/63a0788390c8e488095656ee03808931974f2a29))

- Add GitHub Actions CI/CD pipeline for linting, testing, semantic releases, and Windows binary
  builds
  ([`9ca5f42`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/9ca5f42cd1460107e26b4a4bdf9f4d911d71f606))

- Extend search_stats schema to support knowledge maturity metrics
  ([`1ce832d`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/1ce832d6873792243da9c8d12b4762f737fcddad))

- Implement 2nd Gen Insight Engine with Knowledge Maturity & Precision metrics
  ([`9416d3c`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/9416d3c6ba710727bf1f5d580976fb7284a9c4b0))

- Implement core shared memory server architecture including database, embeddings, and bank file
  management modules
  ([`0159b5f`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/0159b5f61effea580d85d6a5dbe1f3e8c2c1b776))

- Implement Fact-Based Insight Engine and comprehensive 3-tier testing suite
  ([`128dc37`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/128dc37aca1c09ce7cfa42029d4879a1271a53f5))

- Implement InsightEngine metrics and add integration test suite for memory search flow
  ([`73c1756`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/73c175679a87977786172d37d5b54f713a4b8a9d))

- Implement persistent thought logging and automated knowledge distillation system
  ([`d058800`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/d058800a8fb0592f1581a74ac2282a3922a88992))

- Implement semantic and keyword search systems with Gemini embedding support and persistent caching
  ([`c8ba107`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/c8ba107fff6caa58358878a5e5b84c1ea710edbc))

- Integrate Insight Engine with Admin MCP Server for external UI data provision
  ([`f31a346`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/f31a3469bcf7cb75e004b54e51ab9e03649ae38f))

- Record hit IDs and similarity scores in search stats
  ([`1135b30`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/1135b30661970337305457db7f6c4c740e9a0f9b))

### Refactoring

- Harden database connection management for tests and add diagnostic logging
  ([`e8646c1`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/e8646c16a33fe26e22e2272eb7b763a72302b344))

### Testing

- Add integration test for admin insight logic flow
  ([`a18de3e`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/a18de3e7763a0b727db1849dd165242e8433ae8b))

- Add unit test for markdown report generation
  ([`6a676bb`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/6a676bb9c26a1aaef7c2c4507ae3ca3f43dd7edf))

- Fix unused variables and localized keyword assertions in insight tests
  ([`371a16d`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/371a16d8cb429a6ce7b369f4abdc0e5ea6fff91d))

- Update system test to verify value report via logic layer
  ([`d3e0258`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/d3e025805bdbad71ed40f5b89863caf6d17e85c8))

- **system**: Add regression test for robust database initialization
  ([`04f0538`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/04f053806d4e99e655787097deacc150d50bcb12))


## v1.2.0 (2026-04-10)

### Code Style

- Fix trailing whitespace in server.py docstring
  ([`036b156`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/036b156b0207fa752fd59d4391f4d5720e266e26))

### Features

- **mcp**: Add commit advisory to sequential_thinking tool to encourage traceability
  ([`d0b379f`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/d0b379f1cc8cbb8972bb5aeecfba0b5d369a3b26))


## v1.1.2 (2026-04-10)

### Bug Fixes

- Resolve ruff lint errors (E501, I001, W293)
  ([`66b6ae8`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/66b6ae851dbaa0f3481cf60bcee1c00c1c1ce850))

- **ci**: Forcibly terminate OS process after tests pass to completely bypass thread hangs
  ([`20e72ab`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/20e72ab5890056e31a34dfa2c5a20b5c560e86bd))

- **ci**: Switch to pytest-timeout and remove external timeout to prevent job hangs
  ([`8e9a7db`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/8e9a7db2612f125e47d5270e47abcb0601658fb7))

- **test**: Aggressively prevent event loop hangs in CI by shortening cleanup timeout
  ([`c1a9ebe`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/c1a9ebe6d1f19f0e53b30efb4ddf8af9ef58dd76))

- **test**: Harden task cleanup in conftest to prevent CI hangs
  ([`2f13157`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/2f13157d03f79d2b409bd6a13b8b140f1af54ab4))

### Code Style

- Fix remaining ruff lint errors including import sorting
  ([`a243b8f`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/a243b8fba5b4aafc7a11439864deae7b389b01dc))

- Replace aliased asyncio.TimeoutError with builtin TimeoutError (UP041)
  ([`ee7c649`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/ee7c64942a61c52b982028dfc20c902fb14538f7))

- Sort imports in tests and scratch scripts to satisfy ruff
  ([`293f8bf`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/293f8bff99ca0e2c96a9bf99a69cdefe607f52f4))

### Refactoring

- Semantic naming alignment and database resilience hardening
  ([`6e47cf7`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/6e47cf7bec74192b1800573c958b5a991631290f))


## v1.1.1 (2026-04-09)

### Bug Fixes

- **ci**: Only build assets when a new release is published to avoid tag missing error
  ([`2c13060`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/2c130609bad46d5ecc4546dcc30317e3237280c6))


## v1.1.0 (2026-04-09)

### Bug Fixes

- Resolve CI/CD test regressions and environment conflicts
  ([`570e616`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/570e616ebdf28c89bf2b22bf91a14b08a13233ea))

- Resolve GitHub Actions hang by improving asyncio task management and test cleanup
  ([`bb77503`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/bb77503e4f6cafe1ebe2b49569cd006862597b7c))

- Resolve test regressions and mock logic bugs
  ([`03032f4`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/03032f42a5f1190db080e289863c203aebe62cf5))

- **ci**: Resolve GHA hang by isolating curated tests and enhancing task cleanup
  ([`7fb3fc1`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/7fb3fc100d2279ca23291f7ec2fc2edc66736d6d))

- **lint**: Fix E501 and I001 lint errors in conftest.py
  ([`1622b0c`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/1622b0cb823f9fe65dc1b1d098fd45b4715acc75))

- **test**: Make DB teardown robust to handle corrupted databases in resilience tests
  ([`604febc`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/604febc2da926a913cbc5355251a95da9fde6039))

### Chores

- Final manual linting cleanup and repository stabilization
  ([`33e5fd9`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/33e5fd978a58eb36184d6bd718e7dc50db498e6f))

- Global linting cleanup for tests and scratch
  ([`0546822`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/0546822f5331b43229ed6e0d692e585268410ba3))

### Code Style

- Fix remaining ruff lint errors in tests
  ([`f6edda0`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/f6edda0d9107872e79173e1d27c068947a86be86))

- Fix ruff lint errors in conftest.py
  ([`5319f73`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/5319f73265db96373567b132a2ef391b8cf68ade))

### Features

- Consolidate CI/CD into unified pipeline
  ([`512d892`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/512d892f3f9599358a633d0ad8dbf772bfe62716))

### Testing

- Reorganize test suite into unit, integration, and system layers with fake LLM client
  ([`ea46e22`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/ea46e220e904ec58d0abda352008efcf247941fe))


## v1.0.0 (2026-04-09)

### Bug Fixes

- Remove redundant build_command from semantic-release
  ([`dc7b868`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/dc7b8686cb465717ff4c4e83b96e1da8faf0647f))

### Features

- High-concurrency architecture and tool separation
  ([`321b290`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/321b290de8e63f3ea2fd241526abf611a3e033c6))

- Integrate knowledge injection into sequential thinking and code cleanup
  ([`dcd6e4d`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/dcd6e4d6c9d7f7ca6e199409be737a80d0172e20))

- Integrate semantic-release and ci/cd
  ([`c8239e3`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/c8239e389e7c7497e1fcd7d11c0ea4e9bb1b099e))

- Switch default branch back to master
  ([`7d764ef`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/7d764ef4daa965c226f2550150a5455b329b4f39))


## v0.1.1 (2026-03-19)

### Bug Fixes

- Add write permissions for releases
  ([`689381e`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/689381ee8352cdb52a56a8411bb1de0802420c71))


## v0.1.0 (2026-03-19)

### Features

- Add github action for release and enhance registration scripts
  ([`7ce04ac`](https://github.com/Ayato-AI-for-Auto/Ripen/commit/7ce04ac3e88d5d3a9231c31660ee3c23f18cea48))


## v0.5.0 (2026-03-18)

- Initial Release
