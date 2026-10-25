# Step 0 review of Executive_Summary.pdf

Reviewed: 24 October 2026. Full extracted text: `docs/executive_summary_text.txt`.

Purpose: record what is trustworthy, what is wrong, and what must be verified
before this document is shown to investors, CAs or customers. Nothing here is
legal or tax advice.

---

## A. Errors already confirmed by the founder

1. **PSD2 does not apply in India.** PSD2 is an EU payments directive. India's
   equivalent for consented bank-data sharing is the RBI **Account Aggregator
   (AA) framework**. Being an FIU (Financial Information User) or partnering
   with one is a regulated activity, not a simple API key.
2. **India's data law is the Digital Personal Data Protection (DPDP) Act, 2023**,
   not a "PDP Bill". The Act is in force; the supporting rules and phased
   obligations must be checked with a lawyer. Calling it a Bill understates
   live obligations (consent, purpose limitation, erasure, breach notice,
   penalties).
3. **Every citation marker in the PDF is broken** (e.g. `【39†L25-L33】`). They
   are internal artifact references, not verifiable sources. Treat every
   competitor, pricing and market claim as **unverified** until independently
   sourced.

## B. Other errors or misleading statements I found

4. **"Tally API"** — Tally does not offer a simple public REST API. Integration
   is via Tally XML/TDL, ODBC, or file export, and is version-specific. This is
   materially harder than the document implies.
5. **"Odoo/Tally APIs"** — Odoo is an ERP and is irrelevant to the India-first
   SME close workflow described. Mixing it in suggests the stack was not thought
   through.
6. **"GST/VAT returns"** — VAT has largely been replaced by GST in India. VAT
   survives only for certain items (e.g. petroleum products and alcohol in some
   states). The product should say GST, not GST/VAT.
7. **"Zoho Books has limited GST handling"** — false as a blanket claim. The
   India edition handles GST returns and e-invoicing. The competitive table
   understates the strongest low-cost Indian competitor. Needs re-research.
8. **"Xero = manual processes, no automation"** — overstated. Xero has automated
   bank reconciliation and rules; it lacks an agentic close. The table conflates
   "not agentic" with "manual".
9. **"No competitor focuses on Indian compliance"** — very likely false. Indian
   vendors (e.g. ClearTax, Suvit, Vyapar, Busy, Marg, RazorpayX, Karbon, Munim)
   operate in this space. The claim needs a proper competitive scan before it is
   used with investors.
10. **Trullion / Pilot / Digits / FinBooks descriptions** — unverified and partly
    inconsistent with public positioning (Trullion is known for lease/revenue
    accounting and audit AI; Pilot is a US bookkeeping service; "FinBooks" could
    not be identified). Do not repeat these claims without sources.
11. **Stack inconsistency** — the architecture recommends OpenAI GPT-4 while the
    product decision is the Anthropic API. Pick one and record why.
12. **"Indian GAAP/IndAS"** — these are different frameworks. Ind AS applies to
    larger companies; most SMEs use Companies (Accounting Standards) Rules /
    Schedule III formats. The report must state which framework applies to the
    target customer and let a CA confirm it.
13. **GST accuracy target of 98%** — unacceptable for deterministic tax rules.
    Tax computation should be 100% correct on supported cases, with anything
    uncertain blocked and marked `NEEDS CA REVIEW`. A 98% target normalises
    wrong tax returns.
14. **"Automate GST filings"** — filing via GSTN requires GSP integration,
    taxpayer authentication and authorised signatories. Calculating a draft is
    not filing. Scope must say "draft for CA review", not "file".
15. **E-invoicing threshold stated vaguely** — thresholds and scope change by
    notification. E-invoicing applies to specified B2B/exports/credit-note
    transactions, not all invoices. Store thresholds as versioned configuration,
    never hard-code them.

## C. Important gaps (not errors, but missing from the plan)

16. **No CGST/SGST vs IGST place-of-supply logic.** This is core GST, not an
    edge case. Supplier state vs place of supply decides the tax split.
17. **No TDS anywhere in the document** (the founder's build order correctly
    adds it). TDS sections, rates and thresholds change annually via the Finance
    Act and must be configuration with effective dates.
18. **No Section 170 rounding rule** (tax payable rounded to the nearest rupee)
    and no invoice round-off handling.
19. **No ITC conditions**: Section 16 eligibility, Section 17(5) blocked credits,
    reverse charge, time limits, GSTR-2B matching cutoff.
20. **No mention of GSTR-1, GSTR-9, IRN/e-invoice, e-way bill, TCS** — the
    compliance surface is much larger than "GSTR-2B + 3B".
21. **No opening balances, prior-period close, retained earnings, period lock,
    accruals, cut-off, depreciation or inventory valuation.** Without these,
    a P&L and balance sheet cannot be produced. Calling reports "low complexity
    sum logic" is wrong.
22. **A balanced trial balance is necessary but not sufficient.** Wrong
    classification still balances. Verification needs classification and
    completeness checks too.
23. **No prompt-injection defence.** Invoices and bank narrations are untrusted
    input. They can contain instructions aimed at the LLM. The design must treat
    all document text as data and never as instructions, and validate every
    LLM output in code.
24. **No LLM/OCR cost model.** Cost per close (extraction, planning, retries) is
    absent from pricing. Gross margin could be negative at ₹5,000–15,000/month.
25. **No DPDP operational detail**: consent notice, purpose limitation, data
    principal rights, erasure, retention, breach notification, consent manager,
    vendor DPAs, cross-border transfer assessment, sub-processor list. Sending
    client financial data to an LLM API needs a DPA and a no-training guarantee.
    **Needs a lawyer.**
26. **No security architecture beyond "encrypt at rest"**: key management,
    tenant isolation tests, backups/restore drills, audit-log immutability
    (append-only/hash chain), secrets rotation, least privilege, incident
    response.
27. **No statutory retention model** (e.g. Companies Act books, GST records) or
    legal hold. Deletion requests under DPDP must not destroy legally required
    records.
28. **Fuzzy matching tolerance is dangerous as described** ("₹499 vs ₹500,
    date ±1 day"). An absolute tolerance in paise (e.g. ≤ ₹1) with mandatory
    evidence and human approval is safer. Never hide a difference; record it.
29. **"90% match rate on simple cases" is a weak acceptance bar.** Exact matches
    should be ~100%; fuzzy matches should be measured separately with precision
    and recall.
30. **Timeline is unrealistic.** "Core engine in 1–2 months" while the founder
    learns to code, followed by nine more phases, is a multi-quarter build.
    Investors should see a milestone plan, not fixed dates.
31. **Bank statement PDF parsing varies by bank.** There is no standard layout;
    PDF extraction is materially harder than CSV/Excel. Plan per-bank adapters
    and a manual mapping fallback.
32. **Vendor/customer master deduplication is missing** (same party with
    different spellings/GSTINs). This affects reconciliation and GST matching.
33. **"Learns each company's patterns"** raises DPDP purpose-limitation
    questions if data is used for model training. Prefer retrieval/memory per
    tenant without training on client data.
34. **No definition of "completion rate" or "trivial entry"**, so the headline
    metrics are not measurable as written.
35. **No multi-currency decision.** Indian SMEs often receive USD invoices.
    Deferring is fine, but say so.
36. **No professional-liability / engagement model.** Who is responsible for a
    wrong entry? Human sign-off helps, but terms, insurance and disclaimers are
    needed. ICAI advertising/partnership rules also need checking.
37. **Marketing language** ("autonomous AI accountant", "minimal human
    intervention") conflicts with the correct control model (AI proposes,
    qualified human approves). Keep "assistant/coworker" language and avoid
    implying the software takes professional responsibility.

## D. Claims that must be re-verified before external use

- Every competitor capability, market-focus and pricing claim.
- Zoho Books India and Xero India pricing and GST/e-invoice capability.
- The ₹5,000–15,000/month pricing assumption, including LLM/OCR/support costs.
- "No competitor does X" claims.
- Any statement about ICAI, RBI, GSTN or DPDP obligations.
- Market size and SME tool-usage statistics (none are actually sourced).

## E. What the document gets right

- The overall problem framing (messy Indian SME books, GST burden, month-end
  drudgery) is plausible and worth validating with pilot interviews.
- AI proposes, human approves; deterministic maths; independent verification;
  evidence trails; no LLM arithmetic — all correct and adopted as project rules.
- Phased delivery and pilot-based validation are the right shape.
- India-first focus (INR, GST, Tally/Excel reality) is a sensible wedge.

## F. Decisions I am making unless you object

1. Build for **Companies Act / Schedule III-style SME reporting** first, not
   Ind AS. Mark framework choice `NEEDS CA REVIEW`.
2. Treat **GST rates, thresholds and TDS as versioned configuration**, not code
   constants, and block anything unknown.
3. Use **Anthropic** for LLM features, behind a code-validated interface. No
   LLM in any maths path.
4. Support **CSV/Excel first**; PDF/OCR invoices and bank PDFs come later with
   per-format adapters.
5. Do **not** claim GST filing. Produce **drafts for CA review** only.
6. Do **not** integrate bank APIs until the AA/FIU path is legally assessed.
