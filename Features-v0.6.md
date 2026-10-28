# Tavi v0.6 — AwesomeSkill discovery

AwesomeSkill is now the default external discovery source: https://awesomeskill.ai/search?sort=stars. Query filtering uses the site's q parameter, verified from its public client and live results.

The accepted CPU model still predicts when external skill discovery may be useful. Provider choice is an explicit user preference, and candidate ordering is task keyword overlap followed by repository stars. No claim of trained candidate ranking, marketplace trust or improved model accuracy is made. Weights and existing learned decisions are preserved.

Discovery reads bounded public metadata without running page scripts. Candidates have an upstream repository, validated SKILL.md path and structured source-review command; installed duplicates are marked. Marketplace descriptions and ratings remain untrusted data. Source review still pins a Git commit, hashes files, checks licence/dependencies and permits only passive staging. Discovery does not install or execute skills.

One result page is read, not the entire catalog. No relevant results and provider failures are separate outcomes; GitHub search is available explicitly with --provider github. The adapter reports upstream format changes rather than silently claiming an empty successful search.

Validation on 28 October 2026: all78 tests pass; live Blender-materials discovery returns the relevant candidate first after the reported one-keyword retry. Its upstream source review pins commit a2634b588e80265e796aa53f8ab178d75105c2af and reports MIT, no static findings and download_for_review; no skill installed or executed. Bundled/installed skill frontmatter validates. Accepted v2 weights retain SHA256 b4c6c1c55ff09899dafc38455fbf5accdaee3e079b05d0de0b76c153b5ae8bc7.

Routing launch plans also carry the AwesomeSkill discovery preference when the learned model recommends external search. Plans remain unexecuted; no hosted task is needed to verify this behavior.
