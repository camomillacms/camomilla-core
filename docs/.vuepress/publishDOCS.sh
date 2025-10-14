#!/usr/bin/env sh

set -e

echo "==> Preparing to publish docs"

./docs/.vuepress/moveCHANGELOG.sh

# build
echo "==> Building docs"
npm run docs:build

# navigate into the build output directory
cd docs/.vuepress/dist

echo "==> Initializing temporary git repo"

REPO_SLUG="camomillacms/camomilla-core"
TARGET_BRANCH="master:gh-pages"
SOURCE_REF="master"

git init -q
git add -A
commit_msg="docs: publish $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
git commit -m "$commit_msg" >/dev/null 2>&1 || echo "Nothing to commit"


if [ -n "${GITHUB_ACTIONS:-}" ]; then
	echo "==> Detected GitHub Actions environment"
	: "${GITHUB_TOKEN:?GITHUB_TOKEN is required in CI}"
	git config user.name "github-actions[bot]"
	git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
	REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_SLUG}.git"
else
	echo "==> Local environment; using SSH push (ensure you have access)"
	REMOTE_URL="git@github.com:${REPO_SLUG}.git"
fi

echo "==> Pushing to ${REPO_SLUG} ${SOURCE_REF}->${TARGET_BRANCH} (force)"
git push -f $REMOTE_URL $TARGET_BRANCH

cd - >/dev/null 2>&1
echo "==> Docs published"