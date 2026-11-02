# Tavi v0.23: inventory-bound routing review

`route --coverage-requirements REQUIREMENTS.json` prepares an optional review of the explicit operations against the current eligible installed-skill metadata. The reviewer can select installed skill IDs, including unfamiliar names, or identify work the host can handle directly without a skill. Apply its structured answer with `--coverage-answer ANSWER.json`.

The workflow reuses the existing offline coverage packet format. It partitions the complete supplied eligible inventory without truncating packets, combines support across packets, enforces exclusions and rejects answers after the task, requirements or inventory changes. Pending reviews and uncovered operations withhold the provider launch plan. Explicit skills, required policies and model selection retain priority. See [the complete round trip and limits](Features-route-coverage.md).

This is an advisory review workflow. The caller checks that its operation list covers the full task. Reviewer identity, skill behaviour and direct-host capability are unverified; probability remains null. No review or download is performed automatically. These changes do not qualify the standalone policy models or automatic target clicks.

Vision-cache age checks now use integer nanoseconds. Windows file and wall timestamps could round differently as floats, making a fresh observation appear a fraction of a microsecond in the future and causing redundant preparation. The integer comparison preserves strict future/expired rejection and the existing TTL. Cached observations still grant no action authority. No new end-to-end speedup is claimed.

Validation: 307 tests pass in an isolated release-shaped checkout, including strict timestamp-boundary cases. A guarded offline CLI trial checks default routing parity, reviewed selection of an unfamiliar installed skill, direct-host advice, pending-launch withholding and stale-description rejection. It prepares a native Claude plan while forbidding network connections and child-provider processes. Live Claude account access remains untested.

Accepted model files are unchanged. Inactive research models and private operator records are excluded from the release allowlist.
