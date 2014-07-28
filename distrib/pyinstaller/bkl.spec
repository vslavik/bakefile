# -*- mode: python -*-
a = Analysis(['..\\..\\src\\tool.py'],
             pathex=[
                      '..\\..\\src',
                      '..\\..\\3rdparty\\antlr3\\python-runtime',
                    ],
             hiddenimports=['encodings','antlr3'],
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
