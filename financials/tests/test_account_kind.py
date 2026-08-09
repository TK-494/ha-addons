"""Savings-account detection.

Nothing in a Dutch bank CSV declares an account type, so it is inferred: a
savings account has no card payments, no iDEAL and no direct debits, and its
traffic is almost entirely to and from your own accounts.

Getting this wrong is not cosmetic — the *Gespaard* figure counts only accounts
marked as savings, so a missed detection makes it read €0,00 forever.
"""

from __future__ import annotations

from conftest import import_fixture

HEADER = (
    '"IBAN/BBAN","Munt","BIC","Volgnr","Datum","Rentedatum","Bedrag","Saldo na trn",'
    '"Tegenrekening IBAN/BBAN","Naam tegenpartij","Naam uiteindelijke partij",'
    '"Naam initiërende partij","BIC tegenpartij","Code","Batch ID","Transactiereferentie",'
    '"Machtigingskenmerk","Incassant ID","Betalingskenmerk","Omschrijving-1",'
    '"Omschrijving-2","Omschrijving-3","Reden retour","Oorspr bedrag","Oorspr munt","Koers"'
)


def row(iban, seq, day, amount, balance, counter, code, creditor="", description="Overboeking"):
    return (
        f'"{iban}","EUR","TESTNL2U","{seq:018d}","2024-03-{day:02d}","2024-03-{day:02d}",'
        f'"{amount}","{balance}","{counter}","Eigen rekening","","","","{code}","",'
        f'"REF{seq}","","{creditor}","","{description}","","","","","",""'
    )


def upload_csv(client, rows):
    csv = (HEADER + "\n" + "\n".join(rows) + "\n").encode("utf-8")
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("extra.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})


def kind_of(client, iban):
    return next(a["kind"] for a in client.get("/api/accounts/").json() if a["iban"] == iban)


def savings_pair(count=20, code="db"):
    """`count` transfers back and forth between the main account and a savings
    account, so both legs exist and the traffic reads as fully internal."""
    rows = []
    seq = 100
    for index in range(count):
        day = (index % 28) + 1
        rows.append(row("NL00TEST0000000005", seq, day, "100,00", "1.000,00",
                        "NL00TEST0000000001", code))
        seq += 1
        rows.append(row("NL00TEST0000000001", seq, day, "-100,00", "500,00",
                        "NL00TEST0000000005", "tb"))
        seq += 1
    return rows


def test_savings_account_is_detected_automatically(client):
    import_fixture(client, "rabobank_current.csv")
    upload_csv(client, savings_pair())
    assert kind_of(client, "NL00TEST0000000005") == "savings"


def test_code_db_does_not_disqualify_a_savings_account(client):
    """Regression: `db` reads like "doorlopende incasso" but Rabobank uses it
    for diverse bookings. Treating it as spending disqualified a real savings
    account whose every row is coded `db`."""
    import_fixture(client, "rabobank_current.csv")
    upload_csv(client, savings_pair(code="db"))
    assert kind_of(client, "NL00TEST0000000005") == "savings"


def test_a_card_payment_disqualifies_an_account(client):
    import_fixture(client, "rabobank_current.csv")
    rows = savings_pair()
    rows.append(row("NL00TEST0000000005", 999, 15, "-9,99", "990,01", "", "bc",
                    description="Betaalautomaat"))
    upload_csv(client, rows)
    assert kind_of(client, "NL00TEST0000000005") == "checking"


def test_a_direct_debit_disqualifies_an_account(client):
    import_fixture(client, "rabobank_current.csv")
    rows = savings_pair()
    rows.append(row("NL00TEST0000000005", 998, 16, "-25,00", "975,00", "NL00TEST0000000077",
                    "ei", creditor="NL00ZZZ999999999999", description="Incasso"))
    upload_csv(client, rows)
    assert kind_of(client, "NL00TEST0000000005") == "checking"


def test_too_few_transactions_is_left_alone(client):
    """Three transfers is not evidence of anything."""
    import_fixture(client, "rabobank_current.csv")
    upload_csv(client, savings_pair(count=2))
    assert kind_of(client, "NL00TEST0000000005") == "checking"


def test_the_current_account_is_never_reclassified(client):
    import_fixture(client, "rabobank_current.csv")
    upload_csv(client, savings_pair())
    assert kind_of(client, "NL00TEST0000000001") == "checking"


def test_a_credit_card_is_never_reclassified(client):
    import_fixture(client, "rabobank_current.csv")
    import_fixture(client, "rabobank_creditcard.csv")
    card = next(a for a in client.get("/api/accounts/").json() if a["card_last4"])
    assert card["kind"] == "credit_card"


def test_detection_makes_the_saved_figure_real(client):
    """The whole point: without detection this reads €0,00 and looks like a
    bug rather than an unset option."""
    import_fixture(client, "rabobank_current.csv")

    before = client.get("/api/dashboard/summary", params={"year": 2024, "month": 3}).json()
    assert before["savings_accounts"] == 0
    assert before["saved"] == 0

    upload_csv(client, savings_pair())

    after = client.get("/api/dashboard/summary", params={"year": 2024, "month": 3}).json()
    assert after["savings_accounts"] == 1
    assert after["saved"] == 2000.0  # 20 × €100 into savings
