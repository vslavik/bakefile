
def _find_all_plugins():
    from os import walk
    for root, dirs, files in walk('../../src/bkl/plugins'):
        for f in files:
            if f.endswith('.py') and not f == '__init__.py':
                yield 'plugins.%s' % f[:-3]

hiddenimports = ['plugins'] + list(_find_all_plugins())

datas = [
    ('../../src/bkl/plugins/*.py', 'plugins'),
    ]
