from os import makedirs, listdir
from os.path import exists, abspath, dirname, join, split
from abc import abstractmethod, ABC
from typing import Any, List, Dict, TypeVar, Generic, Optional
from shutil import rmtree
from time import time
from pprint import pprint
from copy import deepcopy

DATA_DIR = "data"
OUTFILE = "output.csv"
RUN_DIR = "exp_runner"

SDict = Dict[str, str]


class Observation(ABC):
    @staticmethod
    @abstractmethod
    def fields() -> List[str]:
        pass

    @staticmethod
    @abstractmethod
    def default_values() -> SDict:
        pass

    @abstractmethod
    def values(self) -> SDict:
        pass


O = TypeVar("O", bound=Observation)


class Input(Observation, Generic[O]):
    @abstractmethod
    def run(self, working_dir: str) -> O:
        pass


I = TypeVar("I", bound=Input)


class Runner(Generic[I, O]):
    input_fields: List[str]
    output_fields: List[str]
    fields: List[str]
    extra_outputs: List[str] = ["start_time", "end_time", "hostname"]
    defaults: SDict
    extra_defaults: SDict = {"start_time": "0", "end_time": "0", "hostname": "unknown"}
    script_dir: str
    tmp_dir: str

    def __init__(self, script_dir: str, I: Any, O: Any, tmp_dir: str):
        self.input_fields = I.fields()
        self.output_fields = O.fields() + self.extra_outputs
        assert set(self.input_fields).isdisjoint(set(self.output_fields))
        self.fields = self.input_fields + self.output_fields
        self.defaults = dict(
            I.default_values(), **O.default_values(), **self.extra_defaults
        )
        self.script_dir = script_dir
        self.tmp_dir = join(tmp_dir, RUN_DIR)
        assert all(Runner.safe_str(f) for f in self.fields)

    @staticmethod
    def safe_str(s: str) -> bool:
        return "," not in s and ";" not in s and "\n" not in s and len(s) > 0

    def find_output(self, i: I) -> Optional[str]:
        encs = self.encodings(i)
        extant_encs = [self.outfile(d) for d in encs if exists(self.outfile(d))]
        assert len(extant_encs) < 2
        return extant_encs[0] if len(extant_encs) > 0 else None

    def rundir(self, encoded_inputs: str) -> str:
        return join(self.tmp_dir, encoded_inputs)

    def outfile(self, encoded_inputs: str) -> str:
        return join(self.script_dir, DATA_DIR, encoded_inputs, OUTFILE)

    def load(self, p: str) -> SDict:
        header, values = open(p, "r").read().strip().split()
        vs = {k: v for k, v in zip(header.split(","), values.split(","))}
        self.complete(vs)
        return vs

    def find_result(self, i: I) -> Optional[SDict]:
        o = self.find_output(i)
        if o is None:
            return None
        return self.load(o)

    def complete(self, s: SDict) -> None:
        for f in self.fields:
            if f not in s:
                s[f] = self.defaults[f]

    @staticmethod
    def hostname() -> str:
        try:
            return open("/etc/hostname").read().strip()
        except:
            return "unknown"

    def list(self):
        print(",".join(self.fields))
        d = join(self.script_dir, DATA_DIR)
        if exists(d):
            for n in listdir(d):
                p = join(self.script_dir, DATA_DIR, n, OUTFILE)
                if exists(p):
                    vs = self.load(p)
                    print(",".join(vs[f] for f in self.fields))

    def run(self, i: I) -> SDict:
        r = self.find_result(i)
        if r is None:
            rr = {"start_time": str(time())}
            e = self.encodings(i)[0]
            makedirs(self.rundir(e), exist_ok=True)
            wd = self.rundir(e)
            rr.update(**i.values())
            o = i.run(wd)
            rr.update(**o.values())
            if "hostname" not in rr:
                rr["hostname"] = Runner.hostname()
            if "end_time" not in rr:
                rr["end_time"] = str(time())
            self.complete(rr)
            makedirs(split(self.outfile(e))[0], exist_ok=True)
            with open(self.outfile(e), "w") as f:
                f.writelines(
                    [
                        ",".join(self.fields),
                        "\n",
                        ",".join(rr[f] for f in self.fields),
                        "\n",
                    ]
                )
            rmtree(wd)
            r = self.find_result(i)
            assert r is not None
        self.complete(r)
        return r

    @staticmethod
    def check_values(values: SDict) -> None:
        assert all(Runner.safe_str(v) for v in values.values())

    def encodings(self, i: I) -> List[str]:
        inputs = i.values()
        l = [inputs[s] for s in self.input_fields]
        os = [deepcopy(l)]
        while len(l) > 0 and self.input_fields[len(l) - 1] in self.defaults and self.defaults[self.input_fields[len(l) - 1]] == l[-1]:
            l.pop()
            os.append(deepcopy(l))
        return [",".join(o) for o in os]
