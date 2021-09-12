import nox

nox.options.sessions = ['lint', 'tests']
nox.options.reuse_existing_virtualenvs = True


@nox.session
def tests(session):
    session.install('pytest', 'testfixtures', 'coverage', 'pytest-cov')
    session.install('--quiet', '-r', 'requirements.txt')
    session.install('-e', '.')
    session.run('pytest', '--cov-report', 'term', '--cov=dependencynet')


@nox.session
def lint(session):
    session.install('flake8')
    session.run(
            'flake8',
            '--exclude=.git,__pycache__,.nox,.pytest_cache,target',
            '--select=W,E112,E113,F,C9,N8',
            '--ignore=E501,I202,F401,F841',
            '--show-source',
            '.', 'noxfile.py')


@nox.session
def tests_fanout(session):
    session.install('pytest', 'testfixtures', 'coverage', 'pytest-cov')
    session.install('--quiet', '-r', 'requirements.txt')
    session.install('-e', '.')
    session.run('pytest', '-m', 'fanout')


@nox.session
def tests_towns(session):
    session.install('pytest', 'testfixtures', 'coverage', 'pytest-cov')
    session.install('--quiet', '-r', 'requirements.txt')
    session.install('-e', '.')
    session.run('pytest', '-m', 'towns')


@nox.session
def tests_trips(session):
    session.install('pytest', 'testfixtures', 'coverage', 'pytest-cov')
    session.install('--quiet', '-r', 'requirements.txt')
    session.install('-e', '.')
    session.run('pytest', '-m', 'trips')


@nox.session
def tests_twolevels(session):
    session.install('pytest', 'testfixtures', 'coverage', 'pytest-cov')
    session.install('--quiet', '-r', 'requirements.txt')
    session.install('-e', '.')
    session.run('pytest', '-m', 'twolevels')



@nox.session
def tests_notebooks(session):
    session.install('pytest', 'testfixtures', 'coverage', 'pytest-cov', 'pytest-notebook')
    session.install('--quiet', '-r', 'requirements.txt')
    session.install('-e', '.')
    session.run('pytest', '--nb-test-files')


@nox.session
def lint_notebooks(session):
    # flakehell requieres toml
    # session.install('flake8', 'flakehell')
    # session.run(
    #        'flakehell',
    #        'lint',
    #        './notebooks/')
    session.install('nblint')
    session.install('--quiet', '-r', 'requirements.txt')

    import os
    for root, dirs, files in os.walk('./notebooks/'):
        if 'output' not in root:
            for name in files:
                if name.endswith('.ipynb'):
                    if 'checkpoint' not in name:
                        filename = os.path.join(root, name)
                        session.run(
                                'nblint',
                                '--linter',
                                'pyflakes',
                                filename)
    # TODO ignore magic


@nox.session
def check_notebooks(session):
    session.install('nbconvert')
    session.install('--quiet', '-r', 'requirements.txt')
    import os
    for root, dirs, files in os.walk('./notebooks/'):
        if 'output' not in root:
            for name in files:
                if name.endswith('.ipynb'):
                    if 'checkpoint' not in name:
                        filename = os.path.join(root, name)
                        session.run(
                                'jupyter',
                                'nbconvert',
                                '--to',
                                'notebook',
                                '--execute',
                                '--output',
                                'check',
                                filename)
