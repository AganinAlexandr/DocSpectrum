# Логическая модель результата сравнения

## 1. Назначение документа

Этот документ описывает логическую модель `результата сравнения` для проекта `DocSpectrum`.

Модель результата сравнения должна обеспечивать практическую ценность, зафиксированную в ТЗ:

- сравнение нового раздела с библиотекой ранее выполненных разделов;
- поиск ближайших аналогов и вероятных источников заимствований;
- определение типовых и индивидуальных частей раздела;
- сравнение версий одного раздела;
- выявление устойчивых типовых групп элементов;
- анализ проектных школ, организаций и исполнителей;
- построение доказательной базы сходства даже при неполном или искажённом текстовом слое.

## 2. Главный принцип

`section_passport` хранит данные конкретного раздела и не зависит от библиотеки.

`comparison_result` хранит всё, что появляется только в момент сравнения:

- с каким составом библиотеки сравнивали;
- какие признаки участвовали;
- какие библиотечные совпадения найдены;
- какие признаки не участвовали и почему;
- какие выводы сделаны о сходстве, шаблонности, самостоятельности и происхождении.

При добавлении нового раздела в библиотеку паспорта уже существующих разделов не должны пересчитываться. Пересчитываются только результаты сравнений, если нужно сравнить их с обновлённой библиотекой.

В более общей архитектуре `comparison_result` должен поддерживать сравнение не только разделов проектной документации, но и документов, комплектов документации и доменных профилей. Сравнение разделов ПД является первым и основным сценарием, но не должно жёстко ограничивать модель результата.

## 3. Верхнеуровневая структура

Рекомендуемая логическая структура:

```text
comparison_result
  schema
  comparison_identity
  comparison_scope
  library_snapshot
  compared_passports
  section_set_comparison
  feature_comparison_plan
  feature_comparisons
  similarity_summary
  axis_breakdown
  source_matches
  fragment_matches
  provenance_assessment
  typicality_assessment
  originality_assessment
  version_diff
  organization_and_designer_signals
  vector_space_analysis
  visualization_payload
  quality_and_coverage
  interpretation
  artifacts
  extensions
```

## 4. Блок `schema`

Блок описывает версию модели результата сравнения.

Рекомендуемые поля:

- `schema_name`
- `schema_version`
- `schema_status`
- `created_by`
- `created_at`
- `compatible_with`

## 5. Блок `comparison_identity`

Блок идентифицирует конкретный результат сравнения.

Рекомендуемые поля:

- `comparison_id`
- `comparison_type`
- `created_at`
- `created_by`
- `algorithm_name`
- `algorithm_version`
- `parameters`

Рекомендуемые значения `comparison_type`:

- `section_to_library`
- `section_to_section`
- `version_to_version`
- `object_to_library`
- `section_set_to_section_set`
- `corpus_analysis`

## 6. Блок `comparison_scope`

Блок определяет, что именно сравнивали и с какой целью.

Рекомендуемые поля:

- `goal`
- `query_level`
- `target_level`
- `included_axes`
- `included_feature_groups`
- `excluded_feature_groups`
- `filters`

Примеры `query_level` и `target_level`:

- `section`
- `object`
- `project`
- `corpus`

## 7. Блок `library_snapshot`

Блок фиксирует состояние библиотеки, с которым выполнялось сравнение.

Рекомендуемые поля:

- `library_snapshot_id`
- `library_version`
- `library_created_at`
- `included_passport_ids`
- `included_object_ids`
- `filters_applied`
- `feature_space_id`

Назначение:

- обеспечить воспроизводимость результата;
- понимать, почему результат изменился после пополнения библиотеки;
- не смешивать стабильный паспорт раздела с меняющимся состоянием библиотеки.

## 8. Блок `compared_passports`

Блок содержит ссылки на паспорта, участвующие в сравнении.

Рекомендуемые поля:

- `query_passport_id`
- `target_passport_ids`
- `baseline_passport_id`
- `candidate_passport_ids`

Правило:

результат сравнения не должен дублировать содержимое паспортов. Он должен ссылаться на них и хранить только результаты сопоставления.

## 9. Блок `section_set_comparison`

Блок используется, когда сравниваются не только отдельные разделы, но и наборы разделов внутри объекта или проекта.

Он нужен для оценки относительной доли изменений и сходства по разделам.

Практически важные разделы для первого этапа:

- `АР`
- `КР`
- `ПОС`
- `ЭС`
- `ОВ`
- `СС`

Рекомендуемые поля:

- `section_set_id`
- `included_section_types`
- `section_passport_refs`
- `section_level_similarity`
- `section_level_change_share`
- `section_level_weight`
- `dominant_changed_sections`
- `stable_sections`
- `missing_sections`
- `not_comparable_sections`

Назначение:

- видеть не только общий score по объекту, но и спектр изменений по разделам;
- понимать, какие разделы дают основной вклад в отличие объектов;
- сравнивать близкие дома по относительной структуре изменений;
- поддержать будущий анализ "до экспертизы / после экспертизы".

## 10. Блок `feature_comparison_plan`

Блок описывает, какие признаки должны были сравниваться.

Рекомендуемые поля:

- `feature_space_id`
- `planned_features`
- `axis_weights`
- `feature_weights`
- `required_features`
- `optional_features`
- `comparison_methods`

Назначение:

- зафиксировать план сравнения до учёта фактической доступности признаков;
- отделить методику сравнения от результата.

## 11. Блок `feature_comparisons`

Блок является центральным для модели результата сравнения.

Он должен хранить сопоставление каждого требуемого признака конкретного раздела с библиотечными данными.

Каждая запись может иметь:

- `feature_id`
- `feature_axis`
- `feature_group`
- `query_value_ref`
- `target_value_refs`
- `comparison_method`
- `similarity`
- `distance`
- `rank`
- `weight`
- `contribution`
- `coverage_status`
- `exclusion_reason`
- `confidence`
- `explanation`

`query_value_ref` и `target_value_refs` должны ссылаться на признаки, элементы, типовые группы элементов или векторы в паспортах, а не копировать их содержимое.

Рекомендуемые значения `coverage_status`:

- `compared`
- `excluded`
- `not_applicable`
- `missing_query`
- `missing_target`
- `low_confidence`

Рекомендуемые значения `exclusion_reason`:

- `excluded_zero_variance`
- `excluded_not_applicable`
- `excluded_missing`
- `excluded_low_confidence`

## 12. Блок `similarity_summary`

Блок хранит общий итог сравнения.

Рекомендуемые поля:

- `overall_similarity`
- `overall_distance`
- `overall_rank`
- `confidence`
- `coverage_coefficient`
- `matched_feature_count`
- `compared_feature_count`
- `excluded_feature_count`
- `top_explanatory_features`

Назначение:

- дать быстрый ответ, насколько раздел похож;
- показать, насколько результат надёжен;
- показать, за счёт каких признаков результат сформировался.

Важно:

общий `cosine_similarity` не должен трактоваться без проверки нормализации, весов и вклада доминирующих координат. Если одна крупная составляющая полного вектора почти не изменилась, общий косинус может скрыть существенные различия по другим подвекторам.

Поэтому рядом с общей оценкой сходства желательно хранить:

- косинусы по подвекторам;
- центрированные или иным образом нормализованные косинусы;
- относительные дельты признаков;
- вклад осей в общий результат;
- предупреждения о доминирующих признаках.

## 13. Блок `axis_breakdown`

Блок разлагает результат по осям анализа.

Рекомендуемые оси:

- `structural_axis`
- `text_spectral_axis`
- `text_semantic_axis`
- `graphics_axis`
- `text_graphics_links_axis`
- `typical_element_groups_axis`

Для каждой оси желательно хранить:

- `axis_similarity`
- `axis_distance`
- `axis_weight`
- `axis_contribution`
- `axis_cosine_similarity`
- `axis_centered_cosine_similarity`
- `axis_relative_delta_summary`
- `coverage_coefficient`
- `confidence`
- `top_matches`
- `top_mismatches`

## 14. Блок `source_matches`

Блок описывает ближайшие библиотечные источники сходства.

Рекомендуемые поля:

- `source_passport_id`
- `source_object_id`
- `source_project_id`
- `source_organization_id`
- `similarity`
- `rank`
- `coverage_coefficient`
- `matched_axes`
- `explanation`

Назначение:

- показать ближайшие аналоги;
- показать вероятные источники повторного использования;
- объяснить, почему именно эти источники попали в top-N.

## 15. Блок `fragment_matches`

Блок описывает совпадения на уровне фрагментов.

Рекомендуемые поля:

- `match_id`
- `match_class`
- `query_ref`
- `target_ref`
- `axis`
- `similarity`
- `confidence`
- `match_extent`
- `is_typical`
- `explanation`

Возможные значения `match_class`:

- `element_match`
- `typical_group_match`
- `text_fragment_match`
- `graphic_fragment_match`
- `page_layout_match`
- `text_graphics_link_match`

## 16. Блок `provenance_assessment`

Перед оценкой типичности, оригинальности, почерка и возможного заимствования
результат должен содержать блок `provenance_assessment`.

Он определяет:

- кто мог быть автором совпавшего материала;
- является ли источник внешним для обеих сравниваемых организаций;
- можно ли вообще передавать совпадение в слой проверки заимствования;
- какая часть материала остаётся в организационно-авторском остатке.

Third-party материал производителя, регулятора, программного продукта или
вендора исключается из copy-сигнала и из расчёта организационного почерка.
Неоценённый provenance блокирует интерпретацию заимствования и не считается
организационно-авторским по умолчанию.

Подробная модель: `provenance_assessment_model.md`.

## 17. Блок `typicality_assessment`

Блок оценивает долю типовых, библиотечных и повторно используемых частей.

Рекомендуемые поля:

- `typicality_score`
- `typical_feature_share`
- `typical_text_share`
- `typical_graphics_share`
- `typical_group_share`
- `typical_sources`
- `typical_fragments`

Назначение:

- ответить, какая часть раздела похожа на библиотечные или типовые решения;
- поддержать качественный анализ шаблонности.

## 18. Блок `originality_assessment`

Блок оценивает долю самостоятельной или не найденной в библиотеке части.

Рекомендуемые поля:

- `originality_score`
- `unmatched_feature_share`
- `unmatched_text_share`
- `unmatched_graphics_share`
- `unmatched_group_share`
- `unique_fragments`
- `low_confidence_unmatched_fragments`

Важно:

не найдено в библиотеке не всегда означает полностью авторское. Результат должен хранить это как аналитический признак, а не как окончательный юридический вывод.

## 19. Блок `version_diff`

Блок используется при сравнении двух версий одного раздела.

Рекомендуемые поля:

- `base_passport_id`
- `new_passport_id`
- `changed_features`
- `added_features`
- `removed_features`
- `changed_elements`
- `changed_typical_groups`
- `template_like_changes`
- `original_like_changes`
- `diff_summary`

Назначение:

- отделить обычный diff от качественного анализа изменений;
- показать, какие изменения похожи на шаблонные, а какие выглядят индивидуальными.

## 20. Блок `organization_and_designer_signals`

Блок хранит признаки, полезные для анализа организаций и исполнителей.

Рекомендуемые поля:

- `organization_similarity_signals`
- `designer_similarity_signals`
- `cross_organization_matches`
- `stable_style_features`
- `evidence_strength`
- `interpretation_limits`

Важно:

этот блок не должен формулировать юридическое доказательство авторства. Он фиксирует признаки сходства и силу аналитического сигнала.

## 21. Блок `vector_space_analysis`

Блок описывает сравнение в пространстве признаков.

Рекомендуемые поля:

- `feature_space_id`
- `full_vector_similarity`
- `axis_vector_similarities`
- `informative_subspace`
- `excluded_coordinates`
- `coverage_coefficient`
- `cosine_similarity`
- `distance_metrics`

`informative_subspace` должен фиксировать:

- какие координаты участвовали;
- какие координаты были исключены;
- почему они были исключены.

## 22. Блок `visualization_payload`

Блок хранит данные для последующей визуализации.

Рекомендуемые поля:

- `projection_sets`
- `axis_metadata`
- `point_coordinates`
- `cluster_labels`
- `highlighted_matches`
- `plotly_payload_ref`
- `d3_payload_ref`

Назначение:

- поддержать 2D/3D визуализацию;
- показать проекции на наиболее информативные или динамичные оси;
- дать экспертам инструмент для интерпретации сходства.

## 23. Блок `quality_and_coverage`

Блок описывает качество самого сравнения.

Рекомендуемые поля:

- `overall_confidence`
- `coverage_coefficient`
- `axis_coverage`
- `missing_query_features`
- `missing_target_features`
- `low_confidence_features`
- `known_limitations`
- `warnings`

Назначение:

- не только дать score, но и показать, насколько этому score можно доверять.

## 24. Блок `interpretation`

Блок содержит человекочитаемую интерпретацию результата.

Рекомендуемые поля:

- `summary`
- `main_reasons`
- `main_limitations`
- `recommended_next_steps`

Этот блок должен быть производным от машинных данных и не должен заменять структурированные блоки результата.

## 25. Блок `artifacts`

Блок хранит ссылки на внешние артефакты.

Примеры:

- отчёт в Markdown;
- CSV с совпадениями;
- JSON с детализацией;
- визуализация;
- диагностические файлы.

Рекомендуемые поля:

- `artifact_id`
- `artifact_type`
- `artifact_path`
- `created_at`
- `description`

## 26. Блок `extensions`

Блок для будущих расширений.

Требование:

экспериментальные данные могут попадать в `extensions`, но после стабилизации должны переноситься в явные блоки модели.

## 26. Минимальный состав MVP

Для первой версии результата сравнения обязательными следует считать:

- `schema`
- `comparison_identity`
- `comparison_scope`
- `library_snapshot`
- `compared_passports`
- `feature_comparison_plan`
- `feature_comparisons`
- `similarity_summary`
- `axis_breakdown`
- `source_matches`
- `fragment_matches`
- `typicality_assessment`
- `originality_assessment`
- `vector_space_analysis`
- `quality_and_coverage`

Можно отложить или оставить частично заполненными:

- `section_set_comparison`
- `version_diff`
- `organization_and_designer_signals`
- `visualization_payload`
- `interpretation`
- `artifacts`
- `extensions`

## 27. Открытые вопросы

- Какой уровень детализации нужен для `feature_comparisons`.
- Хранить ли все сравнения признаков или только значимые.
- Как задавать веса осей и признаков для разных типов разделов.
- Как фиксировать версию библиотечного среза.
- Как отличать отсутствие совпадения от низкого качества извлечения.
- Как строить `typicality_score` и `originality_score`.
- Как хранить результаты сравнения с очень большой библиотекой.
- Какие данные обязательно готовить для будущих `Plotly` и `D3` визуализаций.
- Как нормировать относительный вклад изменений по разным разделам объекта.

## 28. Связь с паспортом раздела

Модель результата сравнения зависит от `section_passport`, но не должна изменять его.

Правило:

- паспорт раздела описывает объект;
- результат сравнения описывает отношение объекта к другому объекту, версии или библиотеке.

Это разделение позволяет пополнять библиотеку без пересчёта паспортов уже обработанных разделов.
