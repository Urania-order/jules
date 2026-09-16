Co-SMOS Operating Constitution
Version: 1.0
Status: Normative
Scope: Urania-order/jules · Co-SMOS · Jules agent
Supersedes: all ad-hoc practices
Change policy: зміни лише через ADR + PR у docs/

§0. Призначення
Цей документ визначає обов'язковий життєвий цикл задачі, правила взаємодії з Jules, правила git, правила артефактів і критерії завершеності.

Мета — щоб майбутній агент (Jules, інший AI, або людина) міг відновити не лише WHAT було зроблено, а й WHY, і повторити це відтворювано.

§1. Еталонний життєвий цикл задачі
text
REQUEST
  → TASK RECORD
    → DEDICATED BRANCH
      → ANALYZE
        → PLAN
          → IMPLEMENT
            → TEST
              → REVIEW
                → PULL
                  → ACCEPTANCE
                    → COMMIT
                      → STATE
                        → HISTORY / ADR
Кожна стрілка — обов'язковий артефакт. Пропуск етапу = незавершена задача.

§2. Модель життєвого циклу (формально)
#	Етап	Артефакт	Відповідальний
1	REQUEST	текст задачі	Human
2	TASK RECORD	.jules/tasks/task-<id>.md	Orchestrator
3	DEDICATED BRANCH	jules/task-<id>	Orchestrator
4	ANALYZE	розділ у task record	Jules
5	PLAN	розділ у task record	Jules
6	IMPLEMENT	код / тести / docs	Jules
7	TEST	лог тестів	Jules
8	REVIEW	звіт за §14 AGENTS.md	Jules
9	PULL	jules remote pull --session <id> --apply	Human/Orchestrator
10	ACCEPTANCE	перевірка diff + tests + errata check	Human
11	COMMIT	2 коміти (код + артефакти)	Human
12	STATE	.co-smos/state.json оновлено	Orchestrator
13	HISTORY / ADR	.jules/history/adr-*.md + history	Jules + Human
§3. Правила роботи Jules
Jules має право:

читати весь репозиторій

змінювати код, тести, документацію (frontend/, smos/, tests/, docs/, scripts/)

створювати ADR у .jules/history/

запускати тести

Jules зобов'язаний
перед початком прочитати .jules/errata/INDEX.md і релевантні errata (AGENTS.md §27)

працювати лише на jules/task-<id>, ніколи на main/master

у фінальному звіті додати секцію ERRATA CHECK

дотримуватись AGENTS.md §14 (формат звіту)

Jules категорично не має права:

змінювати main / master напряму

редагувати заборонені шляхи (див. §4)

комітити секрети (.env, токени, ключі)

видаляти існуючу функціональність без явної вказівки

переписувати історію git

робити git push --force

змінювати сам Co-SMOS Operating Constitution без ADR

§4. Заборонені шляхи (Forbidden Paths)
Jules не повинен редагувати:

text
.co-smos/          ← локальний стан оркестратора
.jules/tasks/      ← картки задач, створені оркестратором
.jules/results/    ← логи сесій, створені оркестратором
.jules/queue/      ← runtime-стан черги
Це артефакти оркестратора, а не код проєкту. Спроба Jules їх змінити = дефект процесу, який треба зафіксувати як errata.

Jules може:

читати будь-що з переліченого вище

створювати нові ADR у .jules/history/

створювати нові errata у .jules/errata/

§5. Правила гілок
Кожна задача — окрема гілка: jules/task-<YYYYMMDD-HHMMSS>

Гілка створюється до відправки задачі в Jules

main оновлюється лише через PR зі squash-merge

Після merge: git branch -d jules/task-<id> (або -D, якщо squash створив новий хеш)

Ніколи не працювати напряму на main

§6. Правила git
Дозволено:

git add <конкретні файли>

git commit -m "..."

git push -u origin jules/task-<id>

git checkout main && git pull origin main

git stash push -u / git stash pop

Заборонено:

git add . — ніколи (захоплює .jules/queue/, runtime-стан)

git add -A — ніколи (те саме)

git push --force

git rebase на опублікованих гілках

git commit --amend на опублікованих комітах

git reset --hard на чужих гілках

Правило двох комітів:

Коміт коду й інфраструктури від Jules

Коміт артефактів Co-SMOS (.co-smos/, .jules/tasks/, scripts/jules-task.sh)

§7. Правила state.json
.co-smos/state.json — єдине джерело істини про оркестрацію.

Поля:

json
{
  "version": 1,
  "project": "jules-codespace",
  "agent": "jules",
  "status": "ready | running | failed",
  "active_task": {
    "id": "task-<id>",
    "session_id": "<jules session>",
    "branch": "jules/task-<id>",
    "repository": "https://github.com/...",
    "request": "...",
    "started_at": "ISO8601"
  },
  "last_task": {
    "id": "...",
    "status": "completed | failed",
    "session_id": "...",
    "branch": "...",
    "request": "...",
    "started_at": "...",
    "finished_at": "..."
  },
  "history": [ ... ],
  "meta": {
    "orchestrator": "jules-task.sh",
    "workflow": ["ANALYZE","PLAN","IMPLEMENT","TEST","REVIEW","REPORT"],
    "branch_policy": "every task runs on jules/"
  }
}
Правила:

Jules не редагує state.json (див. §4)

Orchestrator оновлює state.json при старті та завершенні

active_task існує лише під час виконання

Після завершення: active_task = null, last_task = completed, запис у history

§8. Task Records
Кожна задача має картку .jules/tasks/task-<id>.md:

markdown
# Jules Task

## Task ID
task-<YYYYMMDD-HHMMSS>

## Created
<ISO8601>

## Repository
<URL>

## Origin branch
main

## Work branch
jules/task-<id>

## Request
<текст>

## Status
started | completed | failed

## Timeline
- <ISO8601> task dispatched to Jules
- <ISO8601> pulled
- <ISO8601> merged
Картка — append-only під час життя задачі.

§9. Consult Access (RBAC) & Logs

### 9.1 Consult Access and Role-Based Access Control (RBAC)
Co-SMOS v0.9 provides Role-Based Access Control (RBAC) for API consult endpoints and mutation operations.

#### Environment Variables & Tokens
Access authentication relies on Bearer tokens configured via environment variables:
- `JULES_CONSULTANT_TOKEN` (default: `"dev-consultant-token"`)
- `JULES_OPERATOR_TOKEN` (default: `"dev-operator-token"`)
- `JULES_ADMIN_TOKEN` (default: `"dev-admin-token"`)

> **SECURITY WARNING:** Tokens MUST NOT be committed to git or stored in browser `localStorage`. Real secret tokens must be provided via env vars in deployment environments.

#### Roles and Permissions Matrix
| Role | Allowed Endpoints / Actions | Description |
|---|---|---|
| **consultant** | `GET /api/consult/*` only | External AI consultants (e.g., DeepSeek). Read-only surface strictly forbidden from performing any state mutations. |
| **operator** | consultant + `POST /api/tasks`, `PATCH /api/tasks/{id}`, `POST /api/proposals`, `POST /api/proposals/{id}/accept`, `POST /api/batch/run` | Trusted human operators for standard operational tasks and queue/batch controls. |
| **admin** | operator + system configuration endpoints | Trusted system administrators with full administrative capabilities. |

#### External AI Consultant Authentication (e.g. DeepSeek)
- External AI consultants such as DeepSeek MUST be assigned the `consultant` role only using `JULES_CONSULTANT_TOKEN`.
- Requests must include the HTTP header: `Authorization: Bearer <JULES_CONSULTANT_TOKEN>`.
- `consultant` access is strictly read-only (`GET /api/consult/*`). Any write attempt (POST, PATCH, PUT, DELETE) returns `403 CONSULT_ROLE_FORBIDDEN`.
- Unauthenticated requests return `401 CONSULT_AUTH_REQUIRED` (except `GET /api/consult/health?public=1` which allows public monitoring).
- Trusted roles (`operator` and `admin`) are reserved exclusively for authorized human operators.

### 9.2 Logs
.jules/results/task-<id>.log — повний вивід jules remote new і jules remote pull.

Правила:

не редагувати вручну

не видаляти (навіть при помилці)

використовувати для reconstruction

§10. Review
Рев'ю виконує Human (або окремий агент). Обов'язкові перевірки:

diff відповідає задачі

тести проходять (pytest, validate.sh)

немає секретів

немає змін у заборонених шляхах

ERRATA CHECK присутній

ADR створено (якщо рішення архітектурне)

§11. Acceptance
Задача вважається завершеною, якщо:

□ task record заповнено
□ звіт Jules відповідає AGENTS.md §14
□ ERRATA CHECK присутній
□ git diff --check чисто
□ pytest tests/test_frontend_contract.py проходить
□ pytest tests/test_control_room_api.py проходить
□ ./scripts/validate.sh → exit 0
□ жодних змін у .co-smos/, .jules/tasks/, .jules/results/ від Jules
□ diff переглянуто людиною
□ PR створено та змерджено (squash)
□ state.json оновлено
□ ADR створено (якщо потрібно)
□ нові errata створено (якщо були нові помилки)
Будь-який пункт ❌ → задача не завершена.

§12. ADR (Architecture Decision Records)
ADR створюється, коли:

змінюється архітектура

приймається рішення, яке вплине на майбутні задачі

вводиться нове правило (як цей документ)

Формат: .jules/history/adr-<NNNN>-<slug>.md

markdown
# ADR-<NNNN>: <Title>

## Status
proposed | accepted | superseded

## Context
<чому виникло питання>

## Decision
<що вирішено>

## Consequences
<наслідки, позитивні й негативні>

## Alternatives considered
<що ще розглядалось>
§13. Errata
Errata — каталог відомих помилок, щоб вони не повторювались.

Правила:

.jules/errata/INDEX.md — індекс

.jules/errata/errata-<NNNN>-<slug>.md — окремий файл

append-only (ніколи не видаляти)

ID послідовні

Jules зобов'язаний читати INDEX перед кожним завданням

Jules зобов'язаний створювати нову errata, якщо зробив нову помилку

у фінальному звіті — секція ERRATA CHECK

Формат errata:

markdown
# ERRATA-<NNNN>: <Title>

## Symptom
<що сталося>

## Cause
<чому>

## Fix
<як виправити>

## Prevention
<як не повторити>
§14. Replay / Reconstruction
Будь-яка задача має бути відтворюваною за:

task_id

branch

task record

log

diff / patch

tests

report

ADR (якщо є)

errata (якщо є)

history у state.json

Майбутній агент має відновити WHAT і WHY.

§15. Що ніколи не можна робити автоматично
git push --force

git rebase на main

git reset --hard на main

редагувати main напряму

видаляти errata

редагувати ADR заднім числом

комітити секрети

git add . / git add -A

редагувати .co-smos/state.json поза оркестратором

редагувати .jules/queue/

§16. Підказки на кожному етапі (Next-Step Hints)
Після кожного етапу система має видавати рекомендації — що робити далі, на що звернути увагу, які типові помилки.

Етап	Підказка
REQUEST	Переформулюй як конкретну задачу. Додай acceptance criteria. Посилання на errata, якщо є релевантні.
TASK RECORD	Перевір, що task_id, branch, repository заповнені.
BRANCH	Переконайся, що ти не на main. Якщо на main — orchestrator створить jules/task-<id>.
ANALYZE	Jules має прочитати AGENTS.md, .jules/errata/INDEX.md, існуючі тести. Підказка: «Чи є вже часткова реалізація? Не дублюй.»
PLAN	Якщо план зачіпає заборонені шляхи — STOP. Якщо план повторює відому errata — STOP.
IMPLEMENT	Мінімальна зв'язна зміна. Не дублювати функції. Не переписувати архітектуру.
TEST	Запустити pytest, validate.sh. Якщо тест не запускається — явно вказати чому.
REVIEW	Перевірити diff, секрети, заборонені шляхи, ERRATA CHECK.
PULL	Обов'язково --apply. Якщо конфлікт — git stash, pull, stash pop, вирішити конфлікти на користь локальної версії для state.json/tasks/.
ACCEPTANCE	Пройти чек-ліст §11. Будь-який ❌ — задача не завершена.
COMMIT	Два коміти. Ніколи git add ..
STATE	active_task → null, last_task → completed, запис у history.
HISTORY / ADR	Якщо рішення архітектурне — ADR. Якщо нова помилка — errata.
Автоматичні підказки в CLI:

Orchestrator після кожного етапу має виводити блок:

text
[Co-SMOS] Next steps:
  → <наступна команда>
  → Перевір: <що перевірити>
  → Типова помилка: <яка>
Це вбудовується в jules-task.sh, jules-complete.sh, jules-status.sh.

§17. Change policy
Цей документ змінюється лише через:

ADR у .jules/history/

PR у docs/

Squash-merge у main

Оновлення версії документа
vim docs/COSMOS-JULES-WORKFLOW.md
(вставити → Esc → :wq → Enter)


Зміни без ADR не мають сили.

§18. Підпис
Цей документ є частиною архітектури Co-SMOS.
Він має силу для Jules, для оркестратора, для людини-оператора і для будь-якого майбутнього агента.

Порушення будь-якого правила = дефект процесу, який фіксується як errata.

§19. Background Batch Scheduler (Co-SMOS v0.9)

Co-SMOS v0.9 provides an asynchronous background scheduler for running queued task batches within designated execution time windows.

### Default Schedules
The system pre-registers two default schedules:
- **`night`**: `02:00` - `06:00` UTC, all days (`mon` through `sun`).
- **`window`**: `09:00` - `18:00` UTC, workdays (`mon` through `fri`).

### Environment Variable Overrides
Default schedule boundaries can be overridden via environment variables without code modification:
- `JULES_SCHEDULE_NIGHT_START` (default: `"02:00"`)
- `JULES_SCHEDULE_NIGHT_END` (default: `"06:00"`)
- `JULES_SCHEDULE_WINDOW_START` (default: `"09:00"`)
- `JULES_SCHEDULE_WINDOW_END` (default: `"18:00"`)

### Background Execution Loop
- The scheduler runs as an asynchronous background loop within FastAPI using the `lifespan` context manager.
- Every 60 seconds, `bm.run_due_batches()` checks for batches in state `"queued"` whose schedule is currently due according to `is_due()`.
- When a batch is due, its status updates to `"running"`, and its queued tasks transition to `"RUNNING"` up to the specified `concurrency` limit.
- Once tasks are launched, the batch status is updated to `"completed"`.
- Batches with schedule `"now"` or `"now-sequential"` are handled immediately upon creation and are **never** modified or executed by the background loop.
- The background loop task is gracefully cancelled upon FastAPI application shutdown.

### Testing and Manual Trigger Endpoint
To prevent accidental background runs during test suites or manual operation, automated tests or operators can use the trigger endpoint:
- `POST /api/scheduler/trigger`: Forces an immediate check for due batches without waiting for the background loop interval.
- Schedules can also be checked directly using `is_due(name, now=...)` by passing a custom datetime object.

### Timezone Policy
- All schedule comparisons use **UTC** (`datetime.now(timezone.utc)`) by default.
- If necessary, local system timezone overrides can be provided via standard system `TZ` environment variables.
