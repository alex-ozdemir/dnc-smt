# Parallel-SMT/gg

## Tests

Run with `make test`.

Test themselves are in `test`.

## Scripts

The `split.py` script is a dummy splitter, which emits "true" cubes. Run it
with `-h` for information.

The `smt.py` script is a pygg main script. Run it like `./smt.py init solve
SMT2PATH INIT-SPLITS SPLITS TIMEOUT TIMEOUT-FACTOR`, to create a forceable
thunk `out`. That thunk can be forced as
* `gg-force --jobs N --engine local out` (local machine)
* `gg-force --jobs N --engine lambda out` (AWS lambda)
