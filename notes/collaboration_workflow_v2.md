# Collaboration workflow v2 для DocSpectrum

## Основание

Shared-основание:

- `checker-shared-project`
- `DEC-20260614-004 Collaboration workflow v2`
- `E:/repos/checker-shared-project/docs/06_decisions.md`

## Роли

Для проекта `DocSpectrum` принимается схема:

- `Codex` - generator / основной исполнитель;
- `Opus` - reviewer;
- `human` - strategic owner.

## Правило разделения проектов

Этот чат ведёт только `DocSpectrum`.

Решения, артефакты, метрики и обсуждения `Checker` не смешиваются с `DocSpectrum`, кроме случаев, когда явно переносится общий workflow, инфраструктурный шаблон или shared-решение.

## Практическое применение

Для заметных этапов `DocSpectrum` следует готовить review packet для Opus:

- ссылка на коммит или набор изменённых файлов;
- входные данные;
- главные метрики;
- что проверено;
- что не трогалось;
- доменные правила или методические решения;
- открытые вопросы для reviewer.

Канонический shared-шаблон для `DocSpectrum`:

- `E:/repos/checker-shared-project/projects/docspectrum/review_packets/README.md`

Важно:

- `range` и `focus` обязательны;
- reviewer смотрит committed diff, а не весь проект;
- полноценный packet создаётся атомарно вместе с push/commit рабочего репозитория.

Shared-слой используется как координационный слой, а не как место хранения кода `DocSpectrum`.
