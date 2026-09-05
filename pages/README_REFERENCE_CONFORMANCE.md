# Pages Reference Conformance

This directory contains scientific HTML reports that must remain faithful to the source code.

## Mandatory rules
- All text must be written in English.
- The content must remain scientific and factual.
- The HTML must reflect the actual implemented behavior.
- No marketing claims or unsupported statements are allowed.

### Measured state of the English rule — 2026-09-06

**13 of the 15 pages declare `lang="en"`. Two do not**, and this is recorded rather than
silently tolerated: `alternative_swanepoel.html` and `rapport_certus_complet.html` are
`lang="fr"`. Either they are brought into English or the rule above gains a stated exception —
what must not happen is a rule that everyone reads as universal while two files contradict it.
*(Compare `CLAUDE.md` interdit n° 11, which enumerates its French exceptions precisely so that
nobody "corrects" them by mistake.)*

### `CERTUS_STRAT.html` has its own regime, and it is stricter

**`CLAUDE.md` §1 is the authority on that page**, not this README. It is a commercial and
technical showcase on a public repository, and the rule there is sharper than "no marketing
claims": **every number must be traceable to the code or to an artefact in `reports/`**, the
page must show its own limits, and its HTML structure must be re-parsed after every edit —
a deleted `</ul>` once swallowed an entire bullet and rendered 400 lines inside a list.

## Review order
1. METAL pages
2. STRAT pages
3. INDEX and INDEX SPLINE pages
4. RE and DESIGN pages
5. Supporting documentation pages

## Validation principle
Each HTML page must answer one question:

> Does this document describe exactly what the code does, in scientific English, without embellishment?

If the answer is no, the page must be corrected.
