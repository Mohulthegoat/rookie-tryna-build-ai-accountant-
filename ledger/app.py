"""LedgerAI Streamlit App

All pages are wired to the engine. AI proposes, a qualified human approves.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from ledgerai.engine import run_engine
from ledgerai.money import format_inr
from ledgerai.ingest import read_csv_raw, read_excel_raw, detect_bank_format

st.set_page_config(page_title="LedgerAI", layout="wide", initial_sidebar_state="expanded")

st.title("LedgerAI")
st.warning(
    "**AI proposes, a qualified human approves.** Nothing is auto-posted without approval. "
    "Items marked 'needs approval' or 'assumed' require human review."
)

with st.sidebar:
    st.header("Company")
    st.selectbox("Select company", ["Sharma Trading Co. Pvt. Ltd. (FAKE)"])
    st.divider()
    st.header("Mode")
    st.warning("**do not upload real client data**")
    st.divider()
    st.caption("LedgerAI | Paise integers only")

# Session state
if "imported_data" not in st.session_state:
    st.session_state.imported_data = None
if "imported_files" not in st.session_state:
    st.session_state.imported_files = {}
if "use_sample" not in st.session_state:
    st.session_state.use_sample = False

tabs = st.tabs(
    [
        "Upload",
        "Matches",
        "Exceptions",
        "Verification Checks",
        "Trial Balance",
        "P&L",
        "Balance Sheet",
        "Scorecard",
        "Disagreements",
        "Dry Run",
    ]
)

with tabs[0]:
    st.header("Upload")
    st.write(
        "Upload bank statement, ledger/Tally export, and invoices. "
        "Preview and confirm column mapping. AI suggests; you must review and confirm before import."
    )
    
    c1, c2, c3 = st.columns(3)
    with c1:
        bank_file = st.file_uploader("Bank Statement CSV/Excel", type=["csv", "xlsx", "xls"], key="bank_upload")
    with c2:
        ledger_file = st.file_uploader("Ledger/Tally CSV/Excel", type=["csv", "xlsx", "xls"], key="ledger_upload")
    with c3:
        inv_file = st.file_uploader("Invoices CSV/Excel", type=["csv", "xlsx", "xls"], key="inv_upload")
    
    st.divider()
    
    # Preview uploaded files
    errors = []
    previews = {}
    
    for name, uploaded, key in [("Bank Statement", bank_file, "bank"), ("Ledger/Tally", ledger_file, "ledger"), ("Invoices", inv_file, "inv")]:
        if uploaded is not None:
            try:
                suffix = Path(uploaded.name).suffix.lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name
                try:
                    if suffix in ['.xlsx', '.xls']:
                        rows, headers = read_excel_raw(tmp_path)
                    else:
                        rows, headers = read_csv_raw(tmp_path)
                    previews[key] = {"rows": rows, "headers": headers, "name": uploaded.name}
                    st.subheader(f"{name}: {uploaded.name}")
                    st.caption(f"Rows: {len(rows)}, Columns: {len(headers)}")
                    st.dataframe(rows[:10], use_container_width=True)
                    if key == "bank":
                        mapping = detect_bank_format(headers)
                        st.caption(f"Detected mapping: {mapping}")
                finally:
                    os.unlink(tmp_path)
            except Exception as e:
                errors.append(f"{name}: {e}")
                st.error(f"{name}: {e}")
    
    st.divider()
    st.info("AI suggests mapping. You must review and confirm before import.")
    confirm = st.checkbox("I have reviewed and confirm the column mapping")
    
    # Determine if import is possible
    can_import = bank_file is not None and ledger_file is not None and inv_file is not None and confirm
    if not can_import:
        reasons = []
        if bank_file is None or ledger_file is None or inv_file is None:
            reasons.append("Upload all three files (bank statement, ledger/Tally export, invoices)")
        if not confirm:
            reasons.append("Tick the confirmation checkbox after reviewing mappings")
        if errors:
            reasons.append("Fix file errors above")
        st.warning("Import disabled: " + "; ".join(reasons))
    
    if st.button("Import", disabled=not can_import):
        try:
            # Save uploaded files temporarily and run engine
            tmp_files = []
            file_paths = {}
            for name, uploaded, key in [("bank", bank_file, "bank"), ("ledger", ledger_file, "ledger"), ("inv", inv_file, "inv")]:
                suffix = Path(uploaded.name).suffix.lower()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(uploaded.getvalue())
                tmp.close()
                tmp_files.append(tmp.name)
                file_paths[key] = tmp.name
            
            result = run_engine(file_paths["bank"], file_paths["ledger"], file_paths["inv"])
            st.session_state.imported_data = result
            st.session_state.imported_files = {
                "bank": bank_file.name,
                "ledger": ledger_file.name,
                "invoices": inv_file.name
            }
            st.session_state.use_sample = False
            st.success("Files imported successfully")
            for tf in tmp_files:
                try:
                    os.unlink(tf)
                except:
                    pass
        except Exception as e:
            st.error(f"Import failed: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    st.divider()
    if st.button("Load sample data (data/test)"):
        try:
            test_dir = Path(__file__).parent / "data" / "test"
            result = run_engine(
                test_dir / "bank_statement_oct2026.csv",
                test_dir / "ledger_tally_export_oct2026.csv",
                test_dir / "invoices_oct2026.csv"
            )
            st.session_state.imported_data = result
            st.session_state.imported_files = {
                "bank": "bank_statement_oct2026.csv (sample)",
                "ledger": "ledger_tally_export_oct2026.csv (sample)",
                "invoices": "invoices_oct2026.csv (sample)"
            }
            st.session_state.use_sample = True
            st.success("Sample data loaded")
        except Exception as e:
            st.error(f"Failed to load sample: {e}")
    
    if st.button("Clear imported data"):
        st.session_state.imported_data = None
        st.session_state.imported_files = {}
        st.session_state.use_sample = False
        st.success("Cleared")


def _format_paise(value: int) -> str:
    try:
        return format_inr(value)
    except Exception:
        return str(value)


def _no_data():
    st.info("Upload files to begin")


with tabs[1]:
    st.header("Matches (Bank <-> Ledger)")
    st.write("Exact -> Fuzzy -> Split. Every match shows evidence. AI proposes, human approves.")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        rows = []
        for match in result.matches:
            if match["type"] == "SPLIT":
                ledger_names = ", ".join(l.particulars for l in match["ledgers"])
                ledger_ids = ", ".join(l.line_id for l in match["ledgers"])
                rows.append(
                    {
                        "Type": match["type"],
                        "Bank": f"{match['bank'].line_id} - {match['bank'].narration}",
                        "Ledger": ledger_names,
                        "Ledger IDs": ledger_ids,
                        "Amount": _format_paise(abs(match["amount_paise"])),
                        "Diff (paise)": match["difference_paise"],
                        "Needs approval": match["needs_approval"],
                        "Rule used": match["rule_used"],
                        "Reason": match["reason"],
                        "Confidence": match["confidence"],
                    }
                )
            else:
                ledger = match["ledgers"][0]
                rows.append(
                    {
                        "Type": match["type"],
                        "Bank": f"{match['bank'].line_id} - {match['bank'].narration}",
                        "Ledger": f"{ledger.line_id} - {ledger.particulars}",
                        "Ledger IDs": ledger.line_id,
                        "Amount": _format_paise(abs(match["amount_paise"])),
                        "Diff (paise)": match["difference_paise"],
                        "Needs approval": match["needs_approval"],
                        "Rule used": match["rule_used"],
                        "Reason": match["reason"],
                        "Confidence": match["confidence"],
                    }
                )
        st.dataframe(rows, use_container_width=True)
        st.caption(
            f"Bank matched: {result.counts['bank_matched']} / {result.counts['bank_transactions']} | "
            f"Ledger matched: {result.counts['ledger_matched']} / {result.counts['ledger_entries']}"
        )


with tabs[2]:
    st.header("Exceptions")
    st.write("Planted problems, duplicates, uncleared cheques, and mismatches.")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        exc_rows = []
        for exc in result.exceptions:
            exc_rows.append(
                {
                    "Type": exc["type"],
                    "Severity": exc.get("severity", ""),
                    "Title": exc.get("title", ""),
                    "Reason": exc.get("reason", ""),
                    "Bank IDs": ", ".join(exc.get("bank_ids", [])),
                    "Ledger IDs": ", ".join(exc.get("ledger_ids", [])),
                    "Invoice": exc.get("invoice_no", ""),
                    "Diff (paise)": exc.get("difference_paise", ""),
                    "Rule used": exc.get("rule_used", ""),
                }
            )
        st.dataframe(exc_rows, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Planted problems", result.counts["planted_problems"])
        c2.metric("Invoice problems", result.counts["invoice_problems"])
        c3.metric("Exceptions total", len(result.exceptions))

        st.subheader("Invoice checks & suggestions")
        inv_rows = []
        for issue in result.invoice_issues:
            inv_rows.append(
                {
                    "Type": issue["type"],
                    "Invoice": issue.get("invoice_no", ""),
                    "Party": issue.get("party", ""),
                    "Reason": issue.get("reason", ""),
                    "Rule used": issue.get("rule_used", ""),
                }
            )
        st.dataframe(inv_rows, use_container_width=True)

        sug_rows = []
        for bank in result.unmatched_bank:
            suggestion = result.invoice_suggestions.get(bank.line_id, {})
            sug_rows.append(
                {
                    "Bank": bank.line_id,
                    "Narration": bank.narration,
                    "Amount": _format_paise(abs(bank.signed_paise)),
                    "Suggestion status": suggestion.get("status", ""),
                    "Suggested invoice": suggestion.get("invoice_no", ""),
                    "Reason": suggestion.get("reason", ""),
                }
            )
        st.dataframe(sug_rows, use_container_width=True)


with tabs[3]:
    st.header("Verification Checks")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        st.metric("Status", result.verification.status)
        checks = []
        for check in result.verification.checks:
            checks.append(
                {
                    "Check": check.get("name", ""),
                    "Passed": check.get("passed", False),
                    "Detail": check.get("detail", ""),
                }
            )
        st.dataframe(checks, use_container_width=True)
        if result.verification.blocking_failures:
            st.error(f"Blocking failures: {result.verification.blocking_failures}")
        if result.verification.warnings:
            st.warning(f"Warnings: {result.verification.warnings}")


with tabs[4]:
    st.header("Trial Balance")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        rows = []
        for row in result.trial_balance.rows:
            rows.append(
                {
                    "Account": row["account_id"],
                    "Account Type": row.get("account_type", ""),
                    "Debits": _format_paise(row["debits_paise"]),
                    "Credits": _format_paise(row["credits_paise"]),
                    "Balance": _format_paise(row["balance_paise"]),
                }
            )
        st.dataframe(rows, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Debits", _format_paise(result.trial_balance.total_debits_paise))
        c2.metric("Total Credits", _format_paise(result.trial_balance.total_credits_paise))
        c3.metric("Balanced", "YES" if result.trial_balance.balanced else "NO")


with tabs[5]:
    st.header("Profit & Loss")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        c1, c2, c3 = st.columns(3)
        c1.metric("Revenue (Income)", _format_paise(result.pl.revenue_paise))
        c2.metric("Expenses", _format_paise(result.pl.expenses_paise))
        c3.metric("Net Profit/(Loss)", _format_paise(result.pl.net_paise))
        st.caption("Money received = Income, Money paid out = Expense")


with tabs[6]:
    st.header("Balance Sheet")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Assets", _format_paise(result.balance_sheet.assets_paise))
        c2.metric("Liabilities", _format_paise(result.balance_sheet.liabilities_paise))
        c3.metric("Equity", _format_paise(result.balance_sheet.equity_paise))
        c4.metric("Balanced", "YES" if result.balance_sheet.balanced else "NO")
        st.caption("Assets = Liabilities + Equity")


with tabs[7]:
    st.header("Scorecard")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        st.subheader("Imported Files")
        for k, v in st.session_state.imported_files.items():
            st.text(f"{k}: {v}")
        st.json(
            {
                "version": "1.0.0",
                "counts": result.counts,
                "trial_balance_balanced": result.trial_balance.balanced,
                "verification_status": result.verification.status,
                "balance_sheet_balanced": result.balance_sheet.balanced,
            }
        )


with tabs[8]:
    st.header("Disagreement Log")
    st.write("Every case where accountant differs is logged with reason.")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        rows = []
        for exc in result.exceptions:
            if exc["type"] in ("small_difference", "amount_mismatch"):
                rows.append(
                    {
                        "Case": exc["title"],
                        "Reason": exc["reason"],
                        "Status": "open",
                        "Logged by": "engine",
                    }
                )
        st.dataframe(rows, use_container_width=True)


with tabs[9]:
    st.header("Dry Run")
    st.write("Compare reconciled results against expected counts that you upload or type in.")
    if st.session_state.imported_data is None:
        _no_data()
    else:
        result = st.session_state.imported_data
        st.subheader("Compare against your expected counts")
        c1, c2 = st.columns(2)
        with c1:
            exp_bank_txn = st.number_input("Expected bank transactions", value=0)
            exp_bank_matched = st.number_input("Expected bank matched", value=0)
            exp_bank_unmatched = st.number_input("Expected bank unmatched", value=0)
        with c2:
            exp_ledger_entries = st.number_input("Expected ledger entries", value=0)
            exp_ledger_matched = st.number_input("Expected ledger matched", value=0)
            exp_ledger_unmatched = st.number_input("Expected ledger unmatched", value=0)
        if st.button("Compare"):
            rows = [
                {"Check": "Bank transactions", "Expected": exp_bank_txn, "Actual": result.counts["bank_transactions"], "OK": exp_bank_txn == result.counts["bank_transactions"]},
                {"Check": "Bank matched", "Expected": exp_bank_matched, "Actual": result.counts["bank_matched"], "OK": exp_bank_matched == result.counts["bank_matched"]},
                {"Check": "Bank unmatched", "Expected": exp_bank_unmatched, "Actual": result.counts["unmatched_bank"], "OK": exp_bank_unmatched == result.counts["unmatched_bank"]},
                {"Check": "Ledger entries", "Expected": exp_ledger_entries, "Actual": result.counts["ledger_entries"], "OK": exp_ledger_entries == result.counts["ledger_entries"]},
                {"Check": "Ledger matched", "Expected": exp_ledger_matched, "Actual": result.counts["ledger_matched"], "OK": exp_ledger_matched == result.counts["ledger_matched"]},
                {"Check": "Ledger unmatched", "Expected": exp_ledger_unmatched, "Actual": result.counts["unmatched_ledger"], "OK": exp_ledger_unmatched == result.counts["unmatched_ledger"]},
            ]
            st.dataframe(rows, use_container_width=True)

st.divider()
st.caption("LedgerAI | AI proposes, human approves | Paise integers only")
