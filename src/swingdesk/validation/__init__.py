"""Harnesses that check the system against a reference rather than against a market.

Backtest, walk-forward, robustness and forward test are the eventual occupants. What is here now is
the pair that guards behaviour over time: `golden` (frozen input/output vectors per component) and
`replay` (a stored manifest must reproduce its output hash).

Both sit above `application` because both drive the same run the CLI drives. A harness running its
own private version of the pipeline would be checking something other than what ships.
"""
