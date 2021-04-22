#!/usr/bin/env zsh

set -ex

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

