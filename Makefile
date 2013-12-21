

PYTEST := py.test

ANTLR  := java -jar $(abspath 3rdparty/antlr3/antlr.jar)

generated_antlr_files := \
		src/bkl/parser/BakefileParser.py \
		src/bkl/parser/BakefileLexer.py \
		src/bkl/parser/Bakefile.tokens \
		src/bkl/parser/BakefileQuotedStringParser.py \
		src/bkl/parser/BakefileQuotedStringLexer.py \
		src/bkl/parser/BakefileQuotedString.tokens

all: parser doc

parser: $(generated_antlr_files)

%Parser.py %Lexer.py %.tokens: %.g
	cd $(dir $<) && $(ANTLR) $(notdir $<)

# the island-grammar parser emits the same tokens as the main one
src/bkl/parser/BakefileQuotedStringParser.py: src/bkl/parser/Bakefile.tokens

doc: parser
	$(MAKE) -C docs all

clean:
	rm -f $(generated_antlr_files)
	find . -name '*.pyc' -delete
	$(MAKE) -C docs clean

test: all
	$(PYTEST)

.PHONY: clean test doc parser
