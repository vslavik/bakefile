

ANTLR  := antlr-3.4
PYTEST := py.test


generated_antlr_files := \
		src/bkl/parser/BakefileParser.py \
		src/bkl/parser/BakefileLexer.py \
		src/bkl/parser/BakefileQuotedStringParser.py \
		src/bkl/parser/BakefileQuotedStringLexer.py

antlr_from_submodule := $(abspath 3rdparty/antlr3/target/antlr)

antlr_is_34 := $(if $(shell $(ANTLR) -version 2>&1 | grep 'Version 3.4'),yes,no)
ifeq "$(antlr_is_34)" "yes"
	antlr_path := $(shell which $(ANTLR))
else
	antlr_path := $(antlr_from_submodule)
endif

all: parser doc

parser: $(generated_antlr_files)

%Parser.py %Lexer.py: %.g $(antlr_path)
	cd $(dir $<) && $(antlr_path) $(notdir $<)

doc: parser
	$(MAKE) -C docs all

clean:
	rm -f $(generated_antlr_files)
	find . -name '*.pyc' -delete
	$(MAKE) -C docs clean
	$(MAKE) -C 3rdparty clean

test: all
	$(PYTEST)

# Antlr from included submodule:
$(antlr_from_submodule):
	$(MAKE) -C 3rdparty antlr


.PHONY: clean test doc parser
