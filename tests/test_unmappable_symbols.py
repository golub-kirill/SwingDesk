"""Which directory symbols the price vendor has no form for, and which ones only LOOK like them.

**Owner instruction 2026-09-05: skip what we cannot fetch at all.** `universe.UNMAPPABLE_SUFFIXES`
has named `.W`, `.U` and `.R` since it was written, `vendor_symbol` refuses to translate them, and
the coverage pass asked the vendor for them anyway - spending budget every week to be told
"possibly delisted", and leaving a shortfall that made its closing line promise a convergence which
could not happen.

**The test that matters most is `test_a_served_warrant_is_NOT_excluded`**, because it pins the
generalisation that measurement refused. Excluding warrants, units and rights by the vendor's own
Security Name looks obviously right and is wrong: of the eligible directory, 938 names say
warrant/unit/right and **738 of them already have bars**. `AB` is "AllianceBernstein Holding L.P.
Units" and is an ordinary NYSE listing. The CLASS is served; one SPELLING of it is not, and the
difference is the whole rule.
"""

from __future__ import annotations

import pytest

from swingdesk.reference_data.universe import UNMAPPABLE_SUFFIXES, is_mappable, vendor_symbol


@pytest.mark.parametrize("symbol", ["ACHR.W", "AAC.U", "AIIA.R"])
def test_a_symbol_with_no_vendor_form_is_not_mappable(symbol):
    """133 eligible symbols carry these suffixes and not one has ever had a bar stored."""
    assert not is_mappable(symbol)


@pytest.mark.parametrize("symbol", ["AACIW", "AACIU", "AACPR", "AB"])
def test_a_served_warrant_is_NOT_excluded(symbol):
    """The generalisation measurement refused.

    `AACIW` is "Armada Acquisition Corp. III - Warrant" and the vendor serves it. A rule reading
    the Security Name, or one matching a bare trailing W/U/R, would drop it and 737 others.
    """
    assert is_mappable(symbol)


@pytest.mark.parametrize("symbol", ["LOW", "UNIT", "WU", "RUN"])
def test_a_bare_trailing_letter_is_never_the_test(symbol):
    """`LOW` ends in W. Any rule that reads the last letter alone drops real, liquid names."""
    assert is_mappable(symbol)


def test_mappability_and_translation_agree():
    """`vendor_symbol` returns an unmappable symbol UNCHANGED, which is why the predicate exists.

    The result of the translation cannot answer the question - `ACHR.W` in and `ACHR.W` out looks
    exactly like a symbol that needed no translation, and that is how the fetch loop came to ask
    for a form the vendor does not use.
    """
    assert vendor_symbol("ACHR.W") == "ACHR.W"
    assert not is_mappable("ACHR.W")

    # A mappable dotted symbol is translated, and that is the case the suffix test must not catch.
    assert vendor_symbol("BRK.B") == "BRK-B"
    assert is_mappable("BRK.B")


def test_the_suffixes_are_the_ones_the_constant_declares():
    """The predicate reads the constant rather than restating it (`AGENTS.md` section 10.5)."""
    for suffix in UNMAPPABLE_SUFFIXES:
        assert not is_mappable(f"TEST.1{suffix}")
