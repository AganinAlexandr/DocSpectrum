# Analytics Layer

Эта папка хранит слой передачи данных из исследовательских артефактов `DocSpectrum` в Excel/Power Query.

Назначение слоя:

- дать быстрый визуальный контроль динамики проекта;
- смотреть не только сырые элементы, но и развитие результатов сравнения;
- подключать Excel к стабильным CSV/JSON-артефактам без ручной подготовки;
- сохранять лёгкий журнал проектных событий и методических решений.

## Структура

- `pq/` - Power Query M-запросы для подключения из Excel;
- `tables/` - небольшие ручные и проектные таблицы для динамики проекта;
- `excel/` - сгенерированные Excel-снимки.

## Режимы использования

### Power Query

В Excel можно создать пустые запросы и вставить код из `.pq` файлов.

Базовый параметр:

- `pDocSpectrumRoot` - путь к корню репозитория `DocSpectrum`.

После настройки параметра остальные запросы читают CSV/JSON из:

- `samples/element_base_v0`;
- `samples/comparison_results_v0`;
- `samples/detailed_comparison_results_v0`;
- `analytics/tables`.

### Статический Excel-снимок

Для быстрого просмотра текущего состояния можно запустить:

```powershell
python -B E:\repos\DocSpectrum\tools\build_excel_snapshot_v0.py
```

Результат:

- `analytics/excel/DocSpectrum_dynamics_v0.xlsx`

Файл является снимком текущих CSV, а не заменой Power Query.
