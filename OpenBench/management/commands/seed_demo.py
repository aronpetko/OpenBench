"""
Populate a local database with enough fake workloads to look at the UI.

    python manage.py seed_demo --settings=OpenSite.settings_local

Creates a superuser (demo / demo), a machine, and a spread of SPRT tests in
every result state, each with a synthetic LLR history so the workload page's
history graph has something to draw. Intended for development only.
"""

import os
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import OpenBench.utils

from OpenBench.config import OPENBENCH_CONFIG
from OpenBench.models import Engine, Machine, Profile, Result, Test


DEMO_USER = 'demo'
DEMO_PASS = 'demo'

BRANCHES = [
    ('history_bonus_tweak' , 'master'),
    ('lmr_depth_scaling'   , 'master'),
    ('nnue_l1_1536'        , 'master'),
    ('razoring_margin'     , 'master'),
    ('tt_replacement_v3'   , 'master'),
    ('singular_extensions' , 'master'),
    ('corrhist_pawn_king'  , 'master'),
    ('futility_prune_v2'   , 'master'),
]

INFO_NOTES = [
    'Rebased onto master after the corrhist merge.',
    '',
    'Retest at LTC before merging; STC was noisy.',
    'Depends on the pending TT rewrite.',
    '',
    'Author asked for this to stay queued behind the datagen run.',
]

# (name, currentllr, drift, finished, passed, failed)
SCENARIOS = [
    ('running-up'   ,  1.62, +1.0, False, False, False),
    ('running-down' , -1.20, -1.0, False, False, False),
    ('passed'       ,  2.96, +1.0, True , True , False),
    ('failed'       , -2.94, -1.0, True , False, True ),
    ('failed-yellow', -2.91, -0.6, True , False, True ),
    ('running-flat' ,  0.18, +0.1, False, False, False),
]


class Command(BaseCommand):

    help = 'Create demo users, engines and workloads for local UI development'

    def add_arguments(self, parser):
        parser.add_argument('--tests', type=int, default=24, help='How many workloads to create')
        parser.add_argument('--seed' , type=int, default=1917, help='Random seed, for repeatable data')

    def handle(self, *args, **options):

        random.seed(options['seed'])

        user    = self.create_user()
        machine = self.create_machine(user)
        engines = list(OPENBENCH_CONFIG['engines'].keys())

        for i in range(options['tests']):
            test = self.create_test(user, engines[i % len(engines)], i)
            self.create_result(test, machine)
            self.create_llr_history(test)

        self.stdout.write(self.style.SUCCESS(
            'Seeded %d workloads. Log in as %s / %s' % (options['tests'], DEMO_USER, DEMO_PASS)))

    def create_user(self):

        user, created = User.objects.get_or_create(
            username=DEMO_USER, defaults={'email': 'demo@example.com'})

        if created:
            user.set_password(DEMO_PASS)
            user.is_staff = user.is_superuser = True
            user.save()

        Profile.objects.get_or_create(
            user=user, defaults={'enabled': True, 'approver': True, 'engine': 'Integral'})

        return user

    def create_machine(self, user):

        machine, _ = Machine.objects.get_or_create(
            user=user,
            defaults={
                'secret'    : 'demo-secret',
                'dev_mnps'  : 3.21,
                'base_mnps' : 3.18,
                'info'      : {
                    'machine_name'   : 'demo-box',
                    'os_name'        : 'Linux',
                    'os_ver'         : '6.8.0',
                    'client_ver'     : OPENBENCH_CONFIG['client_version'],
                    'python_ver'     : '3.11.0',
                    'cpu_name'       : 'AMD Ryzen 9 7950X',
                    'cpu_flags'      : ['avx2', 'bmi2', 'popcnt'],
                    'logical_cores'  : 32,
                    'physical_cores' : 16,
                    'ram_total_mb'   : 65536,
                    'syzygy_max'     : 6,
                    'concurrency'    : 30,
                    'sockets'        : 1,
                    'focus'          : 'None',
                    'tokens'         : {},
                    'compilers'      : {},
                },
            })

        return machine

    def create_test(self, user, engine_name, index):

        name, _, llr, drift, finished, passed, failed = self.scenario(index)
        source = OPENBENCH_CONFIG['engines'][engine_name]['source']

        dev = Engine.objects.create(
            name=name, source=source, sha='%040x' % (random.getrandbits(160)),
            bench=random.randint(1000000, 9999999))

        base = Engine.objects.create(
            name='master', source=source, sha='%040x' % (random.getrandbits(160)),
            bench=random.randint(1000000, 9999999))

        games = random.randint(2000, 90000)
        wins, losses, draws = self.split_games(games, drift)

        return Test.objects.create(
            author=DEMO_USER, book_name='8moves_v3.epd',
            info=INFO_NOTES[index % len(INFO_NOTES)],

            dev=dev, dev_repo=source, dev_engine=engine_name,
            dev_options='Threads=1 Hash=16 SyzygyPath=/opt/syzygy',
            dev_time_control='10.0+0.10', dev_netname='',

            base=base, base_repo=source, base_engine=engine_name,
            base_options='Threads=1 Hash=16 SyzygyPath=/opt/syzygy',
            base_time_control='10.0+0.10', base_netname='',

            test_mode='SPRT',
            elolower=0.0, eloupper=5.0, alpha=0.05, beta=0.05,
            lowerllr=-2.94, upperllr=2.94, currentllr=llr,

            games=games, wins=wins, losses=losses, draws=draws,
            LL=games // 40, LD=games // 8, DD=games // 3, DW=games // 8, WW=games // 40,

            priority=random.choice([0, 0, 0, 5, 10]),
            throughput=random.choice([100, 250, 500, 1000]),

            passed=passed, failed=failed, finished=finished,
            approved=True, error=(index % 11 == 0))

    def create_result(self, test, machine):

        Result.objects.create(
            test=test, machine=machine, games=test.games,
            wins=test.wins, losses=test.losses, draws=test.draws,
            LL=test.LL, LD=test.LD, DD=test.DD, DW=test.DW, WW=test.WW,
            crashes=0, timeloss=random.randint(0, 3))

    def create_llr_history(self, test):

        # A random walk that lands exactly on the test's current LLR, so the
        # graph and the stat block agree with each other

        steps  = random.randint(30, 110)
        walk   = [0.0]
        for _ in range(steps):
            walk.append(walk[-1] + random.gauss(0.0, 0.28))

        # Rescale the walk so it terminates at the real LLR
        offset = test.currentllr - walk[-1]
        walk   = [v + offset * (i / float(steps)) for i, v in enumerate(walk)]

        history = []
        for i, llr in enumerate(walk):
            games = int(round(test.games * i / float(steps)))
            history.append([games, round(llr, 4), int(llr >= -1.0)])

        history[-1] = [test.games, round(test.currentllr, 4), int(test.wins >= test.losses)]

        path = OpenBench.utils.llr_history_path(test.id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        OpenBench.utils._write_llr_history(path, history)

    def scenario(self, index):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        branch   = BRANCHES[index % len(BRANCHES)]
        return (branch[0], branch[1]) + scenario[1:]

    def split_games(self, games, drift):
        draws  = int(games * random.uniform(0.55, 0.72))
        rest   = games - draws
        edge   = int(rest * 0.5 + drift * rest * random.uniform(0.005, 0.02))
        wins   = max(0, min(rest, edge))
        return wins, rest - wins, draws
