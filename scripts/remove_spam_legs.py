from django.db import connection
from django.utils.timezone import now

script_start = now()


def run():
    cursor = connection.cursor()

    print('calculating stats')
    cursor.execute('insert into statistics_invalidcallstats (server_id, day, unknown_destination, other) '
        " select server_id, date(ts_start), sum(case when local='' then 0 else 1 end), sum(case when local='' then 1 else 0 end) from statistics_leg "
        ' where ts_stop is null and ts_start is not null group by date(ts_start), server_id'
        ' on conflict do nothing'
                   )
    print(now() - script_start)

    print('removing spam data, unknown desination')
    cursor.execute('delete from statistics_leg where call_id is null and ts_stop is null')
    print('removing spam data, probably ringingtimeout')
    cursor.execute("delete from statistics_leg where ts_stop is null and local='' and remote <> '' and target='guest'")
    print(now() - script_start)

    print('cluster')
    cursor.execute('cluster statistics_leg using statistics_leg_pkey')
    print(now() - script_start)


if __name__ == '__main__':
    print('start')
    run()




