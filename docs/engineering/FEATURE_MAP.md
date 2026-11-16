# Карта поведения Musya

| Поведение | Точка входа | Инвариант | Позитивная и негативная проверки | Команда | Доказательство |
| --- | --- | --- | --- | --- | --- |
| Создание задачи оценки | musya/scripts/evaluate.py: prepare | Только новый изолированный каталог. | Подготовка всех случаев; отказ перезаписать каталог. | python3 -B musya/scripts/check.py | .musya/runs/verification.json |
| Проверка результата | musya/scripts/evaluate.py: check | Реальное поведение и сохранность исходных тестов; процесс оценивается отдельно. | Корректный API/CLI; неисправный API, подменённые тесты и неверный ввод. | python3 -B musya/scripts/check.py | .musya/runs/verification.json |
| Сохранность проекта | musya/scripts/evaluate.py: snapshot | Анализ не меняет проект, пользовательские правки сохраняются. | Неизменённый проект; изменение, удаление и новый пустой каталог, потеря notes.txt. | python3 -B musya/scripts/check.py | .musya/runs/verification.json |
| Исходный сбой | musya/references/verification.md | Успех целевого исправления не скрывает обязательный исходный сбой. | Исправленный clamp и падающий legacy; запрет изменения legacy и тестов. | evaluate.py prepare/check baseline-failure по references/evaluation.md | .musya/runs/evaluations/ |
| Поэтапный фундамент | musya/references/foundation.md | Все области остаются в перечне; готовность задачи отделена от фундамента. | staged-foundation; повторное подключение repeat не создаёт дубликаты. | evaluate.py prepare/check по references/evaluation.md | .musya/runs/evaluations/ |
| Честный статус процесса | musya/SKILL.md и references/evaluation.md | Недоступное ревью и непройденный сценарий не считаются успешными. | no-reviewer и отдельная независимая оценка ответа; тесты драйвера не равны прогону агента. | Восемь сценариев по references/evaluation.md | .musya/runs/evaluations/ |

Пути артефактов обозначают место результатов; сам путь не подтверждает
успешный запуск. Фактические статусы и ограничения хранятся в FOUNDATION
и отчётах. Историческое качество навыка до этой матрицы не проверено.
