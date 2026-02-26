# Contributing to MovieBox API

🎉 First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to **MovieBox API**. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## 🛠️ How Can I Contribute?

### Reporting Bugs
- Use the [GitHub Issues](https://github.com/walterwhite-69/Moviebox-API/issues) to report bugs.
- Describe the expected behavior and the actual behavior.
- Include steps to reproduce the issue.
- Mention your environment (Python version, OS, etc.).

### Suggesting Enhancements
- Check if the enhancement has already been suggested.
- Open an issue and describe the feature you'd like to see and why it would be useful.

### Pull Requests
1. **Fork the repository** and create your branch from `main`.
2. **If you've added code that should be tested**, add tests.
3. **Ensure the test suite passes** by running `python verify.py`.
4. **Format your code** according to PEP 8 standards.
5. **Issue a pull request!**

## 💻 Development Workflow

1. Install dependencies:
   ```bash
   pip install fastapi uvicorn httpx beautifulsoup4
   ```
2. Run the developer server:
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Verify your changes:
   ```bash
   python verify.py
   ```

## 📜 Code of Conduct

Help us keep this project open and inclusive. Please be respectful and professional in all interactions.

---

*Thank you for making MovieBox API better!*
