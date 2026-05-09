# Contributing to Ripen

We welcome contributions! To maintain the long-term sustainability of the project as a Single Vendor Commercial Open Source (SV-COS) product, we follow a specific contribution process.

## 1. Sign the CLA

Before we can merge your code, you must agree to our [Contributor License Agreement (CLA)](CLA.md). 

**How to sign:**
In your Pull Request description, simply include the following line:
> I have read and agree to the CLA for Ripen.

## 2. Our Acceptance Policy

We categorize contributions into three types:

| Category | Examples | Action |
| :--- | :--- | :--- |
| **Welcome** | Bug fixes, documentation, unit tests | Merged after review & CLA check |
| **Discussion Needed** | New features, refactoring | Open an Issue first to discuss |
| **Restricted** | Core license changes, monetization logic | Usually rejected to protect the vendor model |

## 3. Development Workflow

1.  **Fork** the repository.
2.  **Create a branch** for your fix/feature: `fix/issue-id-slug`.
3.  **Implement tests** for your changes.
4.  **Run linting**: `uv run ruff check .`.
5.  **Submit a Pull Request** with the CLA agreement statement.

## 4. Code Standards
- **Logging**: Use `loguru`.
- **Async**: Everything should be non-blocking.
- **Tests**: Maintain 80%+ coverage.

---
*Built with ❤️ by Ayato-Labs*
