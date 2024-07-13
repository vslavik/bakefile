FROM ubuntu:18.04 AS build

RUN apt-get update && apt-get -y install python python-dev python-libxml2 make autoconf automake libtool swig

# copy source tree
COPY . .

# placeholder files to avoid building docs
RUN mkdir doc/man
RUN touch doc/man/bakefile.1 doc/man/bakefilize.1 doc/man/bakefile_gen.1

# build and install to /usr/local
RUN ./bootstrap
RUN ./configure && make && make install


FROM ubuntu:18.04 AS runtime

RUN mkdir /share
WORKDIR /share
RUN apt-get update && apt-get -y install python python-libxml2
COPY --from=build /usr/local /usr/local
COPY docker-wrapper.sh /
RUN chmod +x /docker-wrapper.sh

ENTRYPOINT ["/docker-wrapper.sh"]
