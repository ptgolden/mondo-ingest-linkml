from mondo_source.problems import Problem, Problems


def test_problems_print_sorted_in_columns_with_their_number():
    problems = Problems(
        [
            Problem("EX:2", "parents", "No:1", "no prefix in the prefix map"),
            Problem("EX:10", "label", "(missing)", "Field required"),
            Problem("EX:2", "parents", "No:1", "no prefix in the prefix map"),
        ]
    )

    assert str(problems).splitlines() == [
        "EX:10  label    (missing)  Field required",
        "EX:2   parents  No:1       no prefix in the prefix map",
        "2 problems",
    ]
