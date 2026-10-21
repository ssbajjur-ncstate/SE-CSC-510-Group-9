# Why TestBudget

A pull request does not need every test. But running only some of them is a gamble, and nobody can say how risky it is.

TestBudget turns that gamble into a measured budget. It learns from your CI history which tests fail, and which source files they fail with. For a new change it ranks the tests by how much risk they cover per second, then runs as many as fit the time budget you choose, and says why each one was picked or skipped.

The claim we test: running 30% of the suite catches at least 85% of failing runs. The method for checking it is in the [evaluation protocol](eval-protocol.md), and results are reported as they come out, including if they miss.

```bash
python -m testbudget.cli init
python -m testbudget.cli ingest fixtures/sample_junit.xml
python -m testbudget.cli plan --changed src/checkout.py --budget 30
```

Next: [link tests to the code they cover](links.md), or browse the [API reference](api.md).
