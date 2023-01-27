FROM continuumio/miniconda3
RUN conda create -n mqtt -c conda-forge "python>=3.10" paho-mqtt pyserial
WORKDIR /scripts
COPY *.py /scripts/
ENV PATH /opt/conda/envs/mqtt/bin:$PATH
