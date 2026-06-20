# Expert quality difficulty proxy v0

Experiment C step 5 builds an expert-independent spectral complexity proxy for
the pre-expertise documents admitted to the RP-042 arena.

## Raw axes

- page count;
- total PDF elements;
- elements per page;
- non-text structural elements per page;
- table cells per page.

Additional diagnostics retain maximum page load and component-mix entropy.

Each headline axis is transformed with `log1p`, converted to a midrank
percentile within the same section code (KR or POS), then equally averaged.
All raw values and per-axis percentiles remain available.

## Boundary

Difficulty uses only PSE structure and is computed before joining expert or
review outcome. The later session join is diagnostic, not causal.

This layer does not normalize remark recall yet because remark content is not
available. It prepares the denominator needed to distinguish an easy section
from a shallow review once recall can be measured.

Default output:
`E:/output/DocSpectrum/expert_quality_difficulty_v0`.
