# Логическая модель provenance assessment

## Назначение

`provenance_assessment` определяет предполагаемое авторство и источник
совпавшего материала до интерпретации организационного почерка или
заимствования.

Главный инвариант:

```text
overlap != copying
```

Совпадение может быть создано третьей стороной: производителем оборудования,
регулятором, программным продуктом, издателем или отраслевым источником. Такой
материал не является межорганизационным заимствованием между сравниваемыми
проектировщиками.

## Рекомендуемая структура

```text
provenance_assessment
  provenance_status
  authorship_scope
  source_class
  source_subclass
  distinctiveness_class
  borrowing_eligibility
  borrowing_signal_status
  reason_code
  confidence
  evidence
  org_authored_residual_status
```

## `provenance_status`

- `expert_assessed`;
- `model_assessed`;
- `unassessed`.

`unassessed` не может автоматически трактоваться как
`organization_authored`.

## `authorship_scope`

- `third_party`;
- `organization_authored`;
- `none`;
- `unresolved`;
- `unknown`.

## `source_class`

- `external_form`;
- `software_generated`;
- `vendor_technical_material`;
- `regulatory_material`;
- `project_content`;
- `no_material_match`;
- `unresolved`;
- `unassessed`.

## `distinctiveness_class`

- `shared_standard`;
- `shared_technical`;
- `distinctive`;
- `no_match`;
- `unknown`.

## `borrowing_eligibility`

- `eligible_for_review` — только для отличительного
  `organization_authored` материала;
- `ineligible_third_party`;
- `ineligible_no_match`;
- `blocked_unresolved`;
- `blocked_unassessed`.

Eligibility разрешает дальнейшую проверку, но не является вердиктом
заимствования.

## `borrowing_signal_status`

- `research_candidate`;
- `confirmed_non_copy`;
- `not_assessable`.

Юридические формулировки не входят в модель.

## Reason codes

- `PROVENANCE_THIRD_PARTY_FORM`;
- `PROVENANCE_SOFTWARE_GENERATED`;
- `PROVENANCE_VENDOR_TECHNICAL`;
- `PROVENANCE_ORG_AUTHORED_DISTINCTIVE`;
- `PROVENANCE_NO_MATERIAL_MATCH`;
- `PROVENANCE_UNRESOLVED`;
- `PROVENANCE_NOT_ASSESSED`.

## Организационно-авторский остаток

Организационный, ГИП- и исполнительский почерк анализируется только после
исключения third-party материала.

```text
document content
  - third-party forms
  - software-generated output
  - regulatory/vendor technical material
  = organization-authored residual
```

Если provenance не определён, остаток помечается как `not_available`, а не как
авторский.

## Связь с comparison result

`provenance_assessment` принадлежит результату сравнения, а не паспорту
раздела: источник и авторство совпадения устанавливаются относительно
библиотеки, внешних каталогов и экспертных данных.
