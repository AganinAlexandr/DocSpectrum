# NK section clusters v0

This research layer checks whether same-section documents inside
`НК-Инжениринг` form internal similarity families.

The goal is diagnostic:

- detect whether "one organization" is internally uniform;
- identify possible template families or preparation packages;
- prepare a future check against author/performer labels when those become
  available.

It does not prove human authorship by itself.

## Tool

`tools/cluster_section_similarity_v0.py`

Input artifacts:

- pairwise scores:
  `E:/output/DocSpectrum/comparison_results_v0_3_nk_34/comparison_results_v0_3.csv`
- section documents:
  `E:/output/DocSpectrum/element_base_v0_nk_34/documents_index.csv`
- object metadata:
  `E:/output/DocSpectrum/cross_org_manifest_v0/cross_org_manifest_v0.csv`

Generated artifacts:

- `E:/output/DocSpectrum/nk_section_clusters_v0/section_cluster_summary_v0.csv`
- `E:/output/DocSpectrum/nk_section_clusters_v0/section_clusters_v0.csv`
- `E:/output/DocSpectrum/nk_section_clusters_v0/section_clusters_v0.json`

Thresholds:

- `0.75`: near-template / very close family;
- `0.60`: strong family;
- `0.45`: broader section style.

Clusters are connected components of same-section object graphs where an edge is
`idf_similarity_v0_3 >= threshold`.

## High-Level Result

Same sections inside NK are similar, but not as one uniform mass. The corpus
forms several internal families:

- `АР`, `ИОС5.1`, `КР`, `ПОКР` have clear high-similarity components;
- `ИОС5.4.1` is the most fragmented mass section;
- `СМ` has one large medium-threshold family but almost no very-high threshold
  clusters;
- `ПОС` has too few documents and remains weak/diagnostic;
- `1140_24` is an outlier in `ПОКР`, consistent with its separate contractor
  metadata (`Эргана`) and atypical packaging.

## Section Notes

### АР

At `0.75`, `АР` splits into multiple small high-similarity groups. Examples:

- `1811_25|1812_25|1814_25|1828_25|1829_25`
- `1826_25|1839_25|1856_25`
- `1202_24|1203_24|1204_24`
- several strong pairs such as `1860_25|1867_25`, `1832_25|1833_25`,
  `1853_25|1854_25`.

At `0.60`, it becomes two main families:

- a large Serpukhov-oriented family (`25` objects);
- the Dzerzhinsky series `1200_24..1205_24` (`6` objects).

### ИОС5.1

At `0.75`, the section is strongly clustered:

- one large family of `15` objects;
- another family of `11` objects;
- Dzerzhinsky family `1200_24|1202_24|1203_24|1204_24|1205_24`.

At `0.45`, the two large non-Dzerzhinsky families merge into a broader `27`
object style, while Dzerzhinsky remains its own family.

### ИОС5.4.1

This is the most important internal-cluster signal.

At `0.75`, the section has only small tight components:

- `1854_25|1855_25|1861_25|1864_25`
- `1813_25|1826_25|1835_25|1845_25`
- `1853_25|1859_25`
- `1200_24|1204_24`

At `0.60`, it still has six non-singleton components. This suggests multiple
internal template families or preparation packages, not one uniform NK pattern.

This is the best candidate section for testing the hypothesis:

> different internal clusters may reflect different project engineers, teams or
> inherited template lines.

### КР

At `0.75`, `КР` forms several strong groups:

- an 8-object family;
- a 5-object family;
- Dzerzhinsky `1202_24|1203_24|1204_24|1205_24`;
- smaller Serpukhov pairs/triples.

At `0.60`, it resolves into three main families:

- `15` objects;
- `11` objects;
- Dzerzhinsky `1200_24..1205_24`.

### ПОКР

`ПОКР` is very homogeneous except for outliers:

- at `0.75`, two large families of `13` and `12` objects;
- at `0.60`, almost everything merges into one `26` object component;
- `1140_24` remains isolated and should be treated as a real diagnostic outlier.

### СМ

`СМ` has weak very-high clustering:

- at `0.75`, only one strong pair: `1812_25|1833_25`;
- at `0.60`, a large `22` object family appears;
- pair `1865_25|1867_25` stays separate.

This suggests estimates are internally related, but exact preparation templates
vary more than in `ПОКР` or `ИОС5.1`.

### ПОС

Only `6` documents are present. No strong clusters at `0.75` or `0.60`.

At `0.45`, two weak pairs appear:

- `1202_24|1205_24`
- `1200_24|1201_24`

This section is too small for a stable conclusion.

## Interpretation

The NK corpus is internally clustered. The clusters likely reflect a mixture of:

- address/geography series;
- project package style;
- object-series effects inside a mostly uniform `ОВ+ГВС` NK corpus;
- the two `ОВ`-only objects as a control/edge case, not the main explanation;
- inherited templates;
- possible different internal authors/performers.

The current data does not prove different designers because author labels are
not yet connected to these objects/sections.

The next useful validation is across-section persistence:

- if the same object groups recur in `АР`, `КР`, `ИОС5.1`, `ИОС5.4.1`, then the
  cluster is likely an object-series or package-level effect;
- if a split appears mostly in one section, it becomes a stronger candidate for
  section-specific performer/template authorship.

## Next Step

Build a cluster co-occurrence matrix:

- rows: object pairs;
- columns: section codes;
- value: whether the pair is connected at threshold `0.60` or `0.75`.

This will distinguish object-series clusters from section-specific clusters.
