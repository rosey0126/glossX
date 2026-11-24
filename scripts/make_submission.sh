#!/usr/bin/env bash
# Build the COMP7608B submission ZIP from the current commit.
#   scripts/make_submission.sh [path/to/report.pdf]
# Output: dist/Group35_GlossX_submission.zip with the source snapshot (git archive, so ignored files,
# local data and credentials are never included), the report PDF and VERSION.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
report="${1:-submission/GlossX_Final_Report.pdf}"
if [ ! -f "$report" ] && [ -f report/latex/main.tex ] && command -v latexmk >/dev/null; then
  (cd report/latex && latexmk -pdf -interaction=nonstopmode main.tex >/dev/null) && cp report/latex/main.pdf "$report"
fi
[ -f "$report" ] || { echo "report PDF not found: $report" >&2; exit 1; }
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "warning: uncommitted changes are NOT in the snapshot; commit them first" >&2
fi
commit=$(git rev-parse HEAD)
mkdir -p dist
tmp=$(mktemp -d)
git archive --format=tar --prefix=GlossX/ HEAD | tar -x -C "$tmp"
mkdir -p "$tmp/GlossX/submission"
cp "$report" "$tmp/GlossX/submission/GlossX_Final_Report.pdf"
printf 'Group 35 GlossX\ncommit %s\nbranch %s\nbuilt %s\n' "$commit" "$(git rev-parse --abbrev-ref HEAD)" "$(date -u +%FT%TZ)" \
  > "$tmp/GlossX/submission/VERSION.txt"
# refuse to ship anything that looks like a secret
if grep -rIlE '(sk-[A-Za-z0-9]{20,}|ANTHROPIC_API_KEY=.+|OPENAI_API_KEY=.+|BEGIN (RSA|OPENSSH) PRIVATE KEY)' "$tmp/GlossX" \
     --exclude-dir=node_modules | grep -v -e 'tests/' -e '\.md$' ; then
  echo "possible credential found above; aborting" >&2; rm -rf "$tmp"; exit 1
fi
out="$PWD/dist/Group35_GlossX_submission.zip"
rm -f "$out"
(cd "$tmp" && zip -qr "$out" GlossX)
rm -rf "$tmp"
echo "wrote $out ($(du -h "$out" | cut -f1)) from $commit"
