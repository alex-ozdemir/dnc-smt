#!/usr/bin/env bash

export PYTHONPATH=/homes/haozewu/CnC/gg/gg/tools/pygg/:/homes/haozewu/ParallelSMT/dnc-smt/:$PYTHONPATH
PATH=/homes/haozewu/CnC/gg/frontend:$PATH

source /homes/haozewu/py3.6/bin/activate

python /homes/haozewu/ParallelSMT/dnc-smt/runner.py "$@"
#p=$1
#./smt.py init solve $p 3 4 60 1.5
#gg-force out
#echo $(cat out)


deactivate
