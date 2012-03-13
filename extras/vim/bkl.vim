" Vim syntax file
" Language:	Bakefile
" Maintainer:	Vadim Zeitlin <vz-bakefile@zeitlins.org>
" Last Change:	2012-02-22

if exists("b:current_syntax")
    finish
endif

syn case match
syn sync fromstart
set isk+=.,-

" Simple keywords that can occur anywhere (this is not really true for
" bklTarget but we can't easily avoid recognizing it inside another target).
syn keyword	bklTarget	action dll exe library external
syn keyword	bklIf		if

" Statements and properties that can only appear at global scope, outside of
" any block.
syn keyword	bklGlobalStat	submodule
syn keyword	bklGlobalProp	toolsets
syn match	bklGlobalProp	"\<vs2010.generate-solution\ze *=" nextgroup=bklBoolRHS skipwhite

" Properties common to absolutely all targets.
syn keyword	bklCommonProp	deps pre-build-commands post-build-commands contained
syn keyword	bklCommonProp	vs2010.guid vs2010.projectfile contained
syn match	bklCommonProp	"vs2010\.option\(\.\w\+\)\{1,2}" contained

" Properties that can occur inside action/exe/lib/dll targets only.
syn keyword	bklActionProp	commands contained
syn keyword	bklExeProp	exename contained
syn keyword	bklDllProp	libname contained
syn keyword	bklLibProp	libname contained

" Properties that can only occur in the targets building something i.e.
" exe/lib/dll ones.
syn keyword	bklBuildProp	archs compiler-options c-compiler-options cxx-compiler-options contained
syn keyword	bklBuildProp	defines headers includedirs libs link-options outputdir sources contained

syn keyword	bklBool 	false true contained
syn region	bklBoolRHS	matchgroup=Normal start="= *" end=";" contains=bklBool contained

syn match	bklBuildProp	"\<win32-unicode\ze *=" nextgroup=bklBoolRHS skipwhite contained

syn keyword	bklSubsys	console windows contained
syn region	bklSubsysRHS	matchgroup=Normal start="= *" end=";" contains=bklSubsys contained
syn match	bklBuildProp	"\<win32-subsystem\ze *=" nextgroup=bklSubsysRHS skipwhite contained

syn keyword	bklLinkage	static dll contained
syn region	bklLinkageRHS	matchgroup=Normal start="= *" end=";" contains=bklLinkage contained
syn match	bklBuildProp	"\<win32-crt-linkage\ze *=" nextgroup=bklLinkageRHS skipwhite contained

syn match	bklVar		"\$(\k\+)"hs=s+2,he=e-1

" Comments definitions stolen from the standard c.vim.
syn region	bklCommentL	start="//" skip="\\$" end="$" keepend contains=@Spell
syn region	bklComment	matchgroup=bklCommentStart start="/\*" end="\*/" contains=@Spell fold extend

" Define a simple block to avoid nested blocks (e.g. "if" statements) inside
" the more specific blocks below from ending them.
syn region	bklBlock	start="{" end="}" transparent

" Cluster of syntax items that can occur in any block.
syn cluster	bklAnyBlock	contains=bklBlock,bklComment,bklCommentL,bklCommonProp,bklIf,bklVar

syn region	bklExeBlock	matchgroup=Normal start="\%\(exe \+\k\+ \+\)\@<={" end="}" contains=@bklAnyBlock,bklBuildProp,bklExeProp
syn region	bklDllBlock	matchgroup=Normal start="\%\(dll \+\k\+ \+\)\@<={" end="}" contains=@bklAnyBlock,bklBuildProp,bklDllProp
syn region	bklLibBlock	matchgroup=Normal start="\%\(library \+\k\+ \+\)\@<={" end="}" contains=@bklAnyBlock,bklBuildProp,bklLibProp
syn region	bklActionBlock	matchgroup=Normal start="\%\(action \+\k\+ \+\)\@<={" end="}" contains=@bklAnyBlock,bklActionProp


" Define the default highlighting.
hi def link bklActionProp	bklCommonProp
hi def link bklBool		Boolean
hi def link bklBuildProp	bklCommonProp
hi def link bklComment		Comment
hi def link bklCommentL		bklComment
hi def link bklCommonProp	bklGlobalProp
hi def link bklDllProp		bklCommonProp
hi def link bklError		Error
hi def link bklExeProp		bklCommonProp
hi def link bklFilename		bklString
hi def link bklGlobalProp	Keyword
hi def link bklGlobalStat	Statement
hi def link bklIf		Conditional
hi def link bklLibProp		bklCommonProp
hi def link bklLinkage		Constant
hi def link bklString		String
hi def link bklSubsys   	Constant
hi def link bklTarget		Statement
hi def link bklVar		Identifier

let b:current_syntax = "bkl"
