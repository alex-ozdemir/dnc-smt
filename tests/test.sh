#!/usr/bin/env sh

set -ex

export PYTHONPATH=/homes/haozewu/CnC/gg/gg/tools/pygg/:$PYTHONPATH
PATH=/homes/haozewu/CnC/gg/frontend:$PATH

source /homes/haozewu/py3.6/bin/activate


function runtest {
  p=$1
  res=$2
  env PATH="$PATH:.." ../smt.py init solve $p 4 4 1 1.5
  gg-force out
  if [[ $res == $(cat out) ]]
  then
    echo pass: $p is $res
  else
    echo fail: $p should be $res but is $(cat out)
    exit 1
  fi
}

runtest ./smt2/sat.smt2 SAT
runtest ./smt2/unsat.smt2 UNSAT


deactivate
