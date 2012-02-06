# -*- mode: python -*-
a = Analysis(['..\\..\\src\\tool.py'],
             pathex=['..\\..\\src'],
             hiddenimports=['encodings'],
             hookspath=['.'])
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='bkl.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True )
