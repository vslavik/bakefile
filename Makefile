

ANTLR  := antlr-3.4
PYTEST := py.test


grammar_file := src/bkl/parser/Bakefile.g
parser_file  := src/bkl/parser/BakefileParser.py
lexer_file   := src/bkl/parser/BakefileLexer.py


all: parser doc

parser: $(parser_file) $(lexer_file)

%Parser.py %Lexer.py: %.g
	cd $(dir $<) && $(ANTLR) $(notdir $<)

doc: parser
	$(MAKE) -C docs all

clean:
	rm -f $(lexer_file) $(parser_file)
	find . -name '*.pyc' -delete
	$(MAKE) -C docs clean

test: all
	$(PYTEST)


.PHONY: clean test doc parser
