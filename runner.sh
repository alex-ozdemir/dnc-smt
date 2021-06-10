#!/usr/bin/env bash

export GG_THUNK_EXECUTE_TEMPLATE=/export/stanford/barrettlab/parallel-smt/
export PYTHONPATH=/homes/haozewu/ParallelSMT/dnc-smt/gg/tools/pygg/:/homes/haozewu/ParallelSMT/dnc-smt/:$PYTHONPATH
PATH=/homes/haozewu/ParallelSMT/dnc-smt/frontend:$PATH

source /homes/haozewu/py3.6/bin/activate

python /homes/haozewu/ParallelSMT/dnc-smt/runner.py "$@"
#p=$1
#./smt.py init solve $p 3 4 60 1.5
#gg-force out
#echo $(cat out)


deactivate
