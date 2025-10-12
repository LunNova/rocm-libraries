# perf-tests

## Running tests

```bash
# Basic test run
./setup.sh

# With multiprocessing (tests pickle/unpickle)
./setup.sh --multiprocessing

# With memray profiling
PROFILER=memray ./setup.sh

# Different test script
TEST_SCRIPT=test_pickle_identity.py ./setup.sh

# Custom command with configured env
./setup.sh exec python3 -c "import sys; print(sys.path)"
```

## What setup.sh does
- Builds rocisa.so if needed
- Sets PYTHONPATH with rocisa and tensilelite
- Runs TEST_SCRIPT (default: test_parse_logic.py)
