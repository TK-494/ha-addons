#!/bin/sh
# Refuse to let personal data into the repository.
#
# Run from the repo root, or wire it up as a pre-commit hook:
#   ln -s ../../financials/scripts/check-no-personal-data.sh .git/hooks/pre-commit
#
# Checks the *tracked* tree, because that is what a commit actually publishes.
set -eu

cd "$(git rev-parse --show-toplevel)"
status=0

fail() {
    echo "BLOCKED: $1" >&2
    status=1
}

# Real Dutch IBANs. The synthetic fixtures deliberately use NL00TEST…, which is
# excluded here so the tests stay committable.
if git grep -nIE '\bNL[0-9]{2}(RABO|ASNB|INGB|ABNA|SNSB|TRIO|KNAB|BUNQ|RBRB|FVLB)[0-9]{10}\b' \
     -- . ':!*/fixtures/*' >/dev/null 2>&1; then
    fail "a real-looking Dutch IBAN is present"
    git grep -nIE '\bNL[0-9]{2}(RABO|ASNB|INGB|ABNA|SNSB|TRIO|KNAB|BUNQ|RBRB|FVLB)[0-9]{10}\b' \
        -- . ':!*/fixtures/*' >&2
fi

# Bank exports, databases and anything else that carries transactions.
for pattern in '*.db' '*.sqlite' '*.sqlite3' 'CSV_A_*' 'RA_CC_*' 'transactie-historie*'; do
    if git ls-files --error-unmatch "$pattern" >/dev/null 2>&1; then
        fail "tracked file matching $pattern"
    fi
done

# A committed CSV is only ever acceptable as a synthetic fixture.
for file in $(git ls-files '*.csv'); do
    case "$file" in
        */fixtures/*) ;;
        *) fail "CSV outside tests/fixtures: $file" ;;
    esac
done

if [ "$status" -eq 0 ]; then
    echo "OK: no personal data found in tracked files."
fi
exit "$status"
