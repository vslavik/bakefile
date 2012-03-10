" Vim syntax file
" Language:	Bakefile
" Maintainer:	Vadim Zeitlin <vz-bakefile@zeitlins.org>
" Last Change:	2012-02-22

if exists("b:current_syntax")
    finish
endif

syn case match
set isk+=.,-

" Simple keywords.
syn keyword	bklTarget	action dll exe library
syn keyword	bklIf		if

" Properties names.
syn keyword	bklGlobalStat	submodule
syn keyword	bklGlobalProp	toolsets
syn keyword	bklTargetProp	compiler-options c-compiler-options cxx-compiler-options defines link-options contained
syn keyword	bklTargetProp	deps includedirs sources contained
syn keyword	bklTargetProp	vs2010.projectfile pre-build-commands post-build-commands contained
syn match	bklTargetProp	"vs2010\.option\(\.\w\+\)\{1,2}" contained

syn keyword	bklBool 	false true contained
syn region	bklBoolRHS	matchgroup=Normal start="= *" end=";" contains=bklBool contained

syn match	bklTargetProp	"\<win32-unicode\ze *=" nextgroup=bklBoolRHS skipwhite contained
syn match	bklGlobalMatch	"\<vs2010.generate-solution\ze *=" nextgroup=bklBoolRHS skipwhite contained

syn keyword	bklSubsys	console windows contained
syn region	bklSubsysRHS	matchgroup=Normal start="= *" end=";" contains=bklSubsys contained
syn match	bklTargetProp	"\<win32-subsystem\ze *=" nextgroup=bklSubsysRHS skipwhite contained

syn keyword	bklLinkage	static dll contained
syn region	bklLinkageRHS	matchgroup=Normal start="= *" end=";" contains=bklLinkage contained
syn match	bklTargetProp	"\<win32-crt-linkage\ze *=" nextgroup=bklLinkageRHS skipwhite contained

syn match	bklVar		"\$(\w\+)"hs=s+2,he=e-1

" Define a simple block to avoid nested blocks inside target body from ending
" the body region itself.
syn region	bklBlock	start="{" end="}" transparent
syn region	bklTargetBody	start="\%\(\(action\|dll\|exe\|library\) \+\w\+ \+\)\@<={" end="}" contains=ALLBUT,bklGlobalProp,bklGlobalStat,bklTarget,bklBool,bklSubsys,bklLinkage,bklLinkageRHS,bklSubsysRHS,bklBoolRHS,bklError

" Comments definitions stolen from the standard c.vim.
syn region	bklCommentL	start="//" skip="\\$" end="$" keepend contains=@bklCommentGroup,@Spell
syn region	bklComment	matchgroup=bklCommentStart start="/\*" end="\*/" contains=@bklCommentGroup,@Spell fold extend

" Define the default highlighting.
hi def link bklBool		Boolean
hi def link bklComment		Comment
hi def link bklCommentL		bklComment
hi def link bklError		Error
hi def link bklFilename		bklString
hi def link bklGlobalMatch	bklGlobalProp
hi def link bklGlobalProp	Keyword
hi def link bklGlobalStat	Statement
hi def link bklIf		Conditional
hi def link bklLinkage		Constant
hi def link bklString		String
hi def link bklSubsys   	Constant
hi def link bklTarget		Statement
hi def link bklTargetProp	bklGlobalProp
hi def link bklVar		Identifier

let b:current_syntax = "bkl"
