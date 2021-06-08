#!/usr/bin/env python3

"""gg-Marabou test runner

Usage:
  runner.py run [options] <benchmark>
  runner.py list
  runner.py (-h | --help)

Options:
  --working-dir DIR     Where to run the experiments [default: /export/stanford/barrettlab/parallel-smt]
  --jobs N              The number of jobs [default: 1]
  --initial-divides N   The initial number of divides [default: 0]
  --online-divides N    The number of divides to do on timeout [default: 2]
  --future-mode BOOL    The divide strategy [default: false]
  --timeout N           How long to try for (s) [default: 3600]
  --initial-timeout N   How long to try for (s) before splitting [default: 5]
  --timeout-factor F    How long to multiply the initial_timeout by each split [default: 1.5]
  --infra I             gg-local, gg-lambda, cnc-lingeling, painless, plingeling, cadical, parac [default: gg-local]
  --painless-mode M     default, dnc [default: default]
  --trial N             the trial number to run [default: 0]
  -h --help             Show this screen.
"""

from exp import Observation, Input, Runner, SDict

from docopt import docopt
from glob import glob
from typing import Any, List, NamedTuple, Optional
from os import environ
from os.path import exists, abspath, dirname, join, basename, split
from pprint import pprint
from re import match
import re
import shutil
import subprocess as sub
from time import time
import socket
from random import randint

SCRIPT_DIR = abspath(dirname(abspath(__file__)))
BENCHMARKS_DIR = f"{SCRIPT_DIR}/smtlib"
REPO_DIR = split(SCRIPT_DIR)[0]
# TODO search for sat on a new line
# TODO deal with lower/uppercase sat/unsat
SAT_RE = re.compile("sat")
UNSAT_RE = re.compile("unsat")
TIMEOUT = "TIMEOUT"

def which(s: str) -> str:
    r = shutil.which(s)
    assert r is not None
    return r


CNC_PATH = abspath(join(SCRIPT_DIR, "smt.py"))
CVC_PATH = abspath("/homes/haozewu/ParallelSMT/dnc-smt/cvc5")
FORCE_PATH = which("gg-force")

environ["PATH"] = f"{CVC_PATH}" + environ["PATH"]


def returncode_to_result(r: int) -> Optional[str]:
    if r == 10:
        return "sat"
    elif r == 20:
        return "unsat"
    else:
        return None


def main() -> None:
    arguments = docopt(__doc__)
    r = Runner(SCRIPT_DIR, CncInput, CncOutput, arguments['--working-dir'])  # type: Runner[CncInput, CncOutput]
    assert arguments["--painless-mode"] in ["default", "dnc"]
    if arguments["run"]:
        arguments["--benchmark"] = basename(search(arguments["<benchmark>"]))
        a = CncInput(arguments)
        res = r.run(a)
        pprint(res)
    elif arguments["list"]:
        r.list()
    else:
        print("Missing command!")


def argize(s: str) -> str:
    assert match("[a-z0-9_]*", s)
    return "--" + s.replace("_", "-")


def parse(ty: type, s: str) -> Any:
    if ty == str or ty == int or ty == float:
        return ty(s)
    elif ty == bool:
        if s.lower() == "true":
            return True
        elif s.lower() == "false":
            return False
        else:
            raise ValueError(f"Invalid boolean: '{s}' (True and False are acceptable)")
    else:
        raise ValueError(f"Unparsable type: {ty} for '{s}'")


def search(s: str) -> str:
    #print(BENCHMARKS_DIR)
    r = glob(f"{BENCHMARKS_DIR}/**/*{s}*", recursive=True)
    if len(r) == 1:
        return r[0]
    elif len(r) == 0:
        print(f"No benchmark found containing '{s}'")
        exit(1)
    else:
        print(f"Multiple benchmarks found:")
        for f in r:
            print(f"  {f}")
        exit(1)


class CncOutput(Observation):
    duration: float
    result: str
    family: str

    def __init__(self, result: str, duration: float, family: str):
        for attr, ty in self.__annotations__.items():
            self.__setattr__(attr, locals()[attr])

    @staticmethod
    def default_values() -> SDict:
        return {}

    def values(self) -> SDict:
        return {attr: str(self.__getattribute__(attr)) for attr in self.__annotations__}

    @staticmethod
    def fields() -> List[str]:
        return [
            "duration",
            "result",
            "family",
        ]


class CncInput(Input[CncOutput]):
    benchmark: str
    jobs: int
    infra: str
    initial_divides: int
    online_divides: int
    initial_timeout: float
    timeout_factor: float
    timeout: int
    future_mode: bool
    trial: int
    painless_mode: str

    def __init__(self, args):
        for attr, ty in self.__annotations__.items():
            self.__setattr__(attr, parse(ty, args[argize(attr)]))

    @staticmethod
    def default_values() -> SDict:
        return { "painless_mode": "default"
                }

    def values(self) -> SDict:
        return {attr: str(self.__getattribute__(attr)) for attr in self.__annotations__}

    @staticmethod
    def fields() -> List[str]:
        return [
            "benchmark",
            "jobs",
            "infra",
            "initial_divides",
            "online_divides",
            "initial_timeout",
            "timeout_factor",
            "timeout",
            "future_mode",
            "trial",
            "painless_mode",
        ]

    def run_lambda(self, working_dir: str) -> CncOutput:
        assert self.infra in ["gg-local", "gg-lambda"]
        path = search(self.benchmark)

        if ".bz2" in path:
            tmp_cnf_path = f"{working_dir}/tmp.cnf"
            sub.run("bzcat {} > {}".format(path, tmp_cnf_path), shell=True)
        else:
            tmp_cnf_path = path

        family = basename(dirname(path))
        sub.run(
            [
                CNC_PATH,
                "init",
                "solve",
                tmp_cnf_path,
                str(self.initial_divides),
                str(self.online_divides),
                str(self.initial_timeout),
                str(self.timeout_factor),
            ],
            check=True,
            cwd=working_dir
        )
        eng = self.infra.split("-")[1]

        s = time()
        try:
            OUTFILE = "out"
            sub.run(
                [FORCE_PATH, "--jobs", str(self.jobs), "--engine", eng, OUTFILE],
                check=True,
                cwd=working_dir,
                timeout=(self.timeout)
            )
            o = open(join(working_dir, OUTFILE)).read().strip()
            assert len(o) < 20 and Runner.safe_str(o)
            result = o
        except sub.TimeoutExpired as e:
            result = TIMEOUT

        duration = time() - s

        print(join(working_dir, ".gg"))
        return CncOutput(result=result, duration=duration, family=family)

    def run_solver(self, args: List[str], working_dir: str) -> CncOutput:
        path = search(self.benchmark)
        family = basename(dirname(path))
        s = time()
        try:
            r = sub.run(args, cwd=working_dir, stdout=sub.PIPE,timeout=self.timeout)
            o = r.stdout.decode()
            if UNSAT_RE.search(o) is not None:
                result = "unsat"
            elif SAT_RE.search(o) is not None:
                result = "sat"
            else:
                print(f"Cannot parse output:\n{o}")
                raise ValueError("Cannot parse output")
        except sub.TimeoutExpired as e:
            result = TIMEOUT

        duration = time() - s
        return CncOutput(result=result, duration=duration, family=family)

    def run(self, working_dir: str) -> CncOutput:
        path = search(self.benchmark)
        if self.infra in ["gg-local", "gg-lambda"]:
            return self.run_lambda(working_dir)
        elif self.infra in ["cnc-lingeling"]:
            return self.run_cnc_lingeling(working_dir)
        elif self.infra in ["plingeling"]:
            return self.run_solver([PLINGELING_PATH, path, str(self.jobs)], working_dir)
        elif self.infra in ["cvc"]:
            return self.run_solver([CVC_PATH, path], working_dir)
        elif self.infra in ["cadical"]:
            return self.run_solver([CADICAL_PATH, path], working_dir)
        elif self.infra in ["parac"]:
            return self.run_parac(working_dir)
        elif self.infra in ["painless"]:
            mode_flag = "-wkr-strat=" + ("4" if self.painless_mode == "dnc" else "1")
            if ".bz2" in path:
                tmp_cnf_path = f"{working_dir}/tmp.cnf"
                sub.run("bzcat {} > {}".format(path, tmp_cnf_path), shell=True)
            else:
                tmp_cnf_path = path
            return self.run_solver([PAINLESS_PATH, tmp_cnf_path, f"-c={self.jobs}", mode_flag], working_dir)
        else:
            print(f"Invalid infra: {self.infra}")
            exit(1)


if __name__ == "__main__":
    main()
