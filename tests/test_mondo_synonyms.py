import curies

from mondo_source.datamodel import Synonym, SynonymScope, Term
from mondo_source.identifiers import Identifiers
from mondo_source.mondo_synonyms import bracket_stripped, mondo_synonyms

IDENTIFIERS = Identifiers(
    frozenset(),
    curies.Converter.from_prefix_map({"mondo_vocab": "http://purl.obolibrary.org/obo/mondo#"}),
)
FROM_LABEL, GENERATED = "mondo_vocab:GENERATED_FROM_LABEL", "mondo_vocab:GENERATED"


def term(label: str, *exact: str, related: str | None = None, deprecated: bool = False) -> Term:
    synonyms = [Synonym(text=text, scope=SynonymScope.EXACT) for text in exact]
    if related:
        synonyms.append(Synonym(text=related, scope=SynonymScope.RELATED))
    return Term(id="EX:1", label=label, synonyms=synonyms, deprecated=deprecated)


def added(term: Term, strip_brackets: bool = False) -> list[tuple[str, str, str | None]]:
    synonyms = mondo_synonyms(term, IDENTIFIERS, strip_brackets)
    return sorted((s.text, s.scope, s.synonym_type) for s in synonyms)


def test_the_label_becomes_an_exact_synonym():
    assert added(term("Leprosy", "Leprosy")) == [("Leprosy", "EXACT", FROM_LABEL)]


def test_a_deprecated_terms_label_does_not():
    assert added(term("Leprosy", deprecated=True)) == []


def test_bracket_stripped_names_are_added_only_when_asked_for():
    leprosy = term("Leprosy [Hansen disease]", deprecated=True)

    assert added(leprosy) == []
    assert added(leprosy, strip_brackets=True) == [("leprosy", "EXACT", GENERATED)]


def test_a_final_bracketed_part_is_stripped_from_the_label_and_exact_synonyms():
    leprosy = term("Leprosy [Hansen disease]", "Lepra (A30)", "LEPROSY (ALL FORMS)", related="Hansen's (old)")

    assert bracket_stripped(leprosy) == {"leprosy", "lepra"}


def test_a_bracket_that_does_not_end_the_text_is_kept():
    assert bracket_stripped(term("Type (I) disease")) == set()


def test_a_final_bracket_with_no_space_before_it_is_only_lowercased():
    assert bracket_stripped(term("Pericytoma with t(7;12)")) == {"pericytoma with t(7;12)"}


def test_a_term_without_a_label_gets_only_what_its_exact_synonyms_give():
    unnamed = Term(id="EX:1", deprecated=True, synonyms=[Synonym(text="Lepra (A30)", scope=SynonymScope.EXACT)])

    assert added(unnamed, strip_brackets=True) == [("lepra", "EXACT", GENERATED)]
