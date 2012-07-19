
ANTLR_VERSION := 3.4.1-SNAPSHOT

antlr_script := antlr3/target/antlr
antlr_jar    := antlr3/target/antlr-master-$(ANTLR_VERSION)-completejar.jar


all: antlr

antlr: $(antlr_script)

$(antlr_script): $(antlr_jar)
	echo '#!/bin/sh' >$@
	echo 'java -jar $(abspath $(antlr_jar)) "$$@"' >>$@
	chmod +x $@

$(antlr_jar):
	(cd antlr3 && mvn -Dmaven.test.skip=true package assembly:assembly)

clean:
	rm -rf antlr3/target


.PHONY: clean antlr
