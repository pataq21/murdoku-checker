from murdoku_checker.apps.pool_generator.candidate_rules import iter_candidate_rules
from murdoku_checker.domain import Rule, Solution


def generate_pool(solution: Solution) -> list[Rule]:
    """Return only candidate clues whose evaluate method accepts the target."""
    return [
        rule for rule in iter_candidate_rules(solution) if rule.evaluate(solution)
    ]
