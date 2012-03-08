" Vim syntax file
" Language:	Bakefile
" Maintainer:	Vadim Zeitlin <vz-bakefile@zeitlins.org>
" Last Change:	2012-02-22

if exists("b:current_syntax")
    finish
endif

syn case match
set isk+=".-"

" Simple keywords.
syn keyword	bklTarget	action dll exe library
syn keyword	bklIf		if

" Properties names.
syn keyword	bklGlobalStat	submodule
syn keyword	bklGlobalProp	toolsets
syn keyword	bklTargetProp	compiler-options c-compiler-options cxx-compiler-options defines link-options contained
syn keyword	bklTargetProp	deps includedirs sources contained
syn keyword	bklTargetProp	vs2010.projectfile pre-build-commands post-build-commands contained

syn keyword	bklBoolProp	false true contained
syn match	bklTargetProp	"win32-unicode *=.*$"he=s+13 contains=bklBoolProp
syn match	bklGlobalProp	"vs2010.generate-solution *=.*$"he=s+24 contains=bklBoolProp

syn keyword	bklSubsystem	console windows contained
syn match	bklTargetProp	"win32-subsystem *=.*$"he=s+15 contains=bklSubsystem

syn keyword	bklLinkage	static dll contained
syn match	bklTargetProp	"win32-crt-linkage *=.*$"he=s+17 contains=bklLinkage

syn match	bklVar		"\$(\w\+)"hs=s+2,he=e-1

syn region	bklTargetBody	start="{" end="}" contains=ALLBUT,bklGlobalProp,bklGlobalStat,bklTarget,bklBoolProp,bklSubsystem,bklLinkage,bklError transparent

" Comments definitions stolen from the standard c.vim.
syn region	bklCommentL	start="//" skip="\\$" end="$" keepend contains=@bklCommentGroup,@Spell
syn region	bklComment	matchgroup=bklCommentStart start="/\*" end="\*/" contains=@bklCommentGroup,@Spell fold extend

" Define the default highlighting.
hi def link bklBoolProp		Boolean
hi def link bklComment		Comment
hi def link bklCommentL		bklComment
hi def link bklError		Error
hi def link bklFilename		bklString
hi def link bklGlobalProp	Keyword
hi def link bklGlobalStat	Statement
hi def link bklIf		Conditional
hi def link bklLinkage		Constant
hi def link bklString		String
hi def link bklSubsystem	Constant
hi def link bklTarget		Statement
hi def link bklTargetProp	bklGlobalProp
hi def link bklVar		Identifier

let b:current_syntax = "bkl"
