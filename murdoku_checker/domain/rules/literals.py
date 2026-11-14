from collections.abc import Sequence

from ortools.sat.python import cp_model, cp_model_helper

BoolLiteral = cp_model_helper.Literal


def any_of_literal(
    model: cp_model.CpModel, operands: Sequence[BoolLiteral]
) -> cp_model.IntVar:
    """Boolean variable that is true exactly when any operand is true."""
    literal = model.new_bool_var("")
    model.add_bool_or(operands).only_enforce_if(literal)
    model.add_bool_and([operand.negated() for operand in operands]).only_enforce_if(
        literal.negated()
    )
    return literal


def all_of_literal(
    model: cp_model.CpModel, operands: Sequence[BoolLiteral]
) -> cp_model.IntVar:
    """Boolean variable that is true exactly when every operand is true."""
    literal = model.new_bool_var("")
    model.add_bool_and(operands).only_enforce_if(literal)
    model.add_bool_or([operand.negated() for operand in operands]).only_enforce_if(
        literal.negated()
    )
    return literal
