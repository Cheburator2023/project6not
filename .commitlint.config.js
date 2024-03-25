let pullRequestRegexp = /^Pull request #\d+:.*/s;
module.exports = {
    extends: ['@commitlint/config-conventional'],
    ignores: [(commit) => pullRequestRegexp.test(commit)],
    rules: {
        "body-max-line-length": [1, "always", 100],
    },
};