from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from judge.contest_format.default import DefaultContestFormat
from judge.contest_format.registry import register_contest_format
from judge.timezone import from_database_time
from judge.utils.timedelta import nice_repr


@register_contest_format('atcoder')
class AtCoderContestFormat(DefaultContestFormat):
    name = gettext_lazy('AtCoder')
    config_defaults = {'penalty': 5}
    '''
        penalty: Number of penalty minutes each incorrect submission adds. Defaults to 5.
    '''

    @classmethod
    def validate(cls, config):
        if config is None:
            return

        if not isinstance(config, dict):
            raise ValidationError('AtCoder-styled contest expects no config or dict as config')

        for key, value in config.items():
            if key not in cls.config_defaults:
                raise ValidationError('unknown config key "%s"' % key)
            if not isinstance(value, type(cls.config_defaults[key])):
                raise ValidationError('invalid type for config key "%s"' % key)

    def __init__(self, contest, config):
        self.config = self.config_defaults.copy()
        self.config.update(config or {})
        self.contest = contest

    def update_participation(self, participation):
        cumtime = 0
        points = 0
        format_data = {}

        with connection.cursor() as cursor:
            cursor.execute('''
            SELECT MAX(cs.points) as `score`, (
                SELECT MIN(csub.date)
                    FROM judge_contestsubmission ccs LEFT OUTER JOIN
                         judge_submission csub ON (csub.id = ccs.submission_id)
                    WHERE ccs.problem_id = cp.id AND ccs.participation_id = %s AND ccs.points = MAX(cs.points)
            ) AS `time`, (
                SELECT COUNT(csub.id)
                    FROM judge_contestsubmission ccs LEFT OUTER JOIN
                         judge_submission csub ON (csub.id = ccs.submission_id)
                    WHERE ccs.problem_id = cp.id AND ccs.participation_id = %s AND csub.result NOT IN ('CE', 'IE') AND
                          csub.date <= `time`
            ) AS `prev`, cp.id AS `prob`
            FROM judge_contestproblem cp INNER JOIN
                 judge_contestsubmission cs ON (cs.problem_id = cp.id AND cs.participation_id = %s) LEFT OUTER JOIN
                 judge_submission sub ON (sub.id = cs.submission_id)
            GROUP BY cp.id
            ''', (participation.id, participation.id, participation.id))

            for score, time, prev, prob in cursor.fetchall():
                dt = (from_database_time(time) - participation.start).total_seconds()
                if score:
                    cumtime += dt + prev * self.config['penalty'] * 60

                format_data[str(prob)] = {'time': dt, 'points': score}
                points += score

        participation.cumtime = max(cumtime, 0)
        participation.score = points
        participation.format_data = format_data
        participation.save()
