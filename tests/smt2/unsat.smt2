(set-logic QF_UF)
(declare-const a Bool)
(assert (and a (not a)))
(check-sat)
