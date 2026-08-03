"""Study computations: pure, so a study's arithmetic is testable without fetching anything.

Each module here answers one pre-registered question and nothing else. Orchestration - fetching,
storing, writing the result - lives in a tool, because a study that reaches the network cannot be
run in CI and cannot be replayed.
"""
