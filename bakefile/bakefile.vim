" Vim syntax file
" Language:	Bakefile makefile
" Maintainer:	Vaclav Slavik <vslavik@fastmail.fm>
"
" Based on Docbook syntax file by Devin Weaver <ktohg@tritarget.com>
"

" For version 5.x: Clear all syntax items
" For version 6.x: Quit when a syntax file was already loaded
if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

doau FileType xml
syn cluster xmlTagHook add=bakefileKeyword
syn cluster xmlRegionHook add=bakefileVariable
syn case match

syn match bakefileVariable "$([^)]*)" contained

syn keyword bakefileKeyword makefile set unset using option include contained
syn keyword bakefileKeyword command phony action dll exe lib contained
syn keyword bakefileKeyword template description output fragment contained
syn keyword bakefileKeyword requires contained
syn match   bakefileKeyword "define-rule" contained
syn match   bakefileKeyword "define-tag" contained
syn match   bakefileKeyword "default-value" contained

" Define the default highlighting.
hi def link bakefileKeyword  Statement
hi def link bakefileVariable PreProc

let b:current_syntax = "bakefile"
