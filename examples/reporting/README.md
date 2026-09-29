# Reporting walkthrough

`reporting.py` contains the Python blocks from the [package README](../../README.md)
in reading order, separated by one blank line. The configuration files match its
YAML, TOML and dotenv blocks. The script uses an in-memory password store and
prepares PostgreSQL connection arguments without opening a database connection.

With Python 3.12 or later, install the checkout and pytest in your environment.
From the repository root:

```bash
python -m pip install -e . pytest==8.3.5
cd examples/reporting
python reporting.py
```

Run from this directory so the relative configuration paths resolve. A successful
run produces no output; assertions check the results at each step. Run without
Python's `-O` flag, which disables assertions. Environment variables can override
the sample values: unset conflicting `REPORT_*` variables and variables named
after example fields such as `DEBUG`, `DATABASE` or `PASSWORD`.

To run the generated registry checks from the same directory:

```bash
python -m pytest reporting.py -q
```

When changing an example, update both the root README and the corresponding file
here. From the repository root, check that they still match and run:

```bash
hatch run test_github:pytest tests/test_readme_examples.py -q
```

The checks compare all Python blocks and the three configuration files verbatim
(with line endings normalized by Python's text reader). They also run the script
and its generated invariant tests in a temporary directory with conflicting
environment variables removed. These checks are part of the normal test suite.
