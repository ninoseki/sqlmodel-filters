from sqlmodel.sql.expression import Select


def compile_with_literal_binds(s: Select):
    return s.compile(compile_kwargs={"literal_binds": True})
