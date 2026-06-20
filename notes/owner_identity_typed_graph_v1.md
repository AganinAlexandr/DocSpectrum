# Owner-identity typed graph v1

## Why v1

RP-039 accepted the library-relative owner-identity method but found that the
v0 connected components mixed different causal relations:

- organization rename;
- disclosed lead/subcontractor production network;
- shared-GIP handwriting transfer;
- handwriting-only owner-or-template hypotheses.

v1 does not recalculate similarity. It types the existing `12` v0 edges and
builds components separately by edge type.

## Edge priority

1. `disclosed_subcontract_network`
   - at least one four-title lead/sub object;
   - explicit production relation, not hidden common ownership.
2. `rename_candidate`
   - rare handwriting candidate;
   - shared GIP;
   - temporal handoff score `>= 0.40`.
3. `shared_gip_handwriting`
   - rare handwriting candidate plus shared GIP;
   - insufficient temporal handoff for rename.
4. `owner_or_template_candidate`
   - rare handwriting candidate without independent identity evidence.

The four-title class has priority. A disclosed subcontract relation is never
upgraded to hidden ownership because other signals happen to overlap.

## Result

Typed edges:

- rename: `1`;
- disclosed subcontract network: `2`;
- shared-GIP handwriting: `1`;
- owner-or-template: `8`.

Typed components: `7`.

### Rename core

`АО ССУ № 3 | Комтех`

The confirmed rename pair is no longer expanded by handwriting-only links.

### Disclosed production network

`Ватага | ИнфраСтройИнтекс | Спектр`

These links are explained by four-title disclosure.

### Shared-GIP handwriting

`Ватага | СП Стройинвест ГРУПП`

The common GIP is `сергеев`, but temporal evidence does not support calling
the relation a rename.

### Owner-or-template research components

1. `АО ССУ № 3 | Комтех | Сфера`;
2. `Горизонт | ЛСТехникс | СВАЙТЕК-М | ТрансРегионСервис | Экономный Дом`;
3. `Мир | ООО К1`;
4. `РусСтройГрупп | СитиГазСтрой`.

These remain ambiguous and must not be merged into rename/network cores.

## Attachment guard

Three non-core links touch a core component:

- `АО ССУ № 3 <-> Сфера`;
- `Комтех <-> Сфера`;
- `Ватага <-> СП Стройинвест ГРУПП`.

They are emitted as `unvalidated_attachment_to_core`, not as component
expansion.

The two Sphere links also have `large_org_template_noise_risk=True`. Sphere is
the largest organization in the registry (`79` objects); its links have no
shared GIP or four-title corroboration. This directly closes the main RP-039
observation without declaring the links false.

## Anchor behavior

- `Комтех -> АО ССУ № 3`: `rename_candidate`;
- `Ватага <-> Спектр`: `disclosed_subcontract_network`;
- `Тиволион <-> ООО К1`: remains a matrix coverage gap.

## Interpretation boundary

- edge type describes the strongest observed explanation in the current
  library;
- `rename_candidate` is still a candidate, not a registry fact;
- `owner_or_template_candidate` intentionally preserves ambiguity;
- attachments do not inherit the interpretation of the core they touch;
- IUL personnel data remains validation-only and is not used in v1.
