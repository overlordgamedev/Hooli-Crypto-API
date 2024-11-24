# Базовый образ
FROM ubuntu:22.04

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    wget \
    tar \
    dirmngr \
    screen 

# Указываем актуальную версию Dash Core
ARG DASH_VERSION=21.1.1
RUN wget https://github.com/dashpay/dash/releases/download/v${DASH_VERSION}/dashcore-${DASH_VERSION}-x86_64-linux-gnu.tar.gz --no-check-certificate \
    && tar -zvxf dashcore-${DASH_VERSION}-x86_64-linux-gnu.tar.gz \
    && mv dashcore-${DASH_VERSION}/bin/* /usr/bin/ \
    && rm -rf dashcore-${DASH_VERSION} dashcore-${DASH_VERSION}-x86_64-linux-gnu.tar.gz

# Создаем директорию конфигурации и добавляем конфиг
RUN mkdir -p /root/.dashcore
COPY dash.conf /root/.dashcore/dash.conf

# Указываем команду для запуска Dash
CMD ["dashd"]
