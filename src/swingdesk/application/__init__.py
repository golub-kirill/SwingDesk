"""Orchestration: the daily run, assembled from the layers below it.

Owns sequencing, not rules. Every rule it applies belongs to a layer underneath; what lives here is
the order those layers run in and what happens between them.

Separate from `presentation` because it has more than one caller. The CLI runs it live; the replay
harness in `validation` runs it against a recorded snapshot to check the output still hashes the
same. A pipeline sitting in the top layer cannot be imported by either without inverting the
dependency chain, which is what forced this package into existence.
"""
