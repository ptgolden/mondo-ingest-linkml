"""The synonyms Mondo adds to a source's terms, typed as generated so that the
release shows what Mondo added rather than the source said."""

import re

from mondo_source.datamodel import Synonym, SynonymScope, Term
from mondo_source.identifiers import Identifiers, SlotPath

SYNONYM_TYPE: SlotPath = ("synonyms", "synonym_type")
GENERATED_FROM_LABEL = "http://purl.obolibrary.org/obo/mondo#GENERATED_FROM_LABEL"
GENERATED = "http://purl.obolibrary.org/obo/mondo#GENERATED"

# "\Z", not "$": the end of the text, as in the SPARQL these came from, and not also
# before a final newline.
ENDS_IN_BRACKET = re.compile(r"[\])]\Z")
FINAL_BRACKETED_PART = re.compile(r" [\[(].*[)\]]\Z")


def generated(text: str, synonym_type: str, identifiers: Identifiers) -> Synonym:
    """An EXACT synonym of one of Mondo's two types, given as its IRI."""
    return Synonym(text=text, scope=SynonymScope.EXACT, synonym_type=identifiers.curie(synonym_type, SYNONYM_TYPE))


def bracket_stripped(term: Term) -> set[str]:
    """The label and each exact synonym of a term that end in ")" or "]", lowercased
    and without the final bracketed part (mondo-ingest's fix-labels-with-brackets.ru):
    "Leprosy [Hansen disease]" gives "leprosy".

    As there, the part goes only if a space comes before its opening bracket:
    "pericytoma with t(7;12)" is lowercased and nothing more.
    """
    exact = [synonym.text for synonym in term.synonyms or [] if synonym.scope == SynonymScope.EXACT]
    bracketed = [text for text in (term.label, *exact) if ENDS_IN_BRACKET.search(text)]
    return {FINAL_BRACKETED_PART.sub("", text.lower()) for text in bracketed}


def mondo_synonyms(term: Term, identifiers: Identifiers, strip_brackets: bool) -> list[Synonym]:
    """The synonyms Mondo adds to a term, all EXACT:

    - the label of a term that isn't deprecated, typed mondo:GENERATED_FROM_LABEL
      (mondo-ingest's exact_syn_from_label.ru), for every source;
    - bracket_stripped(), typed mondo:GENERATED, for the sources that ask for it.
    """
    from_label = [] if term.deprecated else [term.label]
    stripped = bracket_stripped(term) if strip_brackets else set()
    return [
        *(generated(text, GENERATED_FROM_LABEL, identifiers) for text in from_label),
        *(generated(text, GENERATED, identifiers) for text in stripped),
    ]
