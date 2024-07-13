FROM ubuntu:18.04 AS antbuild

RUN apt-get update && apt-get -y install default-jre make

WORKDIR /app
COPY . /app

RUN make parser


FROM ubuntu:18.04 AS runtime

RUN apt-get update && apt-get -y install git python python-pip
RUN pip install clint

WORKDIR /app
COPY --from=antbuild /app /app

ENV PATH "/app:${PATH}"

ENTRYPOINT ["bkl"]
