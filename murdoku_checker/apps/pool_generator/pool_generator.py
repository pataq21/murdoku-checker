from murdoku_checker.apps.pool_generator.candidate_rules import iter_candidate_rules
from murdoku_checker.domain import AnyOfRule, Rule, Solution


def generate_pool(
    solution: Solution, *, victim: str | None = None
) -> dict[str, list[Rule]]:
    """Return true clues, keeping disjunctions with exactly one true condition."""
    pool = {person: [] for person in sorted(solution.placements) if person != victim}
    for rule in iter_candidate_rules(solution, victim=victim):
        accepted = (
            sum(condition.evaluate(solution) for condition in rule.conditions) == 1
            if isinstance(rule, AnyOfRule)
            else rule.evaluate(solution)
        )
        if accepted:
            pool[rule.person].append(rule)
    return pool
