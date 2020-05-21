FROM ubuntu:latest

# Install.
RUN \
  sed -i 's/# \(.*multiverse$\)/\1/g' /etc/apt/sources.list && \
  apt-get update && \
  apt-get -y upgrade && \
  apt-get install -y build-essential && \
  apt-get install -y software-properties-common && \
  apt-get install -y byobu curl git htop man unzip vim wget && \
  rm -rf /var/lib/apt/lists/*

# Install python 3.7
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update \
   && apt-get install -y python3.7 \
   && ln -s /usr/bin/python3.7 python \
   && ln -s /usr/bin/python3.7 python3

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev \
  && cd /usr/local/bin \
  && pip3 install --upgrade pip

RUN wget https://bootstrap.pypa.io/get-pip.py \
    && python3.7 get-pip.py

RUN apt-get update \
    && apt-get install -y \
        nmap \
        vim

ADD https://api.github.com/repos/mestway/falx/git/refs/heads/bfs version.json
RUN git clone -b bfs https://github.com/Mestway/falx.git
RUN pip install -r /falx/requirements.txt
RUN pip install -e /falx

WORKDIR /falx/server
EXPOSE 8590

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

ENV FLASK_APP server.py
ENV FLASK_RUN_PORT 8590
ENV FLASK_RUN_HOST 0.0.0.0

CMD ["flask", "run"]
