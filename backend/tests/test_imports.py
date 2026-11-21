from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from financepro import clock
from financepro.demo import generator
from financepro.importers.models import ImportBatch
from tests.importing import account, confirm, import_file, transactions, upload

SignedIn = Callable[..., TestClient]
TODAY = date(2026, 11, 20)


@pytest.fixture
def statements() -> tuple[list[generator.Line], list[generator.Line]]:
    card_lines, bills = generator.card(TODAY)
    return generator.checking(TODAY, card_bills=bills), card_lines


class TestNubankPresets:
    def test_checking_account(
        self, signed_in: SignedIn, statements: tuple[list[generator.Line], ...]
    ) -> None:
        checking_lines = statements[0]
        browser = signed_in()
        checking = account(browser)
        batch = upload(browser, checking, generator.nubank_checking_csv(checking_lines))
        assert batch["detected_by"] == "preset:nubank_conta"
        assert batch["summary"] == {
            "total": len(checking_lines), "new": len(checking_lines), "duplicate": 0, "possible_duplicate": 0,
            "error": 0,
        }  # fmt: skip
        assert confirm(browser, batch)["summary"]["inserted"] == len(checking_lines)

        imported = transactions(browser)
        assert sorted(t["amount_cents"] for t in imported) == sorted(
            line.amount_cents for line in checking_lines
        )
        salary = next(t for t in imported if t["amount_cents"] == 685000)
        assert salary["merchant"] == "Transferência de Acme Tecnologia Ltda"
        savings = [t for t in imported if t["description_raw"] == "Aplicação RDB"]
        assert savings
        assert {t["kind"] for t in savings} == {"transfer"}
        assert all(t["category_id"] is None for t in savings)

    def test_card_purchases_become_outflows(
        self, signed_in: SignedIn, statements: tuple[list[generator.Line], ...]
    ) -> None:
        card_lines = statements[1]
        browser = signed_in()
        card = account(browser, "credit_card")
        batch = upload(browser, card, generator.nubank_card_csv(card_lines))
        assert batch["detected_by"] == "preset:nubank_cartao"
        confirm(browser, batch)
        imported = transactions(browser)
        assert sorted(t["amount_cents"] for t in imported) == sorted(line.amount_cents for line in card_lines)
        uber = next(t for t in imported if t["description_raw"] == "UBER *TRIP")
        assert uber["amount_cents"] < 0
        assert uber["merchant"] == "Uber"
        assert uber["category_source"] == "merchant"
        payment = next(t for t in imported if t["description_raw"] == "Pagamento recebido")
        assert payment["amount_cents"] > 0
        assert payment["kind"] == "transfer"


class TestDeduplication:
    def test_the_same_file_twice_adds_nothing(
        self, signed_in: SignedIn, statements: tuple[list[generator.Line], ...]
    ) -> None:
        browser = signed_in()
        checking = account(browser)
        content = generator.nubank_checking_csv(statements[0])
        import_file(browser, checking, content)
        again = upload(browser, checking, content)
        assert again["summary"]["duplicate"] == len(statements[0])
        assert {row["message"] for row in again["rows"]} == {"Já importado."}
        assert confirm(browser, again)["summary"]["inserted"] == 0
        assert len(transactions(browser)) == len(statements[0])

    def test_an_overlapping_statement_adds_only_what_is_new(
        self, signed_in: SignedIn, statements: tuple[list[generator.Line], ...]
    ) -> None:
        card_lines = statements[1]  # the card file has no ids: this is the fingerprint at work
        middle = card_lines[len(card_lines) // 2].date
        first = [line for line in card_lines if line.date <= middle]
        second = [line for line in card_lines if line.date >= middle - timedelta(days=20)]
        browser = signed_in()
        card = account(browser, "credit_card")
        import_file(browser, card, generator.nubank_card_csv(first))
        result = import_file(browser, card, generator.nubank_card_csv(second))
        overlap = len([line for line in second if line.date <= middle])
        assert result["summary"]["duplicate"] == overlap
        assert result["summary"]["inserted"] == len(second) - overlap
        assert len(transactions(browser)) == len(card_lines)

    def test_identical_lines_on_the_same_day_are_all_kept(self, signed_in: SignedIn) -> None:
        content = "Data;Descrição;Valor\n03/11/2026;PADARIA REAL;-5,00\n03/11/2026;PADARIA REAL;-5,00\n"
        browser = signed_in()
        checking = account(browser)
        assert import_file(browser, checking, content)["summary"]["inserted"] == 2
        # The same file again: each coffee matches its counterpart, nothing doubles.
        assert import_file(browser, checking, content)["summary"]["inserted"] == 0
        # A later export with a third coffee that day brings exactly one more.
        content += "03/11/2026;PADARIA REAL;-5,00\n"
        assert import_file(browser, checking, content)["summary"]["inserted"] == 1

    def test_a_deleted_transaction_does_not_come_back(self, signed_in: SignedIn) -> None:
        content = "Data;Descrição;Valor\n03/11/2026;LOJA X;-50,00\n04/11/2026;LOJA Y;-20,00\n"
        browser = signed_in()
        checking = account(browser)
        import_file(browser, checking, content)
        victim = next(t for t in transactions(browser) if t["description_raw"] == "LOJA X")
        assert browser.delete(f"/api/transactions/{victim['id']}").status_code == 204
        again = upload(browser, checking, content)
        messages = {row["description"]: row["message"] for row in again["rows"]}
        assert messages["LOJA X"] == "Você excluiu este lançamento antes."
        assert confirm(browser, again)["summary"]["inserted"] == 0
        assert [t["description_raw"] for t in transactions(browser)] == ["LOJA Y"]

    def test_a_rewritten_description_is_a_possible_duplicate(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        checking = account(browser)
        import_file(browser, checking, "Data;Descrição;Valor\n03/11/2026;PAG*LOJA DO ZE;-89,90\n")
        later = upload(
            browser,
            checking,
            "Data;Descrição;Valor\n04/11/2026;LOJA DO ZE LTDA;-89,90\n05/11/2026;OUTRA;-10,00\n",
        )
        flagged = next(row for row in later["rows"] if row["status"] == "possible_duplicate")
        assert flagged["match"]["description"] == "PAG*LOJA DO ZE"
        # Not chosen: left out. The other line goes in.
        assert confirm(browser, later)["summary"]["inserted"] == 1

        browser2 = signed_in()
        checking2 = account(browser2)
        import_file(browser2, checking2, "Data;Descrição;Valor\n03/11/2026;PAG*LOJA DO ZE;-89,90\n")
        later2 = upload(browser2, checking2, "Data;Descrição;Valor\n04/11/2026;LOJA DO ZE LTDA;-89,90\n")
        assert confirm(browser2, later2, include=[later2["rows"][0]["line"]])["summary"]["inserted"] == 1


class TestOtherLayouts:
    def test_a_title_block_semicolons_comma_decimals_and_windows_1252(self, signed_in: SignedIn) -> None:
        content = (
            "Extrato Conta Corrente\nPeríodo: 01/10/2026 a 31/10/2026\n\n"
            "Data Lançamento;Histórico;Descrição;Valor;Saldo\n"
            "01/10/2026;Pix enviado;Maria Souza;-1.234,56;10.000,00\n"
            "02/10/2026;Compra no débito;Padaria Pão Quente;-12,30;9.987,70\n"
            "05/10/2026;Pix recebido;João Lima;300,00;10.287,70\n"
        ).encode("cp1252")
        browser = signed_in()
        batch = upload(browser, account(browser), content)
        assert batch["detected_by"] == "auto"
        assert batch["header"] == ["Data Lançamento", "Histórico", "Descrição", "Valor", "Saldo"]
        assert [(row["description"], row["amount_cents"]) for row in batch["rows"]] == [
            ("Pix enviado - Maria Souza", -123456),
            ("Compra no débito - Padaria Pão Quente", -1230),
            ("Pix recebido - João Lima", 30000),
        ]

    def test_debit_and_credit_columns(self, signed_in: SignedIn) -> None:
        content = "data,descricao,debito,credito\n2026-10-01,Aluguel,2200.00,\n2026-10-05,Salario,,6850.00\n"
        browser = signed_in()
        batch = upload(browser, account(browser), content)
        assert [row["amount_cents"] for row in batch["rows"]] == [-220000, 685000]

    def test_unknown_column_names_are_read_by_content(self, signed_in: SignedIn) -> None:
        content = "quando,o que,quanto\n01/10/2026,Mercado do bairro,-50.00\n02/10/2026,Farmácia,-12.00\n"
        browser = signed_in()
        batch = upload(browser, account(browser), content)
        assert batch["detected_by"] == "auto"
        assert [(row["description"], row["amount_cents"]) for row in batch["rows"]] == [
            ("Mercado do bairro", -5000),
            ("Farmácia", -1200),
        ]

    def test_a_corrected_mapping_is_remembered_for_the_next_file(self, signed_in: SignedIn) -> None:
        # A card export we don't know, with purchases as positive numbers and too few of them to guess.
        content = "Data;Descrição;Valor\n01/10/2026;LOJA A;50,00\n02/10/2026;Pagamento;-80,00\n"
        browser = signed_in()
        card = account(browser, "credit_card")
        batch = upload(browser, card, content)
        assert [row["amount_cents"] for row in batch["rows"]] == [5000, -8000]
        mapping = {**batch["mapping"], "sign": "inverted"}
        remapped = browser.put(f"/api/imports/{batch['id']}/mapping", json=mapping).json()
        assert [row["amount_cents"] for row in remapped["rows"]] == [-5000, 8000]
        assert remapped["detected_by"] == "manual"
        confirm(browser, remapped)
        # Next time, the same layout needs no correction.
        next_batch = upload(browser, card, content.replace("/10/", "/11/"))
        assert next_batch["detected_by"] == "profile"
        assert [row["amount_cents"] for row in next_batch["rows"]] == [-5000, 8000]

    def test_unreadable_lines_are_reported_not_imported(self, signed_in: SignedIn) -> None:
        content = (
            "Data;Descrição;Valor\n03/11/2026;OK;-5,00\n31/02/2026;DATA RUIM;-5,00\n04/11/2026;ZERO;0,00\n"
        )
        browser = signed_in()
        batch = upload(browser, account(browser), content)
        assert [(row["status"], row["message"]) for row in batch["rows"]] == [
            ("new", None),
            ("error", "Data inválida: “31/02/2026”."),
            ("error", "Valor zero; linha ignorada."),
        ]
        assert batch["rows"][1]["line"] == 3
        assert confirm(browser, batch)["summary"]["inserted"] == 1


class TestFileLimits:
    @pytest.mark.parametrize(
        ("content", "message"),
        [
            (b"", "O arquivo está vazio."),
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00",
                "Isto não parece um arquivo CSV (é binário). Exporte o extrato em CSV.",
            ),
            (
                b"so,um,texto\nsem,data,nenhuma\n",
                "Não encontrei a linha de cabeçalho (com nomes como Data, Descrição e Valor).",
            ),
        ],
    )
    def test_files_that_are_not_statements(self, signed_in: SignedIn, content: bytes, message: str) -> None:
        browser = signed_in()
        response = browser.post(
            "/api/imports", data={"account_id": str(account(browser))}, files={"file": ("x.csv", content)}
        )
        assert response.status_code == 422
        assert response.json()["detail"] == message

    def test_files_over_2_mb(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        big = b"Data;Descricao;Valor\n" + b"01/01/2026;X;-1,00\n" * 120_000
        response = browser.post(
            "/api/imports", data={"account_id": str(account(browser))}, files={"file": ("x.csv", big)}
        )
        assert response.status_code == 413


class TestConfirmAndUndo:
    def test_confirming_twice_imports_once(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        batch = upload(browser, account(browser), "Data;Descrição;Valor\n03/11/2026;LOJA;-5,00\n")
        confirm(browser, batch)
        again = browser.post(f"/api/imports/{batch['id']}/confirm", json={})
        assert again.status_code == 409
        assert len(transactions(browser)) == 1

    def test_an_expired_preview_must_be_uploaded_again(self, signed_in: SignedIn, db: Session) -> None:
        browser = signed_in()
        batch = upload(browser, account(browser), "Data;Descrição;Valor\n03/11/2026;LOJA;-5,00\n")
        db.execute(update(ImportBatch).values(expires_at=clock.now() - timedelta(seconds=1)))
        response = browser.post(f"/api/imports/{batch['id']}/confirm", json={})
        assert response.status_code == 409
        assert response.json()["detail"] == "Esta prévia expirou. Envie o arquivo de novo."

    def test_undo_removes_the_import_and_asks_before_discarding_edits(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        checking = account(browser)
        content = "Data;Descrição;Valor\n03/11/2026;LOJA A;-5,00\n04/11/2026;LOJA B;-7,00\n"
        batch = import_file(browser, checking, content)
        edited = transactions(browser)[0]
        browser.patch(f"/api/transactions/{edited['id']}", json={"notes": "presente da Ana"})

        refused = browser.post(f"/api/imports/{batch['id']}/undo", json={})
        assert refused.status_code == 409
        assert refused.json()["detail"].startswith("1 lançamento(s)")
        assert (
            browser.post(f"/api/imports/{batch['id']}/undo", json={"discard_edits": True}).status_code == 200
        )
        assert transactions(browser) == []
        # Undone means never imported: the same file goes in again.
        assert import_file(browser, checking, content)["summary"]["inserted"] == 2
        history = browser.get("/api/imports").json()
        assert [b["status"] for b in history] == ["committed", "undone"]
