import sys

from shared.timescale import get_all_model_timescale_sql


def run():

    try:
        sql = get_all_model_timescale_sql(check_timescale_status=False)
    except ValueError as e:
        sys.stderr.write(str(e))
    else:
        print('\n'.join(sql))


