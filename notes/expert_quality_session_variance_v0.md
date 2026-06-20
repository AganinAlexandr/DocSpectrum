# Expert quality session variance v0

This step implements experiment C step 4 after RP-042.

## Observation unit

The independent unit is:

`expert × organization × work type × session start date`.

KR and POS transferred in the same batch remain one session. Their section
codes stay visible in the artifact, but they do not become independent quality
observations. Duplicate registry lines for one object-section are collapsed.

## Outputs

Default output:
`E:/output/DocSpectrum/expert_quality_session_variance_v0`.

- `expert_quality_sessions_v0.csv` — one row per session;
- `expert_quality_session_variance_by_expert_v0.csv` — descriptive dispersion
  across sessions;
- `expert_quality_session_variance_v0.json` — counts and prime-batch checks.

The variance metrics use `clean_share_all_sections`, matching the registry
probe, and expose a parallel classified-only variance plus outcome coverage.
Unresolved outcomes therefore remain visible rather than being silently
treated as remarks or clean passes.

Because single-object sessions are mechanically binary, the expert summary
also reports the same clean-share statistics for multi-object batches only.

The primary conditional-mode diagnostic is polarization on multi-object
sessions with at least one classified outcome:

- `thorough`: classified clean share = 0;
- `skim`: classified clean share = 1;
- `mixed`: strictly between 0 and 1;
- `polarized`: thorough or skim.

Unresolved rows are excluded from the classified share, while their coverage
remains explicit. A whole session is excluded only when it has no classified
outcomes.

## Interpretation boundary

This is a descriptive proxy layer. It does not assign expert quality classes.
True recall variance remains blocked until remark content is available.
Monthly workload is not used as a causal explanation because the exploratory
correlation did not support it.

The fixed acceptance check confirms that the AO SSU No. 3 foundation holdout
batch from February 13, 2025 contains 10 objects and 20 KR/POS section records,
all clean, but contributes exactly one independent session observation.
