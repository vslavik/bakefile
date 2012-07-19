

ANTLR  := antlr-3.4
PYTEST := py.test


grammar_file := src/bkl/parser/Bakefile.g
parser_file  := src/bkl/parser/BakefileParser.py
lexer_file   := src/bkl/parser/BakefileLexer.py

antlr_from_submodule := 3rdparty/antlr3/target/antlr

antlr_is_34 := $(if $(shell $(ANTLR) -version 2>&1 | grep 'Version 3.4'),yes,no)
ifeq "$(antlr_is_34)" "yes"
	antlr_path := $(shell which $(ANTLR))
else
	antlr_path := $(abspath $(antlr_from_submodule))
endif

all: parser doc

parser: $(parser_file) $(lexer_file)

%Parser.py %Lexer.py: %.g $(antlr_path)
	cd $(dir $<) && $(antlr_path) $(notdir $<)

doc: parser
	$(MAKE) -C docs all

clean:
	rm -f $(lexer_file) $(parser_file)
	find . -name '*.pyc' -delete
	$(MAKE) -C docs clean
	$(MAKE) -C 3rdparty clean

test: all
	$(PYTEST)

# Antlr from included submodule:
$(antlr_from_submodule):
	$(MAKE) -C 3rdparty antlr


.PHONY: clean test doc parser
