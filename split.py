#!/usr/bin/env python3

import argparse
import itertools as it

parser = argparse.ArgumentParser(
    description="Pretend to split an SMT2 query",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument(
    "query", metavar="SMT2-FILE", type=str, help="SMT2 file containing the query"
)
parser.add_argument(
    "-o", "--output", default="out.smt2.cubes", help="path to write cubes to"
)
parser.add_argument("-n", "--number", type=int, default=2, help="number of cubes")

def main():
    args = parser.parse_args()
    with open(args.output, "w") as f:
        for i in range(args.number):
            # Give syntactically different cubes to defeat gg's cache
            f.write(f"(and {' '.join(it.repeat('true', i + 1))})\n")
main()
