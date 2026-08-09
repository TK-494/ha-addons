"""Parser tests.

Fixtures are synthetic: invented IBANs, invented merchants, invented amounts.
No real bank export ever enters this repository, so these tests are safe to run
anywhere and the repo stays free of personal data.

Every test here corresponds to a way real Dutch bank CSVs have actually gone
wrong, not to a hypothetical.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.parsers import ParseError, detect, parse_csv
from app.parsers.base import decode_csv_bytes, detect_decimal_sep, parse_amount_cents, parse_date

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return decode_csv_bytes((FIXTURES / name).read_bytes())


# ─── detection ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("rabobank_current.csv", "rabobank_current"),
    ("rabobank_creditcard.csv", "rabobank_creditcard"),
    ("asn.csv", "asn"),
])
def test_detects_each_layout(name, expected):
    assert detect(load(name)) == expected


def test_unknown_layout_refuses_to_guess():
    """Detection returns None rather than defaulting. Defaulting is how the
    predecessor ended up running a credit-card file through the wrong parser."""
    assert detect("kolom_a,kolom_b\n1,2\n") is None
    with pytest.raises(ParseError):
        parse_csv("kolom_a,kolom_b\n1,2\n")


# ─── the regression that motivated this rewrite ─────────────────────────────

def test_creditcard_file_is_never_parsed_as_current_account():
    """The predecessor read the card layout as its 'legacy' Rabobank layout,
    found no `Bedrag (EUR)` column, and imported every row at €0.00 with no
    error at all. Choosing the wrong format must now fail loudly."""
    with pytest.raises(ParseError) as exc:
        parse_csv(load("rabobank_creditcard.csv"), "rabobank_current")
    assert "ontbreken" in str(exc.value)


def test_no_row_silently_imports_as_zero():
    for name in ("rabobank_current.csv", "rabobank_creditcard.csv", "asn.csv"):
        result = parse_csv(load(name))
        assert result.rows, name
        assert all(r.amount_cents != 0 for r in result.rows), name


# ─── Rabobank current account ───────────────────────────────────────────────

def test_rabobank_amounts_dates_and_balance():
    result = parse_csv(load("rabobank_current.csv"))
    first = result.rows[0]
    assert first.booked_on == date(2024, 1, 2)
    assert first.amount_cents == -1234
    assert first.balance_after_cents == 98766
    assert first.bank_code == "bc"


def test_rabobank_thousands_separator():
    """`-1.234,56` is minus twelve hundred, not minus one and a bit."""
    rows = parse_csv(load("rabobank_current.csv")).rows
    assert rows[1].amount_cents == -123456


def test_rabobank_keeps_creditor_id_for_subscription_detection():
    rows = parse_csv(load("rabobank_current.csv")).rows
    assert rows[1].creditor_id == "NL00ZZZ000000000000"
    assert rows[1].mandate_ref == "M-0001"


def test_rabobank_multiple_accounts_in_one_file():
    result = parse_csv(load("rabobank_current.csv"))
    assert set(result.accounts) == {"NL00TEST0000000001", "NL00TEST0000000002"}


def test_rabobank_filler_row_skipped():
    """The zero-amount, empty-description padding row is not a transaction."""
    rows = parse_csv(load("rabobank_current.csv")).rows
    assert len(rows) == 6


def test_rabobank_cp1252_encoding():
    """Rabobank ships Windows-1252; the header contains `initiërende`."""
    text = load("rabobank_current.csv")
    as_cp1252 = text.encode("cp1252")
    with pytest.raises(UnicodeDecodeError):
        as_cp1252.decode("utf-8")
    assert "initiërende" in decode_csv_bytes(as_cp1252)


def test_undecodable_file_raises_rather_than_mangling():
    """0x81/0x8d/0x90 are undefined in CP1252 and invalid UTF-8, so nothing
    can decode this. It must fail rather than substitute replacement
    characters into a counterparty name."""
    with pytest.raises(ParseError):
        decode_csv_bytes(b"\x81\x8d\x90\x9d")


# ─── Rabobank credit card ───────────────────────────────────────────────────

def test_creditcard_basics():
    result = parse_csv(load("rabobank_creditcard.csv"))
    account = result.accounts["CC-0000"]
    assert account.kind == "credit_card"
    assert account.settlement_iban == "NL00TEST0000000001"
    assert result.rows[0].amount_cents == -299


def test_creditcard_foreign_currency_preserved():
    rows = parse_csv(load("rabobank_creditcard.csv")).rows
    fx = rows[1]
    assert fx.fx_amount_cents == -4950
    assert fx.fx_currency == "USD"
    assert fx.fx_rate == "1,1000"


def test_creditcard_cardholder_name_is_dropped():
    """`Creditcard Regel1` holds the cardholder's name. It must not survive
    into anything the app stores."""
    result = parse_csv(load("rabobank_creditcard.csv"))
    blob = " ".join(
        f"{r.description} {r.counter_name} {r.payment_ref} {r.bank_ref}" for r in result.rows
    )
    assert "ESTPERSOON" not in blob.upper()


def test_creditcard_description_whitespace_collapsed():
    rows = parse_csv(load("rabobank_creditcard.csv")).rows
    assert "  " not in rows[0].description


# ─── ASN ────────────────────────────────────────────────────────────────────

def test_asn_dates_are_dayfirst():
    """`03-04-2024` is 3 April. Read ISO-first it becomes 4 March — parses
    fine, lands in the wrong month, never raises."""
    rows = parse_csv(load("asn.csv")).rows
    assert rows[0].booked_on == date(2024, 4, 3)


def test_asn_balance_converted_from_before_to_after():
    rows = parse_csv(load("asn.csv")).rows
    assert rows[0].balance_after_cents == 20000     # 0.00 before + 200.00
    assert rows[1].balance_after_cents == 17505     # 200.00 before - 24.95


def test_asn_quotes_stripped():
    rows = parse_csv(load("asn.csv")).rows
    assert rows[0].description == "Start"


def test_asn_counterparty_address_not_retained():
    result = parse_csv(load("asn.csv"))
    blob = " ".join(f"{r.description} {r.counter_name} {r.payment_ref}" for r in result.rows)
    assert "Teststraat" not in blob and "1234AB" not in blob


def test_asn_headerless_variant():
    text = load("asn.csv")
    headerless = text.split("\n", 1)[1]
    assert detect(headerless) == "asn"
    assert len(parse_csv(headerless).rows) == 3


def test_asn_decimal_convention_decided_per_file():
    """ASN has shipped both conventions; the file decides once, not per row —
    per-row guessing is what turns `1.234` into €1.23."""
    assert detect_decimal_sep(["200,00", "-24,95"]) == ","
    assert detect_decimal_sep(["200.00", "-24.95"]) == "."
    assert detect_decimal_sep(["1.234,56", "-24,95"]) == ","


# ─── primitives ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,sep,expected", [
    ("-6,20", ",", -620),
    ("+41,09", ",", 4109),
    ("1.234,56", ",", 123456),
    ("200.00", ".", 20000),
    ("1,234.56", ".", 123456),
    ("0,145", ",", 15),          # Decimal rounds half-up; float would give 14
])
def test_parse_amount_cents(value, sep, expected):
    assert parse_amount_cents(value, sep) == expected


@pytest.mark.parametrize("value", ["", "  ", "abc", None])
def test_parse_amount_rejects_junk(value):
    with pytest.raises(ValueError):
        parse_amount_cents(value, ",")


def test_parse_date_dayfirst_vs_isofirst():
    assert parse_date("03-04-2024", dayfirst=True) == date(2024, 4, 3)
    assert parse_date("2024-04-03") == date(2024, 4, 3)
    assert parse_date("20240403") == date(2024, 4, 3)


# ─── dedupe ─────────────────────────────────────────────────────────────────

def test_hashes_are_stable_across_runs():
    a = [r.import_hash for r in parse_csv(load("rabobank_current.csv")).rows]
    b = [r.import_hash for r in parse_csv(load("rabobank_current.csv")).rows]
    assert a == b


def test_hashes_distinguish_identical_looking_rows():
    """Two €2.99 charges from the same merchant on the same day are two
    transactions, not one — the bank reference keeps them apart."""
    rows = parse_csv(load("rabobank_creditcard.csv")).rows
    assert len({r.import_hash for r in rows}) == len(rows)
