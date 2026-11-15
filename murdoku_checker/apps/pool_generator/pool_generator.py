from murdoku_checker.apps.pool_generator.candidate_rules import iter_candidate_rules
from murdoku_checker.domain import Rule, Solution


def generate_pool(solution: Solution) -> dict[str, list[Rule]]:
    """Return true candidate clues grouped by their protagonist."""
    pool = {person: [] for person in sorted(solution.placements)}
    for rule in iter_candidate_rules(solution):
        if rule.evaluate(solution):
            pool[rule.person].append(rule)
    return pool
