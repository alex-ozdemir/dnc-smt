#!/usr/bin/env python3

import pygg
import subprocess as sub
import enum
import re
import os
import functools as ft
import time

gg = pygg.init()

SOLVE = "cvc4"
SPLIT = f"{os.path.split(os.path.abspath(__file__))[0]}/split.py"
SAT_REGEX = "^sat$"
UNSAT_REGEX = "^unsat$"

gg.install(SOLVE)
gg.install(SPLIT)


class Result(enum.Enum):
    SAT = "SAT"
    UNSAT = "UNSAT"
    TIMEOUT = "TIMEOUT"


def merge_query_and_cube(base_query_path: str, cube_path: str) -> str:
    OUTPUT_PATH = "merged.cnf"
    with open(OUTPUT_PATH, "w") as fout:
        with open(base_query_path) as fin:
            for l in fin.readlines():
                if "check-sat" not in l:
                    fout.write(l)
            with open(cube_path) as fcube:
                fout.write("(assert ")
                fout.write(fcube.read().strip())
                fout.write(")\n")
            fout.write("(check-sat)")
    return OUTPUT_PATH


def base_solve(smt2_path: str, timeout: float) -> Result:
    args = [gg.bin(SOLVE).path(), "--lang", "smt2", smt2_path]
    print(f"waiting 1s before solving: {os.path.abspath(smt2_path)}")
    time.sleep(1)
    try:
        r = sub.run(args, stdout=sub.PIPE, stderr=sub.STDOUT, timeout=timeout)
        if r.returncode == 0:
            o = r.stdout.decode()
            if re.search(SAT_REGEX, o) is not None:
                return Result.SAT
            elif re.search(UNSAT_REGEX, o) is not None:
                return Result.UNSAT
            else:
                print(r.stdout.decode())
                raise Exception("Could not find 'sat' or 'unsat'")
        else:
            print(r.stdout.decode())
            raise Exception(f"Bad return code: {r.returncode}")
    except sub.TimeoutExpired:
        return Result.TIMEOUT


@gg.thunk_fn()
def solve_cube(
    query: pygg.Value,
    cube: pygg.Value,
    initial_splits: int,
    splits: int,
    timeout: float,
    timeout_factor: float,
) -> pygg.Output:
    """ Solve a (query, cube) pair """
    merged_path = merge_query_and_cube(query.path(), cube.path())
    try:
        # Attempt solve, if no initial splits
        if initial_splits == 0:
            r = base_solve(merged_path, timeout)
            if r != Result.TIMEOUT:
                return gg.str_value(str(r.name))
        # Fallback to splitting
        splits_now = initial_splits if initial_splits > 0 else splits
        next_timeout = timeout if initial_splits == 0 else timeout * timeout_factor
        CUBES = "cubes"
        sub.run(
            [gg.bin(SPLIT).path(), merged_path, "-o", CUBES, "-n", str(splits_now)],
            check=True,
        )
        with open(CUBES) as f:
            subsolves = []
            orig_cube = cube.as_str().strip()
            for l in f.readlines():
                l = l.strip()
                if len(l) > 0:
                    merged_cube = gg.str_value(f"(and {orig_cube} {l})\n")
                    subsolves.append(
                        gg.thunk(
                            solve_cube,
                            query,
                            merged_cube,
                            0,
                            splits,
                            next_timeout,
                            timeout_factor,
                        )
                    )
        os.remove(CUBES)
        return ft.reduce(lambda a, b: gg.thunk(merge, a, b), subsolves)
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
    """ Solve a query """
    null_cube = gg.str_value("true\n")
    return gg.thunk(
        solve_cube, query, null_cube, initial_splits, splits, timeout, timeout_factor
    )


@gg.thunk_fn()
def merge(res_a: pygg.Value, res_b: pygg.Value) -> pygg.Output:
    """ Combine SAT and UNSAT answers to subproblems """
    if (
        res_a.as_str().strip() == Result.SAT.name
        or res_b.as_str().strip() == Result.SAT.name
    ):
        return gg.str_value(Result.SAT.name)
    else:
        return res_a


gg.main()
