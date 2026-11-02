# Inventory-bound routing review

Available in v0.23. Standalone policy models remain below their required accuracy targets; this optional review path does not qualify them.

Normal `route` behaviour is unchanged. The calling agent supplies the explicit operation list and must check it against the full task; Tavi does not verify that this decomposition is complete. With explicit requirements, Tavi prepares packets containing the full task and every operation, split across the complete supplied eligible inventory. It makes no model or network request for this review. The current Codex chat or another explicitly chosen reviewer can assess the descriptions and return the structured answer.

Save a UTF-8 JSON array as `requirements.json`, for example:

```json
["Build the settings interface", "Summarize the supplied notes"]
```

Prepare a route:

```text
python tavi.py route "Build the settings interface and summarize the supplied notes" --coverage-requirements requirements.json
```

The result has `status: needs_review` and a `capability_review` object. Review **every** packet. Use its current context and packet IDs, never the illustrative IDs below. An answer can select installed skill IDs for an operation or identify an operation that the host can handle directly:

```json
{
  "context_id": "COPY_CURRENT_CONTEXT_ID",
  "native_requirement_ids": ["r1"],
  "reviews": [
    {
      "packet_id": "COPY_CURRENT_PACKET_ID",
      "coverage": [
        {"requirement_id": "r0", "skill_ids": ["CURRENT_INSTALLED_SKILL_ID"]},
        {"requirement_id": "r1", "skill_ids": []}
      ]
    }
  ]
}
```

If there are several packets, include each once, with every requirement once per packet. Only cite skills present in that packet. Supporting skills are combined across packets. For a direct-host operation, leave its skill list empty in every packet and put its requirement ID in `native_requirement_ids`. That field is optional; omitting it makes no direct-host claim. A requirement cannot simultaneously claim direct handling and list supporting skills.

Apply the answer to the same task, requirements and current inventory:

```text
python tavi.py route "Build the settings interface and summarize the supplied notes" --coverage-requirements requirements.json --coverage-answer answer.json --plan
```

Use the same `--exclude-skill` options in both requests. Excluded skills are omitted from review and cannot be returned as support. Explicit and required-policy skills retain priority. Reviewed skill IDs can select an installed skill even when its name was not learned by the local model. A complete answer replaces the local skill/discovery recommendation; it does not change the predicted model tier or upgrade an already-withheld model route.

Pending or incomplete coverage withholds the provider launch plan. Uncovered operations suggest the existing AwesomeSkill discovery workflow and keep installation authorization false. Once all operations have supplied coverage or direct-host advice, the existing `--plan`/explicit `--execute` behaviour can apply if ordinary model routing is eligible. Execution still uses the native provider and its existing permissions; the review itself grants no execution authority. Claude support stays offline unless an explicit provider execution is requested.

Review packets are bound to the full task, requirement order, current eligible skill IDs/names/descriptions and exclusions. Inventory ordering and packet-answer ordering do not matter. Changed content rejects a stale answer. At most 1,000 supplied descriptions are accepted. The CLI uses the existing metadata scanner, which caps each description at 700 characters; coverage claims concern this supplied metadata, not every instruction in each skill file. Packets contain at most 100 descriptions and 128 KiB each; splitting observes actual UTF-8 bytes without truncation. The collection is bounded at 2 MiB, and input JSON at 256 KiB. Only one input may use stdin (`-`). Duplicate JSON fields, IDs, packets or requirement answers are refused.

`probability` remains null. Reviewer identity, native capability and skill behaviour remain unverified. Descriptions are untrusted claims, not proof of functioning code, permission or task success. This workflow neither downloads skills nor changes the target-confidence/automatic-click gates. Unit tests establish software behaviour; they are not a new accuracy or computer-use speed benchmark.
