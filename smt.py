#!/usr/bin/env python3

import pygg
import subprocess as sub
import enum
import re
import os
import functools as ft
import time
from typing import List, Optional
import pdb 

gg = pygg.init()

SOLVE = f"{os.path.split(os.path.abspath(__file__))[0]}/cvc5"
SPLIT = f"{os.path.split(os.path.abspath(__file__))[0]}/cvc5"
SAT_REGEX = "^sat$"
UNSAT_REGEX = "^unsat$"
UNKNOWN_REGEX = "^unknown$"

gg.install(SOLVE)
#gg.install(SPLIT)


class Result(enum.Enum):
    SAT = "sat"
    UNSAT = "unsat"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


def merge_query_and_cube(base_query_path: str, cube_path: str) -> str:
    # skip if contains expected result .
    OUTPUT_PATH = "merged.smt2"
    with open(OUTPUT_PATH, "w") as fout:
        with open(base_query_path) as fin:
            for l in fin.readlines():
                if "check-sat" not in l and ":status" not in l and "(exit)" not in l:
                    fout.write(l)
            with open(cube_path) as fcube:
                fout.write("(assert ")
                fout.write(fcube.read().strip())
                fout.write(")\n")
            fout.write("(check-sat)")
    return OUTPUT_PATH


def base_solve(smt2_path: str, timeout: float) -> Result:
    args = [gg.bin(SOLVE).path(), "--lang", "smt2", smt2_path]
    try:
        r = sub.run(args, stdout=sub.PIPE, stderr=sub.STDOUT, timeout=timeout)
        if r.returncode == 0:
            o = r.stdout.decode()
            if re.search(SAT_REGEX, o) is not None:
                return Result.SAT
            elif re.search(UNSAT_REGEX, o) is not None:
                return Result.UNSAT
            elif re.search(UNKNOWN_REGEX, o) is not None:
                return Result.UNKNOWN
            else:
                print(r.stdout.decode())
                raise Exception("Could not find 'sat' or 'unsat'")
        else:
            print(r.stdout.decode())
            raise Exception(f"Bad return code: {r.returncode}")
    except sub.TimeoutExpired:
        return Result.TIMEOUT


def split(orig_cube: pygg.Value, merged_path: str, splits: int) -> (List[str], bool):
    CUBES = "cubes"
    r = sub.run(
        [gg.bin(SPLIT).path(), merged_path, "--lang", "smt2", "--write-partitions-to", CUBES, "--compute-partitions", str(splits)],
        check=True, stdout=sub.PIPE, stderr=sub.STDOUT
    )
    o = r.stdout.decode()
    if re.search(SAT_REGEX, o) is not None:
        os.remove(CUBES)
        return [], True
    cubes = []
    with open(CUBES) as f:
        subsolves = []
        orig_cube = orig_cube.as_str().strip()
        for line in f.readlines():
            line = line.strip()
            if len(line) > 0:
                cubes.append(f"(and {orig_cube} {line})\n")
    os.remove(CUBES)
    while len(cubes) < splits:
        cubes.append("false\n")
    if len(cubes) > splits:
        raise Exception(f"Wanted {splits} cubes but got {len(cubes)} cubes from the splitter.")
    return cubes, False


@gg.thunk_fn()
def solve_cube(
    query: pygg.Value,
    cube: pygg.Value,
    initial_splits: int,
    splits: int,
    timeout: float,
    timeout_factor: float,
) -> pygg.Output:
    """Solve a (query, cube) pair"""
    merged_path = merge_query_and_cube(query.path(), cube.path())
    try:
        # Attempt solve, if no initial splits
        if initial_splits == 0:
            r = base_solve(merged_path, timeout)
            if r != Result.TIMEOUT and r != Result.UNKNOWN:
                return gg.str_value(str(r.value))
        # Fallback to splitting
        splits_now = initial_splits if initial_splits > 0 else splits
        next_timeout = timeout if initial_splits == 0 else timeout * timeout_factor
        new_cubes, sat = split(cube, merged_path, splits_now)
        if sat:
            return gg.str_value(str(Result.SAT.value))
        subsolves = [
            gg.thunk(
                solve_cube,
                query,
                gg.str_value(new_cube),
                0,
                splits,
                next_timeout,
                timeout_factor,
            )
            for new_cube in new_cubes
        ]
        return ft.reduce(lambda a, b: gg.thunk(merge_fut, a, b), subsolves)
    finally:
        os.remove(merged_path)


@gg.thunk_fn()
def solve(
    query: pygg.Value,
    initial_splits: int,
    splits: int,
    timeout: float,
    timeout_factor: float,
) -> pygg.Output:
    """Solve a query"""
    null_cube = gg.str_value("true\n")
    return gg.thunk(
        solve_cube, query, null_cube, initial_splits, splits, timeout, timeout_factor
    )


@gg.thunk_fn()
def merge(res_a: pygg.Value, res_b: pygg.Value) -> pygg.Output:
    """Combine SAT and UNSAT answers to subproblems"""
    if (
        res_a.as_str().strip().lower() == Result.SAT.value
        or res_b.as_str().strip().lower() == Result.SAT.value
    ):
        return gg.str_value(Result.SAT.value)
    else:
        return res_a


@gg.thunk_fn()
def merge_fut(a: Optional[pygg.Value], b: Optional[pygg.Value]) -> pygg.Output:
    """Combine SAT and UNSAT answers to subproblems"""
    if a is not None and a.as_str().strip().lower() == Result.SAT.value:
        return a
    elif b is not None and b.as_str().strip().lower() == Result.SAT.value:
        return b
    elif a is None or b is None:
        return gg.this()  # Could not reduce
    else:
        print(a.as_str(), "merge with", b.as_str())
        assert a.as_str().strip().lower() == Result.UNSAT.value and b.as_str().strip().lower() == Result.UNSAT.value
        return a


gg.main()
